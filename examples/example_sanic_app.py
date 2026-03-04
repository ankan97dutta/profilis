"""
Simple Sanic example using Profilis instrumentation + built-in UI.

Run:
    python examples/example_sanic_app.py
    (or run via sanic CLI depending on your environment)

Visit:
    http://127.0.0.1:8000/ok
    http://127.0.0.1:8000/boom    (simulate an error)
    http://127.0.0.1:8000/profilis/   (Profilis dashboard)
"""

from time import time_ns
from typing import Any

from sanic import Sanic
from sanic.request import Request
from sanic.response import JSONResponse
from sanic.response import json as sanic_json

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore
from profilis.sanic.adapter import SanicConfig, instrument_sanic_app
from profilis.sanic.ui import make_ui_blueprint

# HTTP status used to treat response as server error (PLR2004)
HTTP_INTERNAL_SERVER_ERROR = 500

app = Sanic("profilis-demo")


@app.route("/ok")
async def ok(request: Request) -> JSONResponse:
    return sanic_json({"ok": True})


@app.route("/boom")
async def boom(request: Request) -> None:
    raise RuntimeError("demo boom (sanic)")


def jsonl_export(batch: list[Any]) -> None:
    print("BATCH:")
    for i in batch:
        print(i)


collector = AsyncCollector(jsonl_export, queue_size=256, flush_interval=2.0)
emitter = Emitter(collector)

# Attach core HTTP instrumentation (emits HTTP metrics to the collector)
instrument_sanic_app(
    app,
    emitter,
    SanicConfig(sampling_rate=1.0, always_sample_errors=True),
)


# ---------------- Demo UI wiring (StatsStore) ----------------
stats = StatsStore()


@app.middleware("request")
async def _demo_before(request: Request) -> None:
    # Record start time for StatsStore (independent of the main instrumentation)
    request.ctx._profilis_demo_start_ns = time_ns()


@app.middleware("response")
async def _demo_after(request: Request, response: Any) -> Any:
    start = getattr(request.ctx, "_profilis_demo_start_ns", None)
    if start is not None:
        dur_ns = time_ns() - start
        status = int(
            getattr(response, "status", HTTP_INTERNAL_SERVER_ERROR) or HTTP_INTERNAL_SERVER_ERROR
        )
        is_error = status >= HTTP_INTERNAL_SERVER_ERROR
        stats.record(dur_ns, error=is_error)
    return response


# Mount the Profilis UI under /profilis
ui_bp = make_ui_blueprint(stats, ui_prefix="/profilis")
app.blueprint(ui_bp)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
