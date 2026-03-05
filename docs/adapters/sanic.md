# Sanic Adapter

The Sanic adapter provides automatic request/response profiling via native Sanic middleware and an optional built-in dashboard blueprint.

## Quick Start

```python
from sanic import Sanic
from sanic.response import json as sanic_json
from profilis.sanic.adapter import SanicConfig, instrument_sanic_app
from profilis.sanic.ui import make_ui_blueprint
from profilis.exporters.jsonl import JSONLExporter
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore

app = Sanic("myapp")
exporter = JSONLExporter(dir="./logs", rotate_bytes=1024*1024, rotate_secs=3600)
collector = AsyncCollector(exporter, queue_size=2048, batch_max=128, flush_interval=0.1)
emitter = Emitter(collector)
stats = StatsStore()

instrument_sanic_app(
    app,
    emitter,
    SanicConfig(sampling_rate=1.0, always_sample_errors=True),
)
ui_bp = make_ui_blueprint(stats, ui_prefix="/profilis")
app.blueprint(ui_bp)

@app.route("/api/users")
async def get_users(request):
    return sanic_json({"users": ["alice", "bob"]})

# Visit http://localhost:8000/profilis for the dashboard
```

## Components

### instrument_sanic_app

Attaches Profilis request, response, and exception middleware to your Sanic app so every HTTP request is profiled.

- **Request/response timing** — Duration and status code are recorded.
- **Exception handling** — Server errors and unhandled exceptions are recorded with error info.
- **Config** — `SanicConfig(sampling_rate=1.0, route_excludes=..., always_sample_errors=True)`.
- **Optional ASGI UI mount** — You can pass `mount_asgi_app` and `mount_path` to mount an ASGI app (e.g. dashboard) if your Sanic version supports it; otherwise use the blueprint below.

```python
from profilis.sanic.adapter import SanicConfig, instrument_sanic_app

instrument_sanic_app(
    app,
    emitter,
    SanicConfig(
        sampling_rate=1.0,
        route_excludes=["/profilis", "/health"],
        always_sample_errors=True,
    ),
)
```

### make_ui_blueprint

Serves the built-in Profilis dashboard and JSON endpoints as a Sanic Blueprint:

- `GET /` (under your `ui_prefix`) — HTML dashboard.
- `GET /metrics.json` — StatsStore snapshot.
- `GET /errors.json` — Recent error ring.

Optional Bearer token auth:

```python
ui_bp = make_ui_blueprint(stats, bearer_token="secret", ui_prefix="/profilis")
app.blueprint(ui_bp)
```

## Recording Errors for the Dashboard

Use the shared `record_error` and `ErrorItem` so exceptions appear in the dashboard error ring. In Sanic you can do this in an exception handler or in response/exception middleware (the adapter’s exception middleware already records failures; use `record_error` when you want to add custom error details).

```python
from profilis.sanic.ui import ErrorItem, record_error
from time import time_ns

@app.exception(Exception)
async def on_exception(request, exception):
    record_error(
        ErrorItem(
            ts_ns=time_ns(),
            route=getattr(request, "path", "/"),
            status=500,
            exception_type=type(exception).__name__,
            exception_value=repr(exception),
            traceback="",
        )
    )
    return json({"error": str(exception)}, status=500)
```

## Function Profiling

Use the core decorator with the same emitter for function-level profiling:

```python
from profilis.decorators.profile import profile_function

@profile_function(emitter)
async def expensive_operation():
    ...
```

## Related Documentation

- [Getting Started](../guides/getting-started.md) — Core Profilis usage.
- [UI Dashboard](../ui/ui.md) — Dashboard features.
- [FastAPI Adapter](fastapi.md) — ASGI/FastAPI integration.
- [Exporters](../exporters/jsonl.md) — Output formats.
