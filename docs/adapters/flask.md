# Flask Adapter

The Flask adapter provides automatic request/response profiling with minimal code changes.

## Quick Start

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
ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics"],
    sample=1.0  # 100% sampling
)

@app.route('/api/users')
def get_users():
    return {"users": ["alice", "bob"]}

if __name__ == "__main__":
    app.run(debug=True)
```

## Features

### Automatic Profiling
- **Request Timing**: Measures request duration with microsecond precision
- **Status Tracking**: Records HTTP status codes and error conditions
- **Route Detection**: Automatically identifies route templates when available
- **Exception Handling**: Captures and records exceptions with stack traces
- **Bytes In/Out**: Tracks request/response sizes (best-effort)

### Performance Optimized
- **Non-blocking**: All profiling happens asynchronously
- **Sampling Support**: Configurable sampling rates for production use
- **Route Exclusion**: Skip profiling for health checks and static assets
- **Minimal Overhead**: ≤15µs per request profiling cost

## Configuration

### Basic Configuration

```python
profilis = ProfilisFlask(
    app,
    collector=collector,           # Required: AsyncCollector instance
    exclude_routes=None,           # Optional: Routes to exclude
    sample=1.0                     # Optional: Sampling rate (0.0-1.0)
)
```

### Advanced Configuration

```python
# Production configuration with sampling
ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=[
        "/health",
        "/metrics",
        "/_profilis",  # Built-in dashboard
        "/static",     # Static assets
        "/admin"       # Admin routes
    ],
    sample=0.1  # 10% sampling in production
)
```

## What Gets Profiled

### Request Events (REQ)
Each HTTP request generates a `REQ` event with:

```json
{
  "ts_ns": 1703123456789000000,
  "trace_id": "trace-abc123",
  "span_id": "span-def456",
  "kind": "REQ",
  "route": "/api/users",
  "status": 200,
  "dur_ns": 15000000,
  "bytes_in": 1024,
  "bytes_out": 2048
}
```

**Fields:**
- **`ts_ns`**: Timestamp in nanoseconds
- **`trace_id`**: Unique trace identifier
- **`span_id`**: Unique span identifier
- **`route`**: Request route/path
- **`status`**: HTTP status code
- **`dur_ns`**: Request duration in nanoseconds
- **`bytes_in`**: Request body size (if available)
- **`bytes_out`**: Response body size (if available)

### Exception Events (REQ_META)
When exceptions occur, additional metadata is recorded:

```json
{
  "kind": "REQ_META",
  "ts_ns": 1703123456789000000,
  "trace_id": "trace-abc123",
  "span_id": "span-def456",
  "route": "/api/users",
  "exception_type": "ValueError",
  "exception_value": "Invalid user ID",
  "traceback": "..."
}
```

## Integration Patterns

### With Built-in Dashboard

```python
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

app = Flask(__name__)
stats = StatsStore()

# Setup Profilis profiling
ProfilisFlask(app, collector=collector)

# Add dashboard
ui_bp = make_ui_blueprint(stats, ui_prefix="/_profilis")
app.register_blueprint(ui_bp)

# Visit /_profilis for real-time metrics
```

### With Custom Exporters

```python
from profilis.exporters.console import ConsoleExporter
from profilis.exporters.jsonl import JSONLExporter

# Multiple exporters
console_exporter = ConsoleExporter(pretty=True)
jsonl_exporter = JSONLExporter(dir="./logs")

# Use JSONL for production, console for development
if app.debug:
    collector = AsyncCollector(console_exporter)
else:
    collector = AsyncCollector(jsonl_exporter)

profilis = ProfilisFlask(app, collector=collector)
```

### With Database Instrumentation

```python
from profilis.sqlalchemy.instrumentation import instrument_sqlalchemy

# Instrument SQLAlchemy
instrument_sqlalchemy(engine, collector)

# Flask adapter will automatically correlate request and database events
profilis = ProfilisFlask(app, collector=collector)
```

## Performance Considerations

### Sampling Strategies

```python
# Development: 100% sampling
profilis = ProfilisFlask(app, collector=collector, sample=1.0)

# Staging: 50% sampling
profilis = ProfilisFlask(app, collector=collector, sample=0.5)

# Production: 10% sampling
profilis = ProfilisFlask(app, collector=collector, sample=0.1)

# Critical endpoints: Always profile
profilis = ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics"],
    sample=1.0  # 100% for critical paths
)
```

### Route Exclusion

```python
# Exclude monitoring and static routes
exclude_routes = [
    "/health",           # Health checks
    "/metrics",          # Metrics endpoints
    "/_profilis",        # Built-in dashboard
    "/static",           # Static assets
    "/admin",            # Admin interface
    "/favicon.ico"       # Browser requests
]

profilis = ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=exclude_routes
)
```

## Error Handling

### Exception Tracking

The Flask adapter automatically captures exceptions:

```python
@app.route('/api/users/<user_id>')
def get_user(user_id):
    try:
        user = database.get_user(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        return user
    except ValueError as e:
        # This exception will be automatically recorded
        raise
    except Exception as e:
        # All exceptions are captured
        app.logger.error(f"Unexpected error: {e}")
        raise
```

### Custom Error Handling

```python
from profilis.core.emitter import Emitter

@app.errorhandler(404)
def not_found(error):
    # Custom error handling with profiling
    emitter = Emitter(collector)
    emitter.emit_req(request.path, 404, dur_ns=0)
    return {"error": "Not found"}, 404
```

## Testing

### Unit Testing

```python
import pytest
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.exporters.console import ConsoleExporter

@pytest.fixture
def app():
    app = Flask(__name__)

    # Use console exporter for testing
    exporter = ConsoleExporter(pretty=False)
    collector = AsyncCollector(exporter, queue_size=128, flush_interval=0.01)

    profilis = ProfilisFlask(app, collector=collector)
    return app

def test_user_endpoint(app, client):
    response = client.get('/api/users')
    assert response.status_code == 200
```

### Integration Testing

```python
def test_profiling_integration(app, client):
    # Make requests
    client.get('/api/users')
    client.get('/api/users/1')

    # Verify profiling data
    # (Implementation depends on your testing strategy)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're using `profilis.flask.adapter.ProfilisFlask`
2. **Missing Collector**: Always provide an AsyncCollector instance
3. **Route Conflicts**: Check for conflicts with built-in dashboard routes
4. **Performance Impact**: Use sampling in production to reduce overhead

### Debug Mode

```python
import os
os.environ['PROFILIS_DEBUG'] = '1'

# This will enable debug logging
profilis = ProfilisFlask(app, collector=collector)
```

### Health Checks

```python
@app.route('/_profilis/health')
def profilis_health():
    """Check Profilis collector health"""
    return {
        "collector": {
            "queue_size": collector.queue.qsize(),
            "queue_max": collector.queue.maxsize,
            "dropped_events": getattr(collector, 'dropped_events', 0)
        }
    }
```

## Migration from v0.0.x

If you're upgrading from an earlier version:

```python
# Old import (v0.0.x)
# from profilis.integrations.flask_ext import ProfilisFlask

# New import (v0.1.0)
from profilis.flask.adapter import ProfilisFlask

# Old configuration
# sg = ProfilisFlask(app, ui_enabled=True, ui_prefix="/_profilis")

# New configuration
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
profilis = ProfilisFlask(app, collector=collector)

# Add UI separately if needed
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

stats = StatsStore()
ui_bp = make_ui_blueprint(stats, ui_prefix="/_profilis")
app.register_blueprint(ui_bp)
```
