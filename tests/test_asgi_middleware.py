import time
from typing import Any, Union

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from profilis.asgi.middleware import ASGIConfig, ProfilisASGIMiddleware
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.runtime import use_span

# Constants
HTTP_OK = 200
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_SERVER_ERROR = 500
EXPECTED_MIN_ITEMS = 3


def make_collector_sink() -> tuple[AsyncCollector[Any], list[Any]]:
    items: list[Any] = []
    col: AsyncCollector[Any] = AsyncCollector(items.extend, queue_size=100, flush_interval=0.02)
    return col, items


def ok_view(request: Any) -> JSONResponse:
    return JSONResponse({"ok": True})


def bad_view(request: Any) -> JSONResponse:
    return JSONResponse({"error": "bad"}, status_code=400)


def exc_view(request: Any) -> None:
    raise RuntimeError("boom from view")


def server_error_view(request: Any) -> JSONResponse:
    return JSONResponse({"error": "server error"}, status_code=500)


def create_app(emitter: Emitter, cfg: Union[ASGIConfig, None] = None) -> ProfilisASGIMiddleware:
    routes = [
        Route("/ok", ok_view),
        Route("/bad", bad_view),
        Route("/exc", exc_view),
        Route("/server-error", server_error_view),
    ]
    starlette_app = Starlette(routes=routes)
    # wrap as ASGI app manually
    middleware_app = ProfilisASGIMiddleware(starlette_app, emitter, cfg or ASGIConfig())
    return middleware_app


def test_asgi_middleware_records_200_400_500() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    app = create_app(em, ASGIConfig(sampling_rate=1.0, always_sample_errors=True))
    client = TestClient(app)

    r1 = client.get("/ok")
    assert r1.status_code == HTTP_OK
    r2 = client.get("/bad")
    assert r2.status_code == HTTP_BAD_REQUEST
    # exception endpoint should raise inside TestClient and return 500
    with pytest.raises(RuntimeError):
        client.get("/exc")
    # wait for collector to flush
    time.sleep(0.05)
    # find HTTP payloads
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert len(http_items) >= EXPECTED_MIN_ITEMS
    # check one contains 200, one 400, one 500
    statuses = sorted([it.get("status", 0) for it in http_items])
    assert HTTP_OK in statuses
    assert HTTP_BAD_REQUEST in statuses
    assert HTTP_INTERNAL_SERVER_ERROR in statuses
    col.close()


def test_asgi_middleware_propagates_span_id_into_payload() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    app = create_app(em, ASGIConfig(sampling_rate=1.0))
    client = TestClient(app)

    with use_span(trace_id="T1", span_id="S1"):
        r = client.get("/ok")
        assert r.status_code == HTTP_OK
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(i.get("parent_span_id") == "S1" for i in http_items), (
        "parent_span_id should be present in payload"
    )
    col.close()


def test_asgi_middleware_respects_route_excludes() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = ASGIConfig(sampling_rate=1.0, route_excludes=["/ok"])
    app = create_app(em, cfg)
    client = TestClient(app)

    r = client.get("/ok")
    assert r.status_code == HTTP_OK
    r2 = client.get("/bad")
    assert r2.status_code == HTTP_BAD_REQUEST
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    # only /bad should be recorded
    assert all((i.get("path") != "/ok") for i in http_items)
    assert any((i.get("path") == "/bad") for i in http_items)
    col.close()


def test_asgi_middleware_rate_zero_2xx_not_recorded() -> None:
    """With sampling_rate=0, successful (2xx) requests are not recorded."""
    col, items = make_collector_sink()
    em = Emitter(col)
    app = create_app(em, ASGIConfig(sampling_rate=0.0, always_sample_errors=True, random_seed=42))
    client = TestClient(app)

    client.get("/ok")
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert not any(i.get("path") == "/ok" and i.get("status") == HTTP_OK for i in http_items)
    col.close()


def test_asgi_middleware_rate_zero_5xx_always_recorded() -> None:
    """With sampling_rate=0, 5xx responses are always recorded when always_sample_errors=True."""
    col, items = make_collector_sink()
    em = Emitter(col)
    app = create_app(em, ASGIConfig(sampling_rate=0.0, always_sample_errors=True))
    client = TestClient(app)

    r = client.get("/server-error")
    assert r.status_code == HTTP_INTERNAL_SERVER_ERROR
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(
        i.get("path") == "/server-error" and i.get("status") == HTTP_INTERNAL_SERVER_ERROR
        for i in http_items
    )
    col.close()


def test_asgi_middleware_route_excludes_regex() -> None:
    """Route excludes support regex via 're:' prefix."""
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = ASGIConfig(sampling_rate=1.0, route_excludes=["re:^/ok"])
    app = create_app(em, cfg)
    client = TestClient(app)

    client.get("/ok")
    client.get("/bad")
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert all(i.get("path") != "/ok" for i in http_items)
    assert any(i.get("path") == "/bad" for i in http_items)
    col.close()


def test_asgi_middleware_route_override_records_when_override_is_one() -> None:
    """Per-route override with rate 1.0 records that route even when global rate is 0."""
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = ASGIConfig(
        sampling_rate=0.0,
        always_sample_errors=True,
        route_overrides=[("/critical", 1.0)],
        random_seed=42,
    )
    routes = [
        Route("/ok", ok_view),
        Route("/critical", ok_view),
    ]
    starlette_app = Starlette(routes=routes)
    app = ProfilisASGIMiddleware(starlette_app, em, cfg)
    client = TestClient(app)

    client.get("/ok")  # global 0 -> not recorded
    client.get("/critical")  # override 1.0 -> recorded
    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert not any(i.get("path") == "/ok" for i in http_items)
    assert any(i.get("path") == "/critical" for i in http_items)
    col.close()
