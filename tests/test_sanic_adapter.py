import asyncio
import time
from typing import Any, Optional

from sanic import Sanic
from sanic.response import json as sanic_json
from sanic.response import text as sanic_text
from sanic_testing.testing import SanicTestClient

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore
from profilis.sanic.adapter import SanicConfig, instrument_sanic_app
from profilis.sanic.ui import ErrorItem, make_ui_blueprint, record_error

# Constants for magic numbers (PLR2004)
HTTP_OK = 200
HTTP_INTERNAL_SERVER_ERROR = 500


def make_collector_sink() -> tuple[AsyncCollector[dict[str, Any]], list[Any]]:
    items: list[Any] = []
    col: AsyncCollector[dict[str, Any]] = AsyncCollector(
        lambda b: items.extend(b), queue_size=100, flush_interval=0.02
    )
    return col, items


def create_sanic_app(
    emitter: Emitter,
    cfg: Optional[SanicConfig] = None,
) -> Sanic:
    app = Sanic("profilis-test")

    @app.route("/ok")
    async def ok(request: Any) -> Any:
        return sanic_json({"ok": True})

    @app.route("/err")
    async def err(request: Any) -> None:
        raise RuntimeError("boom-sanic")

    @app.route("/slow")
    async def slow(request: Any) -> Any:
        await asyncio.sleep(0.01)
        return sanic_text("done")

    instrument_sanic_app(app, emitter, cfg or SanicConfig())
    return app


def test_sanic_basic_emits() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    app = create_sanic_app(em, SanicConfig(sampling_rate=1.0))
    client = SanicTestClient(app)
    request, response = client.get("/ok")
    assert response.status == HTTP_OK
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(i.get("status") == HTTP_OK for i in http_items)
    col.close()


def test_sanic_exception_emits() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    app = create_sanic_app(em, SanicConfig(sampling_rate=1.0, always_sample_errors=True))
    client = SanicTestClient(app)
    # In modern Sanic + sanic-testing, exceptions are turned into 500 responses
    # instead of being raised directly to the caller.
    request, response = client.get("/err")
    assert response.status == HTTP_INTERNAL_SERVER_ERROR
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(i.get("status") == HTTP_INTERNAL_SERVER_ERROR and i.get("error") for i in http_items)
    col.close()


def test_sanic_mount_asgi_ui_no_crash() -> None:
    # Basic smoke test: mount a trivial ASGI app and ensure app starts and
    # receives a well-formed ASGI scope with correct path/root_path.
    seen_scopes: list[dict[str, Any]] = []

    async def asgi_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        seen_scopes.append(scope)
        if scope["type"] == "http":
            headers = [(b"content-type", b"text/plain; charset=utf-8")]
            await send({"type": "http.response.start", "status": HTTP_OK, "headers": headers})
            await send({"type": "http.response.body", "body": b"ok", "more_body": False})

    col, items = make_collector_sink()
    em = Emitter(col)
    app = Sanic("mount-test")

    # instrument with mount
    instrument_sanic_app(
        app,
        em,
        SanicConfig(),
        mount_asgi_app=asgi_app,
        mount_path="/profilis",
    )
    client = SanicTestClient(app)
    req, res = client.get("/profilis")
    assert res.status == HTTP_OK
    assert res.text == "ok"

    # The mounted ASGI app should see path="/" and root_path="/profilis"
    assert seen_scopes, "ASGI app was not invoked"
    scope = seen_scopes[-1]
    assert scope["path"] == "/"
    assert scope.get("root_path") == "/profilis"

    col.close()


def test_sanic_ui_metrics_and_errors_endpoints() -> None:
    # Sanic UI blueprint should expose working /metrics.json and /errors.json endpoints.
    stats = StatsStore()
    app = Sanic("ui-test")

    # Seed stats with a couple of samples
    stats.record(int(10 * 1e6), error=False)
    stats.record(int(50 * 1e6), error=True)

    # Seed error ring with a sample error
    record_error(
        ErrorItem(
            ts_ns=123456789,
            route="/boom",
            status=HTTP_INTERNAL_SERVER_ERROR,
            exception_type="RuntimeError",
            exception_value="demo",
            traceback="",
        )
    )

    bp = make_ui_blueprint(stats, ui_prefix="/profilis")
    app.blueprint(bp)

    client = SanicTestClient(app)

    # metrics.json should return a JSON payload with basic keys
    req, res = client.get("/profilis/metrics.json")
    assert res.status == HTTP_OK
    data = res.json
    assert "rps" in data
    assert "p50" in data
    assert "p95" in data

    # errors.json should include at least one error record
    req, res = client.get("/profilis/errors.json")
    assert res.status == HTTP_OK
    errors = res.json.get("errors") or []
    assert any(e.get("route") == "/boom" for e in errors)


def test_sanic_exception_records_error_ring() -> None:
    """
    The Sanic adapter exception handler should emit HTTP error items.

    NOTE: SanicTestClient starts a fresh worker process per request, so we
    cannot reliably assert cross-request state in the in-memory UI error
    ring here. That integration is covered separately in
    `test_sanic_ui_metrics_and_errors_endpoints` using direct `record_error`.
    """

    col, items = make_collector_sink()
    em = Emitter(col)

    app = create_sanic_app(em, SanicConfig(sampling_rate=1.0, always_sample_errors=True))
    client = SanicTestClient(app)

    # Trigger an error route to exercise the adapter's exception handler
    req, res = client.get("/err")
    assert res.status == HTTP_INTERNAL_SERVER_ERROR

    # Give the async collector a moment
    time.sleep(0.05)

    # Ensure HTTP error item was emitted with an error payload
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(i.get("status") == HTTP_INTERNAL_SERVER_ERROR and i.get("error") for i in http_items)

    col.close()
