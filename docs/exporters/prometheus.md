# Prometheus Exporter

The Prometheus exporter exposes profiling events as Prometheus metrics: counters and histograms for HTTP requests, function calls, and database queries. Optionally, collector health metrics (queue depth, events dropped) can be registered for the same registry.

## Installation

```bash
pip install profilis[prometheus]
```

## Metrics

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `profilis_http_requests_total` | Counter | service, instance, worker, route, status | Total HTTP requests |
| `profilis_http_request_duration_seconds` | Histogram | service, instance, worker, route, status | HTTP request duration |
| `profilis_function_calls_total` | Counter | service, instance, worker, function | Total function calls (decorated) |
| `profilis_function_duration_seconds` | Histogram | service, instance, worker, function | Function call duration |
| `profilis_db_queries_total` | Counter | service, instance, worker, db_vendor | Total DB queries |
| `profilis_db_query_duration_seconds` | Histogram | service, instance, worker, db_vendor | DB query duration |
| `profilis_events_dropped_total` | Counter | — | Events dropped (queue full; optional health) |
| `profilis_queue_depth` | Gauge | — | Current collector buffer size (optional health) |

Default histogram buckets (seconds): `[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10]`. You can override them when creating the exporter.

## Quick Start (ASGI / FastAPI)

```python
from prometheus_client import CollectorRegistry
from profilis.exporters.prometheus import (
    PrometheusExporter,
    make_asgi_app,
    register_collector_health_metrics,
)
from profilis.core.async_collector import AsyncCollector

registry = CollectorRegistry()
prom = PrometheusExporter(registry, service="myapp")
collector = AsyncCollector(prom, queue_size=2048, batch_max=128)
register_collector_health_metrics(registry, collector)

# Wire collector into your app (e.g. instrument_fastapi with same collector)
# Then expose /metrics:
app.mount("/metrics", make_asgi_app(registry))
```

## Quick Start (Flask)

```python
from prometheus_client import CollectorRegistry
from profilis.exporters.prometheus import (
    PrometheusExporter,
    make_metrics_blueprint,
    register_collector_health_metrics,
)
from profilis.core.async_collector import AsyncCollector

registry = CollectorRegistry()
prom = PrometheusExporter(registry, service="myapp")
collector = AsyncCollector(prom, queue_size=2048, batch_max=128)
register_collector_health_metrics(registry, collector)

# Wire collector into ProfilisFlask(app, collector=collector, ...)
app.register_blueprint(make_metrics_blueprint(registry))  # GET /metrics
# Or with prefix: make_metrics_blueprint(registry, url_prefix="/custom")
```

## Configuration

- **PrometheusExporter(registry, service="", instance="", worker="", buckets=DEFAULT_BUCKETS)**
  Use a dedicated `CollectorRegistry()` so scrapes only see Profilis metrics. Set `service`, `instance`, `worker` for label values.

- **register_collector_health_metrics(registry, collector)**
  Registers `profilis_events_dropped_total` and `profilis_queue_depth` for the given `AsyncCollector`. Call after creating the collector and use the same registry as the exporter.

- **make_asgi_app(registry)**
  Returns an ASGI app that serves `GET /metrics` in Prometheus text format. Mount at `/metrics` (or another path).

- **make_metrics_blueprint(registry, url_prefix="")**
  Returns a Flask blueprint that serves `GET /metrics`. Register with `app.register_blueprint(...)`.

## Composing with Other Exporters

You can use the Prometheus exporter alongside JSONL or console by using a sink that fans out to multiple exporters:

```python
def sink(batch):
    jsonl_exporter(batch)  # or your JSONL writer
    prom(batch)

collector = AsyncCollector(sink, queue_size=2048, batch_max=128)
```

## See Also

- [JSONL Exporter](jsonl.md) — Rotating log files
- [Configuration](../guides/configuration.md) — Sampling and route exclusions
- [Architecture](../architecture/architecture.md) — System overview
