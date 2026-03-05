# Built-in UI Dashboard

Profilis includes a real-time dashboard for monitoring application performance, errors, and metrics.

## Quick Start

```python
from flask import Flask
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

app = Flask(__name__)
stats = StatsStore()  # 15-minute rolling window

# Mount the dashboard at /_profilis
ui_bp = make_ui_blueprint(stats, ui_prefix="/_profilis")
app.register_blueprint(ui_bp)

# Visit http://localhost:5000/_profilis for the dashboard
```

## Features

### Real-time Metrics
- **Request Latency**: P50, P95, P99 percentiles
- **Throughput**: Requests per second
- **Error Rates**: Error percentage by route
- **Response Times**: Distribution of response times

### Error Tracking
- **Recent Errors**: Last 100 errors with details
- **Exception Types**: Breakdown by exception class
- **Route Analysis**: Error rates per endpoint
- **Stack Traces**: Full error context when available

### Performance Monitoring
- **Database Queries**: Query performance metrics
- **Function Calls**: Profiled function timing
- **Resource Usage**: Memory and CPU utilization
- **Trend Analysis**: Performance over time

## Dashboard Components

### Main Dashboard
The primary dashboard provides an overview of application health:

```
┌─────────────────────────────────────────────────────────────┐
│                    Profilis Dashboard                      │
├─────────────────────────────────────────────────────────────┤
│  Requests/sec: 1,234  │  Avg Latency: 45ms  │  Errors: 2% │
├─────────────────────────────────────────────────────────────┤
│  [Latency Chart]        │  [Throughput Chart]              │
│  P50: 25ms             │  P95: 120ms                      │
│  P99: 250ms            │  P99.9: 500ms                    │
├─────────────────────────────────────────────────────────────┤
│  [Error Rate Chart]     │  [Route Performance]             │
│  Recent Errors: 5      │  Top Routes by Latency           │
└─────────────────────────────────────────────────────────────┘
```

### Metrics API
Programmatic access to dashboard data:

```python
# Get metrics as JSON
GET /_profilis/metrics.json

# Response format
{
  "requests": {
    "total": 1234,
    "errors": 25,
    "error_rate": 0.02,
    "latency": {
      "p50": 25000000,    # 25ms in nanoseconds
      "p95": 120000000,   # 120ms in nanoseconds
      "p99": 250000000    # 250ms in nanoseconds
    }
  },
  "routes": {
    "/api/users": {
      "count": 456,
      "errors": 5,
      "avg_latency": 30000000
    }
  },
  "errors": [
    {
      "ts_ns": 1703123456789000000,
      "route": "/api/users",
      "status": 500,
      "exception_type": "ValueError",
      "exception_value": "Invalid user ID"
    }
  ]
}
```

## Configuration

### Basic Setup

```python
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

# Create stats store
stats = StatsStore(
    window_minutes=15,      # Rolling window size
    max_errors=100          # Maximum errors to track
)

# Create UI blueprint
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis"  # URL prefix
)
```

### Advanced Configuration

```python
# Production configuration with authentication
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis",
    ui_auth_token="secret123",  # Bearer token authentication
    ui_title="Production Dashboard",
    ui_theme="dark"             # Dark theme
)

# Custom configuration
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/monitoring",
    ui_auth_token="prod-token-456",
    ui_title="MyApp Monitoring",
    ui_theme="light",
    ui_refresh_interval=5000    # 5 second refresh
)
```

### StatsStore Configuration

```python
# Configure stats collection
stats = StatsStore(
    window_minutes=30,          # 30-minute rolling window
    max_errors=500,             # Track up to 500 errors
    max_routes=1000,            # Track up to 1000 routes
    precision_ns=1000000        # 1ms precision
)
```

## Integration Patterns

### With Flask Adapter

```python
from flask import Flask
from profilis.flask.adapter import ProfilisFlask
from profilis.flask.ui import make_ui_blueprint
from profilis.core.stats import StatsStore

app = Flask(__name__)

# Setup Profilis profiling
exporter = JSONLExporter(dir="./logs")
collector = AsyncCollector(exporter)
profilis = ProfilisFlask(app, collector=collector)

# Add dashboard
stats = StatsStore()
ui_bp = make_ui_blueprint(stats, ui_prefix="/_profilis")
app.register_blueprint(ui_bp)

# Now both profiling and dashboard are available
```

### With FastAPI

```python
from fastapi import FastAPI
from profilis.fastapi.adapter import instrument_fastapi
from profilis.fastapi.ui import make_ui_router
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore

app = FastAPI()
stats = StatsStore()
# ... set up collector and emitter, then:
instrument_fastapi(app, emitter, route_excludes=["/profilis"])
app.include_router(make_ui_router(stats, prefix="/profilis"))
# Visit /profilis for the dashboard
```

### With Sanic

```python
from sanic import Sanic
from profilis.sanic.adapter import instrument_sanic_app, SanicConfig
from profilis.sanic.ui import make_ui_blueprint
from profilis.core.emitter import Emitter
from profilis.core.stats import StatsStore

app = Sanic("myapp")
stats = StatsStore()
# ... set up collector and emitter, then:
instrument_sanic_app(app, emitter, SanicConfig())
app.blueprint(make_ui_blueprint(stats, ui_prefix="/profilis"))
# Visit /profilis for the dashboard
```

### With Custom Stats

```python
from profilis.core.stats import StatsStore
from profilis.core.emitter import Emitter

# Custom stats collection
stats = StatsStore()
emitter = Emitter(collector)

# Record custom metrics
def record_custom_metric(name: str, value: float):
    stats.record_custom(name, value)

# Use in your application
@app.route('/api/process')
def process_data():
    start_time = time.time_ns()

    # Process data...
    result = expensive_operation()

    # Record custom metric
    duration = time.time_ns() - start_time
    record_custom_metric("process_duration", duration)

    return result
```

