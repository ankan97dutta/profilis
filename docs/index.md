# Profilis

A high‑performance, non‑blocking profiler for Python web applications.

## Features

- **Frameworks**: Flask ✅, FastAPI (planned v0.3.0), Sanic (planned v0.3.0)
- **Databases**: SQLAlchemy ✅ (sync & async), MongoDB ✅ (PyMongo), Neo4j ✅ (sync & async), pyodbc ✅ (raw cursor wrapper)
- **UI**: Built‑in, real-time dashboard ✅
- **Exporters**: JSONL (rotating) ✅, Console ✅, Prometheus (planned v0.4.0), OTLP (planned v0.4.0)
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

## What's New in v0.2.0

- ✅ **MongoDB Instrumentation**: PyMongo command monitoring with comprehensive metrics extraction
- ✅ **Neo4j Instrumentation**: Both sync and async graph database profiling with query analysis
- ✅ **pyodbc Instrumentation**: Raw cursor wrapper for execute/executemany operations with SQL monitoring
- ✅ **Enhanced Runtime Context**: Improved tracing support with parent span ID tracking
- ✅ **Extended Database Support**: Now supporting SQLAlchemy, MongoDB, Neo4j, and pyodbc

## What's New in v0.1.0

- ✅ **Core Profiling Engine**: AsyncCollector, Emitter, and runtime context
- ✅ **Flask Integration**: Automatic request/response profiling with hooks
- ✅ **SQLAlchemy Instrumentation**: Both sync and async engine support with query redaction
- ✅ **Built-in Dashboard**: Real-time metrics and error tracking with authentication
- ✅ **JSONL Exporter**: Rotating log files with configurable retention
- ✅ **Function Profiling**: Decorator-based timing for sync/async functions with exception tracking
- ✅ **Performance Optimized**: Non-blocking collection with configurable batching and drop-oldest policy

## Documentation

- [Installation](guides/installation.md) - Complete installation guide and options
- [Getting Started](guides/getting-started.md) - Quick setup and basic usage
- [Configuration](guides/configuration.md) - Tuning and customization
- [Framework Adapters](adapters/flask.md) - Flask integration, FastAPI (planned)
- [Database Support](databases/sqlalchemy.md) - SQLAlchemy integration
- [MongoDB Support](databases/mongodb.md) - MongoDB/PyMongo instrumentation
- [Neo4j Support](databases/neo4j.md) - Neo4j graph database profiling
- [pyodbc Support](databases/pyodbc.md) - pyodbc raw cursor instrumentation
- [Exporters](exporters/jsonl.md) - JSONL and Console exporters
- [Architecture](architecture/architecture.md) - System design and components
- [UI Dashboard](ui/ui.md) - Built-in monitoring interface
