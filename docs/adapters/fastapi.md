# FastAPI Adapter

The FastAPI adapter provides automatic request/response profiling via ASGI middleware and an optional built-in dashboard.

## Quick Start

```python
from fastapi import FastAPI
from profilis.fastapi.adapter import instrument_fastapi
from profilis.fastapi.ui import make_ui_router
from profilis.exporters.jsonl import JSONLExporter
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore

exporter = JSONLExporter(dir="./logs", rotate_bytes=1024*1024, rotate_secs=3600)
collector = AsyncCollector(exporter, queue_size=2048, batch_max=128, flush_interval=0.1)
emitter = Emitter(collector)
stats = StatsStore()

app = FastAPI()
instrument_fastapi(app, emitter, route_excludes=["/profilis"])
app.include_router(make_ui_router(stats, prefix="/profilis"))

@app.get("/api/users")
async def get_users():
    return {"users": ["alice", "bob"]}

# Visit http://localhost:8000/profilis for the dashboard
```

Run with: `uvicorn your_module:app --reload`

## Components

### instrument_fastapi

Registers the Profilis ASGI middleware with your FastAPI app so every HTTP request is profiled.

- **Automatic request/response timing** — Duration and status code are captured from the ASGI lifecycle.
- **Route detection** — Uses Starlette/FastAPI route info so you see path templates (e.g. `/api/users/{id}`) instead of raw paths when available.
- **Route exclusions** — Skip paths via `route_excludes` (prefix or exact). Use `"re:..."` for regex (e.g. `"re:^/v1/"`).
- **Per-route overrides** — `route_overrides`: list of `(pattern, rate)`; first match wins. Lets you sample 100% of critical paths while keeping a lower global rate.
- **Always sample 5xx** — With `always_sample_errors=True` (default), 5xx and exceptions are always recorded.
- **Config** — Optional `ASGIConfig(sampling_rate=1.0, route_excludes=..., route_overrides=..., always_sample_errors=True, random_seed=..., rng=...)` from `profilis.asgi.middleware`. Use `random_seed` or `rng` for deterministic tests.

```python
from profilis.asgi.middleware import ASGIConfig
from profilis.fastapi.adapter import instrument_fastapi

instrument_fastapi(
    app,
    emitter,
    config=ASGIConfig(
        sampling_rate=0.1,
        route_excludes=["/profilis", "/health", "re:^/static/"],
        route_overrides=[("/api/critical", 1.0)],
        always_sample_errors=True,
    ),
    route_excludes=["/profilis", "/health"],
)
```

### make_ui_router

Serves the built-in Profilis dashboard and JSON endpoints as a FastAPI `APIRouter`:

- `GET /` (or your prefix) — HTML dashboard (KPIs, sparkline, recent errors).
- `GET /metrics.json` — StatsStore snapshot (latency, RPS, error rate).
- `GET /errors.json` — Recent error ring.

Optional Bearer token auth:

```python
router = make_ui_router(stats, bearer_token="secret", prefix="/profilis")
app.include_router(router)
```

## Manual Error Recording

To feed exceptions into the dashboard error ring (e.g. for the FastAPI exception handler):

```python
from profilis.fastapi.ui import ErrorItem, record_error
from time import time_ns

@app.exception_handler(Exception)
async def record_exception(request: Request, exc: Exception):
    record_error(
        ErrorItem(
            ts_ns=time_ns(),
            route=request.url.path or "-",
            status=500,
            exception_type=type(exc).__name__,
            exception_value=repr(exc),
            traceback="",
        )
    )
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

## Function Profiling

You can still use the core decorator and emitter for function-level profiling:

```python
from profilis.decorators.profile import profile_function

@profile_function(emitter)
async def expensive_handler():
    ...
```

## Related Documentation

- [ASGI middleware](../architecture/architecture.md) — Used under the hood; can be used with any ASGI app.
- [Getting Started](../guides/getting-started.md) — Core Profilis usage.
- [UI Dashboard](../ui/ui.md) — Dashboard features and configuration.
- [Exporters](../exporters/jsonl.md) — JSONL and other output formats.
