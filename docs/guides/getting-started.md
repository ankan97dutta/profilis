# Getting Started

## Installation

Install Profilis with the dependencies you need:

### Option 1: Using pip with extras (Recommended)

```bash
# Core package only
pip install profilis

# With Flask support
pip install profilis[flask]

# With FastAPI support
pip install profilis[fastapi]

# With Sanic support
pip install profilis[sanic]

# With database support
pip install profilis[flask,sqlalchemy]

# With all integrations
pip install profilis[all]
```

### Option 2: Using requirements files

```bash
# Minimal setup (core only)
pip install -r requirements-minimal.txt

# Flask integration
pip install -r requirements-flask.txt

# SQLAlchemy integration
pip install -r requirements-sqlalchemy.txt

# All integrations
pip install -r requirements-all.txt
```

### Option 3: Manual installation

```bash
# Core dependencies
pip install typing_extensions>=4.0

# Flask support
pip install flask[async]>=3.0

# SQLAlchemy support
pip install sqlalchemy>=2.0 aiosqlite greenlet

# Performance optimization
pip install orjson>=3.8
```

### What Each Option Provides

- **`profilis` (core)**: Basic profiling with Emitter and AsyncCollector
- **`profilis[flask]`**: Core + Flask request/response profiling
- **`profilis[fastapi]`**: Core + FastAPI/ASGI middleware and UI router
- **`profilis[sanic]`**: Core + Sanic middleware and UI blueprint
- **`profilis[sqlalchemy]`**: Core + SQLAlchemy query profiling
- **`profilis[perf]`**: Core + orjson for faster JSON serialization
- **`profilis[all]`**: Everything including all frameworks and databases

## Quick Start with Flask

Here's a minimal Flask application with Profilis integration:

```python
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.exporters.jsonl import JSONLExporter
from profilis.core.async_collector import AsyncCollector

# Setup exporter and collector
exporter = JSONLExporter(dir="./logs", rotate_bytes=1024*1024, rotate_secs=3600)
collector = AsyncCollector(exporter, queue_size=2048, batch_max=128, flush_interval=0.1)

# Create Flask app
app = Flask(__name__)

# Integrate Profilis
profilis = ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics"],
    sample=1.0  # 100% sampling
)

@app.route('/api/users')
def get_users():
    return {"users": ["alice", "bob"]}

@app.route('/health')
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(debug=True)
```

## Quick Start with FastAPI

For FastAPI (and other ASGI apps), use the FastAPI adapter and optional UI router:

```python
from fastapi import FastAPI
from profilis.fastapi.adapter import instrument_fastapi
from profilis.fastapi.ui import make_ui_router
from profilis.exporters.jsonl import JSONLExporter
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore

exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)
stats = StatsStore()

app = FastAPI()
instrument_fastapi(app, emitter, route_excludes=["/profilis"])
app.include_router(make_ui_router(stats, prefix="/profilis"))
# Run with: uvicorn your_module:app --reload
# Visit http://localhost:8000/profilis for the dashboard
```

See [FastAPI Adapter](../adapters/fastapi.md) and [Sanic Adapter](../adapters/sanic.md) for more.

## Function Profiling

Use the `@profile_function` decorator to profile specific functions:

```python
from profilis.decorators.profile import profile_function
from profilis.core.emitter import Emitter
from profilis.exporters.console import ConsoleExporter
from profilis.core.async_collector import AsyncCollector

# Setup profiling
exporter = ConsoleExporter(pretty=True)
collector = AsyncCollector(exporter, queue_size=128, flush_interval=0.2)
emitter = Emitter(collector)

@profile_function(emitter)
def expensive_calculation(n: int) -> int:
    """This function will be automatically profiled."""
    result = sum(i * i for i in range(n))
    return result

@profile_function(emitter)
async def async_operation(data: list) -> list:
    """Async functions are also supported."""
    processed = [item * 2 for item in data]
    return processed

# Use the profiled functions
result = expensive_calculation(1000)
```

## Built-in Dashboard

Enable the built-in dashboard for real-time monitoring:

```python
from flask import Flask
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

app = Flask(__name__)
stats = StatsStore()  # 15-minute rolling window

# Mount the dashboard at /_profilis
ui_bp = make_ui_blueprint(stats, ui_prefix="/_profilis")
app.register_blueprint(ui_bp)

# Visit http://localhost:5000/_profilis to see the dashboard
```

## Manual Event Emission

For custom instrumentation, use the Emitter directly:

```python
from profilis.core.emitter import Emitter
from profilis.exporters.jsonl import JSONLExporter
from profilis.core.async_collector import AsyncCollector
from profilis.runtime import use_span, span_id

# Setup
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
emitter = Emitter(collector)

# Create a trace context
with use_span(trace_id=span_id()):
    # Emit custom events
    emitter.emit_req("/api/custom", 200, dur_ns=15000000)  # 15ms
    emitter.emit_fn("custom_function", dur_ns=5000000)      # 5ms
    emitter.emit_db("SELECT * FROM users", dur_ns=8000000, rows=100)

# Close collector to flush remaining events
collector.close()
```

## What's Available

### Core Components
- **AsyncCollector**: Non-blocking event collection with configurable batching
- **Emitter**: High-performance event creation and emission
- **Runtime Context**: Distributed tracing with trace/span ID management

### Framework Support
- **Flask**: Automatic request/response profiling with hooks
- **FastAPI**: ASGI middleware and built-in UI router (v0.3.0+)
- **Sanic**: Native middleware and built-in UI blueprint (v0.3.0+)
- **SQLAlchemy**: Query performance monitoring and instrumentation

### Exporters
- **JSONL**: Rotating log files with configurable retention
- **Console**: Pretty-printed output for development
- **Prometheus**: Counters and histograms for HTTP, functions, and DB; `/metrics` endpoint (v0.4.0+)

### UI
- **Built-in Dashboard**: Real-time metrics, error tracking, and performance visualization

### Decorators
- **@profile_function**: Automatic timing for sync and async functions

## Next Steps

- [Configuration](configuration.md) - Learn about tuning and customization
- [Framework Adapters](../adapters/flask.md) - Explore Flask, FastAPI, and Sanic integration
- [Database Support](../databases/sqlalchemy.md) - Understand SQLAlchemy and other database integrations
- [Exporters](../exporters/jsonl.md) - Configure JSONL, Console, and [Prometheus](../exporters/prometheus.md) output
- [Architecture](../architecture/architecture.md) - Learn about the system design
