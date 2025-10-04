"""
Example: Starlette + Profilis ASGI middleware integration.

Run:
    uvicorn examples.starlette_app:app --reload

Visit:
    http://127.0.0.1:8000/
    http://127.0.0.1:8000/error
    http://127.0.0.1:8000/health  (excluded route)
"""

from typing import Any

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from profilis.asgi.middleware import ASGIConfig, ProfilisASGIMiddleware
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
from profilis.runtime.context import get_span_id, use_span


# Step 1: define your handlers
async def homepage(request: Any) -> JSONResponse:
    return JSONResponse({"hello": "world"})


async def error_page(request: Any) -> None:
    # Simulate a 500 error
    raise RuntimeError("simulated failure")


async def health(request: Any) -> PlainTextResponse:
    # Excluded route (won't be recorded)
    return PlainTextResponse("ok")


async def traced_endpoint(request: Any) -> JSONResponse:
    """Demonstrates ContextVar propagation via profilis.runtime.context"""
    # Set span_id inside a context manager for this request
    with use_span(trace_id="T-001", span_id="S-XYZ"):
        # The middleware will automatically attach parent_span_id="S-XYZ"
        return JSONResponse({"trace": get_span_id()})


routes = [
    Route("/", homepage),
    Route("/error", error_page),
    Route("/health", health),
    Route("/traced", traced_endpoint),
]

# Step 2: configure Profilis instrumentation
jsonl_exporter = JSONLExporter(dir="./logs", rotate_bytes=1024, rotate_secs=5)


collector = AsyncCollector(jsonl_exporter, queue_size=128, flush_interval=2.0)
emitter = Emitter(collector)

# Only sample 50% of normal requests, but always record errors; skip /health
cfg = ASGIConfig(sampling_rate=0.5, route_excludes=["/health"], always_sample_errors=True)


# Step 3: attach middleware
middleware = [
    Middleware(ProfilisASGIMiddleware, emitter=emitter, config=cfg),
]

app = Starlette(debug=True, routes=routes, middleware=middleware)


# Optional: graceful shutdown
@app.on_event("shutdown")
async def shutdown_event() -> None:
    collector.close()
    print("Collector closed")
