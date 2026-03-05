# Configuration

Profilis provides extensive configuration options for tuning performance, controlling data collection, and customizing behavior.

## Core Configuration

### AsyncCollector Settings

The `AsyncCollector` is the heart of Profilis's non-blocking architecture:

```python
from profilis.core.async_collector import AsyncCollector

collector = AsyncCollector(
    exporter,
    queue_size=2048,        # Maximum events in memory
    batch_max=128,          # Maximum events per batch
    flush_interval=0.1,     # Flush interval in seconds
    drop_oldest=True        # Drop events under backpressure
)
```

**Key Parameters:**
- **`queue_size`**: Maximum number of events that can be queued (default: 2048)
- **`batch_max`**: Maximum events per batch for efficient processing (default: 128)
- **`flush_interval`**: How often to flush events to exporters (default: 0.1s)
- **`drop_oldest`**: Whether to drop old events under backpressure (default: True)

### Performance Tuning

#### High-Throughput Configuration
```python
# For high-volume applications
collector = AsyncCollector(
    exporter,
    queue_size=8192,        # Large queue for high concurrency
    batch_max=256,          # Larger batches for efficiency
    flush_interval=0.05,    # More frequent flushing
    drop_oldest=True        # Drop events under backpressure
)
```

#### Low-Latency Configuration
```python
# For low-latency requirements
collector = AsyncCollector(
    exporter,
    queue_size=512,         # Smaller queue for lower latency
    batch_max=32,           # Smaller batches for faster processing
    flush_interval=0.01,    # Very frequent flushing
    drop_oldest=False       # Don't drop events
)
```

## Framework-Specific Configuration

### Flask Adapter

```python
from profilis.flask.adapter import ProfilisFlask

profilis = ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics", "/static"],  # Routes to ignore
    sample=0.1  # Sample 10% of requests
)
```

**Configuration Options:**
- **`collector`**: Required AsyncCollector instance
- **`exclude_routes`**: List of route prefixes to exclude from profiling
- **`sample`**: Sampling rate from 0.0 (0%) to 1.0 (100%)

### Route Exclusion Patterns

```python
# Exclude health and monitoring endpoints
exclude_routes = [
    "/health",
    "/metrics",
    "/_profilis",  # Built-in dashboard
    "/static",     # Static assets
    "/admin"       # Admin routes
]

profilis = ProfilisFlask(app, collector=collector, exclude_routes=exclude_routes)
```

## Sampling Configuration

### Random Sampling
```python
# Sample 5% of requests in production
profilis = ProfilisFlask(app, collector=collector, sample=0.05)

# Sample 100% in development
profilis = ProfilisFlask(app, collector=collector, sample=1.0)
```

### Route-Based Sampling
```python
# Different sampling rates for different route patterns
profilis = ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics"],  # Always exclude
    sample=0.1  # 10% sampling for all other routes
)
```

### ASGI / Sanic sampling (FastAPI, Starlette, Sanic)

When using `ASGIConfig` (FastAPI/Starlette) or `SanicConfig` (Sanic), you get:

- **Global `sampling_rate`** — Float in `[0.0, 1.0]`. `1.0` = capture all requests; `0.0` = capture none (except 5xx when `always_sample_errors=True`). Values outside this range raise `ValueError`.
- **Route excludes** — Paths to skip entirely (prefix or exact match). Use the `re:` prefix for regex (e.g. `"re:^/v[12]/"` to exclude `/v1/` and `/v2/`).
- **Per-route overrides** — `route_overrides`: iterable of `(pattern, rate)`. First matching pattern wins. Use prefix or `re:...` for regex. Example: sample 100% of `/api/critical` while keeping 10% elsewhere.
- **Always sample 5xx** — With `always_sample_errors=True` (default), responses with status ≥ 500 and requests that raise exceptions are always recorded, regardless of `sampling_rate`.
- **Deterministic tests** — Pass `random_seed=int` for reproducible sampling, or `rng=callable` that returns a float in `[0, 1)`.

```python
from profilis.asgi.middleware import ASGIConfig

# Production: 10% global sampling, exclude health/dashboard, always record 5xx
config = ASGIConfig(
    sampling_rate=0.1,
    route_excludes=["/health", "/profilis", "re:^/static/"],
    route_overrides=[("/api/critical", 1.0), ("/api/", 0.05)],
    always_sample_errors=True,
)

# Tests: deterministic sampling
config_test = ASGIConfig(sampling_rate=0.5, always_sample_errors=True, random_seed=42)
```

