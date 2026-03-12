# Profilis

A high‑performance, non‑blocking profiler for Python web applications.

## Features

- **Frameworks**: Flask, FastAPI, Sanic
- **Databases**: SQLAlchemy (sync & async), MongoDB (PyMongo), Neo4j (sync & async), pyodbc (raw cursor wrapper)
- **UI**: Built-in, real-time dashboard
- **Exporters**: JSONL (rotating), Console, Prometheus, OTLP (planned)
- **Performance**: ≤15µs per event, 100K+ events/second

## Quick start (Flask)

```bash
pip install profilis[flask,sqlalchemy]
```

```python
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.exporters.jsonl import JSONLExporter
from profilis.core.async_collector import AsyncCollector

# Setup exporter and collector
exporter = JSONLExporter(dir="./logs", rotate_bytes=1024*1024, rotate_secs=3600)
collector = AsyncCollector(exporter, queue_size=2048, batch_max=128, flush_interval=0.1)

# Create Flask app and integrate Profilis
app = Flask(__name__)
ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics"],
    sample=1.0
)

@app.route('/health')
def ok():
    return {'ok': True}

# Visit /_profilis for the dashboard
```

## Quick start (FastAPI)

```bash
pip install profilis[fastapi,sqlalchemy]
```

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

# Visit /profilis for the dashboard
```

## What's New in v1.0.0

- [x] **1.0 Stable Release**: First stable release of Profilis with a consolidated, production-ready feature set and documentation updates
- [x] **Versioning**: Project version bumped to `1.0.0` (see PyPI / package metadata)

## What's New in v0.4.0

- [x] **Sampling Policies**: Global `sample_rate`, per-route overrides and regex-based route exclusions for ASGI and Sanic; always-sample 5xx responses; seedable RNG for deterministic tests
- [x] **Prometheus Exporter**: HTTP/function/DB counters and histograms (`profilis_http_requests_total`, `profilis_http_request_duration_seconds`, etc.); `/metrics` endpoint for Flask and ASGI; configurable buckets and labels (service, instance, worker, route, status, db_vendor)
- [x] **Reliability**: Graceful shutdown with best-effort flush and timeout; JSONL exporter disk-full handling (no-op + warn once); health metrics `profilis_events_dropped_total` and `profilis_queue_depth` via `register_collector_health_metrics()`

## What's New in v0.3.0

- [x] **ASGI Middleware**: Generic ASGI middleware (`ProfilisASGIMiddleware`) for Starlette and any ASGI framework
- [x] **FastAPI Integration**: `instrument_fastapi()` for automatic request/response profiling; `make_ui_router()` for the built-in dashboard
- [x] **Sanic Integration**: `instrument_sanic_app()` with native request/response/exception middleware; `make_ui_blueprint()` for the dashboard
- [x] **Route Detection**: Automatic route template capture (e.g. OpenAPI path formats) in ASGI/FastAPI
- [x] **Configurable Sampling**: Per-request sampling, route exclusions, and always-sample-errors for ASGI and Sanic

## What's New in v0.2.0

- [x] **MongoDB Instrumentation**: PyMongo command monitoring with comprehensive metrics extraction
- [x] **Neo4j Instrumentation**: Both sync and async graph database profiling with query analysis
- [x] **pyodbc Instrumentation**: Raw cursor wrapper for execute/executemany operations with SQL monitoring
- [x] **Enhanced Runtime Context**: Improved tracing support with parent span ID tracking
- [x] **Extended Database Support**: Now supporting SQLAlchemy, MongoDB, Neo4j, and pyodbc

## What's New in v0.1.0

- [x] **Core Profiling Engine**: AsyncCollector, Emitter, and runtime context
- [x] **Flask Integration**: Automatic request/response profiling with hooks
- [x] **SQLAlchemy Instrumentation**: Both sync and async engine support with query redaction
- [x] **Built-in Dashboard**: Real-time metrics and error tracking with authentication
- [x] **JSONL Exporter**: Rotating log files with configurable retention
- [x] **Function Profiling**: Decorator-based timing for sync/async functions with exception tracking
- [x] **Performance Optimized**: Non-blocking collection with configurable batching and drop-oldest policy

## Documentation

- [Installation](guides/installation.md) - Complete installation guide and options
- [Getting Started](guides/getting-started.md) - Quick setup and basic usage
- [Configuration](guides/configuration.md) - Tuning and customization
- [Framework Adapters](adapters/flask.md) - Flask, [FastAPI](adapters/fastapi.md), [Sanic](adapters/sanic.md)
- [Database Support](databases/sqlalchemy.md) - SQLAlchemy integration
- [MongoDB Support](databases/mongodb.md) - MongoDB/PyMongo instrumentation
- [Neo4j Support](databases/neo4j.md) - Neo4j graph database profiling
- [pyodbc Support](databases/pyodbc.md) - pyodbc raw cursor instrumentation
- [Exporters](exporters/jsonl.md) - JSONL, Console, and [Prometheus](exporters/prometheus.md) exporters
- [Architecture](architecture/architecture.md) - System design and components
- [UI Dashboard](ui/ui.md) - Built-in monitoring interface