## Dashboard Features

### Real-time Updates
The dashboard automatically refreshes to show current metrics:

- **Auto-refresh**: Configurable refresh intervals
- **Live Updates**: Real-time metric updates
- **Historical Data**: Rolling window statistics
- **Trend Analysis**: Performance over time

### Interactive Charts
Visual representation of performance data:

- **Latency Distribution**: Histogram of response times
- **Throughput Trends**: Requests per second over time
- **Error Patterns**: Error rates and types
- **Route Performance**: Endpoint-specific metrics

### Error Analysis
Comprehensive error tracking and analysis:

- **Error Details**: Full exception information
- **Route Correlation**: Errors by endpoint
- **Time Analysis**: When errors occur
- **Pattern Recognition**: Common error types

## Security and Access Control

### Authentication

```python
# Enable bearer token authentication
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis",
    ui_auth_token="your-secret-token"
)

# Access with Authorization header
# Authorization: Bearer your-secret-token
```

### Access Control

```python
# Custom authentication middleware
from functools import wraps
from flask import request, abort

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token or token != 'Bearer your-token':
            abort(401)
        return f(*args, **kwargs)
    return decorated_function

# Apply to dashboard routes
@app.route('/_profilis')
@require_auth
def dashboard():
    return render_template('dashboard.html')
```

### Production Security

```python
# Production configuration
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis",
    ui_auth_token=os.environ.get('PROFILIS_TOKEN'),
    ui_https_only=True,
    ui_cors_origins=['https://yourdomain.com']
)
```

## Customization

### Custom Themes

```python
# Custom CSS styling
custom_css = """
.dashboard-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
}

.metric-card {
    border-radius: 10px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
"""

ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis",
    ui_custom_css=custom_css
)
```

### Custom Metrics

```python
# Extend StatsStore for custom metrics
class CustomStatsStore(StatsStore):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.custom_metrics = {}

    def record_custom(self, name: str, value: float):
        """Record custom metric"""
        if name not in self.custom_metrics:
            self.custom_metrics[name] = []

        self.custom_metrics[name].append({
            'ts_ns': time.time_ns(),
            'value': value
        })

    def get_custom_metrics(self):
        """Get custom metrics summary"""
        summary = {}
        for name, values in self.custom_metrics.items():
            if values:
                summary[name] = {
                    'count': len(values),
                    'avg': sum(v['value'] for v in values) / len(values),
                    'min': min(v['value'] for v in values),
                    'max': max(v['value'] for v in values)
                }
        return summary

# Use custom stats store
custom_stats = CustomStatsStore()
ui_bp = make_ui_blueprint(custom_stats, ui_prefix="/_profilis")
```

## Monitoring and Alerting

### Health Checks

```python
@app.route('/_profilis/health')
def dashboard_health():
    """Check dashboard health"""
    return {
        "status": "healthy",
        "stats_store": {
            "window_minutes": stats.window_minutes,
            "total_requests": stats.total_requests,
            "total_errors": stats.total_errors,
            "error_rate": stats.error_rate
        },
        "collector": {
            "queue_size": collector.queue.qsize(),
            "queue_max": collector.queue.maxsize
        }
    }
```

### Integration with External Monitoring

```python
# Prometheus metrics endpoint
@app.route('/_profilis/metrics')
def prometheus_metrics():
    """Prometheus-formatted metrics"""
    metrics = []

    # Request metrics
    metrics.append(f"profilis_requests_total {stats.total_requests}")
    metrics.append(f"profilis_errors_total {stats.total_errors}")
    metrics.append(f"profilis_error_rate {stats.error_rate}")

    # Latency metrics
    if stats.latency_percentiles:
        p50 = stats.latency_percentiles.get(50, 0)
        p95 = stats.latency_percentiles.get(95, 0)
        p99 = stats.latency_percentiles.get(99, 0)

        metrics.append(f"profilis_latency_p50 {p50}")
        metrics.append(f"profilis_latency_p95 {p95}")
        metrics.append(f"profilis_latency_p99 {p99}")

    return '\n'.join(metrics), 200, {'Content-Type': 'text/plain'}
```

## Troubleshooting

### Common Issues

1. **Dashboard Not Loading**: Check blueprint registration and routes
2. **No Data Displayed**: Verify StatsStore is receiving data
3. **Authentication Errors**: Check bearer token configuration
4. **Performance Issues**: Monitor dashboard refresh intervals

### Debug Mode

```python
import os
os.environ['PROFILIS_DEBUG'] = '1'

# This will enable debug logging for the dashboard
ui_bp = make_ui_blueprint(stats, ui_prefix="/_profilis")
```

### Performance Optimization

```python
# Optimize for high-traffic applications
stats = StatsStore(
    window_minutes=5,       # Shorter window for real-time updates
    max_errors=50,          # Limit error storage
    max_routes=100          # Limit route tracking
)

# Reduce refresh frequency
ui_bp = make_ui_blueprint(
    stats,
    ui_prefix="/_profilis",
    ui_refresh_interval=10000  # 10 second refresh
)
```

## Best Practices

1. **Use Appropriate Window Sizes**: Balance real-time updates with memory usage
2. **Implement Authentication**: Always secure dashboard access in production
3. **Monitor Dashboard Performance**: Watch for dashboard impact on application
4. **Regular Cleanup**: Monitor StatsStore memory usage
5. **Custom Metrics**: Extend with application-specific monitoring
6. **Integration**: Connect with existing monitoring infrastructure