## Exporter Configuration

### JSONL Exporter

```python
from profilis.exporters.jsonl import JSONLExporter

exporter = JSONLExporter(
    dir="./logs",                    # Output directory
    rotate_bytes=1024*1024,         # Rotate at 1MB
    rotate_secs=3600,               # Rotate every hour
    filename_template="profilis-{timestamp}.jsonl"
)
```

**Rotation Options:**
- **`rotate_bytes`**: Rotate when file reaches this size
- **`rotate_secs`**: Rotate after this many seconds
- **`dir`**: Output directory for log files
- **`filename_template`**: Custom filename pattern

### Console Exporter

```python
from profilis.exporters.console import ConsoleExporter

# Pretty-printed output for development
exporter = ConsoleExporter(pretty=True)

# Compact output for production
exporter = ConsoleExporter(pretty=False)
```

## Environment Variables

Configure Profilis behavior through environment variables:

```bash
# Enable debug mode
export PROFILIS_DEBUG=1

# Set default log directory
export PROFILIS_LOG_DIR=/var/log/profilis

# Configure sampling rate (0.0 to 1.0)
export PROFILIS_SAMPLE_RATE=0.1

# Set queue size
export PROFILIS_QUEUE_SIZE=4096

# Set batch size
export PROFILIS_BATCH_MAX=256

# Set flush interval
export PROFILIS_FLUSH_INTERVAL=0.05
```

## Runtime Context Configuration

### Trace and Span Management

```python
from profilis.runtime import use_span, span_id, get_trace_id, get_span_id

# Create distributed trace context
with use_span(trace_id="trace-123", span_id="span-456"):
    current_trace = get_trace_id()  # "trace-123"
    current_span = get_span_id()    # "span-456"

    # Nested spans inherit trace context
    with use_span(span_id="span-789"):
        nested_span = get_span_id()  # "span-789"
        parent_trace = get_trace_id() # "trace-123"
```

## Dashboard Configuration

### UI Blueprint Settings

```python
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

# Configure stats store
stats = StatsStore(
    window_minutes=15,      # Rolling window size
    max_errors=100          # Maximum errors to track
)

# Mount dashboard with custom settings
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis",     # URL prefix
    ui_auth_token="secret123"   # Optional authentication
)
app.register_blueprint(ui_bp)
```

## Production Configuration

### Recommended Production Settings

```python
# Production-ready configuration
exporter = JSONLExporter(
    dir="/var/log/profilis",
    rotate_bytes=100*1024*1024,  # 100MB files
    rotate_secs=86400            # Daily rotation
)

collector = AsyncCollector(
    exporter,
    queue_size=4096,        # Larger queue for production
    batch_max=256,          # Larger batches
    flush_interval=0.1,     # 100ms flush interval
    drop_oldest=True        # Drop under pressure
)

profilis = ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/health", "/metrics", "/_profilis"],
    sample=0.1              # 10% sampling in production
)
```

### Monitoring and Alerting

```python
# Add custom monitoring
import logging

logger = logging.getLogger(__name__)

def monitor_collector(collector):
    """Monitor collector health"""
    if collector.queue_size > collector.queue.maxsize * 0.8:
        logger.warning("Collector queue is 80% full")

    if collector.dropped_events > 0:
        logger.error(f"Collector dropped {collector.dropped_events} events")
```

## Configuration Validation

Profilis validates configuration at runtime:

```python
# Invalid sampling rate will raise ValueError
try:
    profilis = ProfilisFlask(app, collector=collector, sample=1.5)
except ValueError as e:
    print(f"Invalid configuration: {e}")

# Invalid queue size will raise ValueError
try:
    collector = AsyncCollector(exporter, queue_size=0)
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

## Best Practices

1. **Start Conservative**: Begin with default settings and tune based on your needs
2. **Monitor Queue Size**: Watch for queue backpressure in production
3. **Use Sampling in Production**: Start with 10% sampling and adjust based on volume
4. **Exclude Health Endpoints**: Always exclude monitoring endpoints from profiling
5. **Configure Log Rotation**: Set appropriate rotation policies for your log storage
6. **Test Performance Impact**: Measure overhead in your specific environment
