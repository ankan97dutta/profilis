"""Prometheus exporter: counters and histograms for HTTP, functions, and DB.

Metrics:
- HTTP: profilis_http_requests_total, profilis_http_request_duration_seconds
- Functions: profilis_function_calls_total, profilis_function_duration_seconds
- DB: profilis_db_queries_total, profilis_db_query_duration_seconds
- Collector health (optional): profilis_events_dropped_total, profilis_queue_depth
  Use register_collector_health_metrics(registry, collector) to expose them.

Labels: service, instance, worker, route, status (HTTP), function (FN), db_vendor (DB).
Buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10] seconds.

Use as an AsyncCollector sink; optionally compose with other sinks:
  registry = CollectorRegistry()
  prom = PrometheusExporter(registry, service="myapp")
  def sink(batch):
      console_exporter(batch)
      prom(batch)
  collector = AsyncCollector(sink, ...)
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable
from typing import Any

try:
    from prometheus_client import CollectorRegistry, Counter, Histogram
    from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
except ImportError:  # pragma: no cover
    CollectorRegistry = None  # type: ignore[misc, assignment]
    Counter = None  # type: ignore[misc, assignment]
    Histogram = None  # type: ignore[misc, assignment]
    CounterMetricFamily = None  # type: ignore[misc, assignment]
    GaugeMetricFamily = None  # type: ignore[misc, assignment]

__all__ = [
    "DEFAULT_BUCKETS",
    "PrometheusExporter",
    "make_asgi_app",
    "make_metrics_blueprint",
    "register_collector_health_metrics",
]

# Histogram buckets in seconds (issue #17)
DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)


def _ns_to_seconds(dur_ns: int) -> float:
    """Convert nanosecond duration to seconds for Prometheus."""
    return max(0.0, dur_ns / 1e9)


def _str(s: Any) -> str:
    """Coerce value to string for label; empty or missing -> placeholder."""
    if s is None:
        return ""
    return str(s).strip() or "-"


def _ensure_prometheus() -> None:
    if CollectorRegistry is None or Counter is None or Histogram is None:
        raise ImportError(
            "prometheus_client is required for Prometheus exporter. "
            "Install with: pip install profilis[prometheus]"
        )


class PrometheusExporter:
    """Sink that updates Prometheus counters and histograms from REQ/HTTP/FN/DB events."""

    def __init__(
        self,
        registry: Any = None,
        *,
        service: str = "",
        instance: str = "",
        worker: str = "",
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> None:
        _ensure_prometheus()
        self._registry = registry if registry is not None else CollectorRegistry()
        self._service = _str(service)
        self._instance = _str(instance)
        self._worker = _str(worker)
        self._buckets = buckets

        # HTTP
        self._http_requests_total = Counter(
            "profilis_http_requests_total",
            "Total HTTP requests",
            ("service", "instance", "worker", "route", "status"),
            registry=self._registry,
        )
        self._http_request_duration_seconds = Histogram(
            "profilis_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ("service", "instance", "worker", "route", "status"),
            buckets=list(self._buckets),
            registry=self._registry,
        )

        # Functions
        self._function_calls_total = Counter(
            "profilis_function_calls_total",
            "Total function calls",
            ("service", "instance", "worker", "function"),
            registry=self._registry,
        )
        self._function_duration_seconds = Histogram(
            "profilis_function_duration_seconds",
            "Function call duration in seconds",
            ("service", "instance", "worker", "function"),
            buckets=list(self._buckets),
            registry=self._registry,
        )

        # DB
        self._db_queries_total = Counter(
            "profilis_db_queries_total",
            "Total DB queries",
            ("service", "instance", "worker", "db_vendor"),
            registry=self._registry,
        )
        self._db_query_duration_seconds = Histogram(
            "profilis_db_query_duration_seconds",
            "DB query duration in seconds",
            ("service", "instance", "worker", "db_vendor"),
            buckets=list(self._buckets),
            registry=self._registry,
        )

    @property
    def registry(self) -> Any:
        return self._registry

    def _labels_http(self, route: str, status: int) -> tuple[str, str, str, str, str]:
        return (
            self._service,
            self._instance,
            self._worker,
            _str(route) or "-",
            _str(status),
        )

    def _labels_fn(self, function: str) -> tuple[str, str, str, str]:
        return (self._service, self._instance, self._worker, _str(function) or "-")

    def _labels_db(self, db_vendor: str) -> tuple[str, str, str, str]:
        return (self._service, self._instance, self._worker, _str(db_vendor) or "unknown")

    def _process_event(self, ev: dict[str, Any]) -> None:
        kind = ev.get("kind")
        if kind in ("REQ", "HTTP"):
            route = ev.get("route") or ev.get("path") or "-"
            status = int(ev.get("status", 0))
            dur_ns = int(ev.get("dur_ns", 0))
            lbl_http = self._labels_http(route, status)
            self._http_requests_total.labels(*lbl_http).inc()
            self._http_request_duration_seconds.labels(*lbl_http).observe(_ns_to_seconds(dur_ns))
        elif kind == "FN":
            fn = ev.get("fn", "-")
            dur_ns = int(ev.get("dur_ns", 0))
            lbl_fn = self._labels_fn(fn)
            self._function_calls_total.labels(*lbl_fn).inc()
            self._function_duration_seconds.labels(*lbl_fn).observe(_ns_to_seconds(dur_ns))
        elif kind == "DB":
            db_vendor = ev.get("db_vendor") or "unknown"
            dur_ns = int(ev.get("dur_ns", 0))
            lbl_db = self._labels_db(db_vendor)
            self._db_queries_total.labels(*lbl_db).inc()
            self._db_query_duration_seconds.labels(*lbl_db).observe(_ns_to_seconds(dur_ns))

    def __call__(self, batch: Iterable[dict[str, Any] | Any]) -> None:
        for ev in batch:
            if not isinstance(ev, dict):
                continue
            with contextlib.suppress(Exception):
                self._process_event(ev)


def register_collector_health_metrics(registry: Any, collector: Any) -> None:
    """Register health metrics for an AsyncCollector: profilis_events_dropped_total, profilis_queue_depth.

    Call after creating your AsyncCollector and pass the same registry used for PrometheusExporter:
      collector = AsyncCollector(sink, ...)
      register_collector_health_metrics(registry, collector)
    """
    _ensure_prometheus()
    if CounterMetricFamily is None or GaugeMetricFamily is None:
        raise ImportError(
            "prometheus_client is required for health metrics. "
            "Install with: pip install profilis[prometheus]"
        )

    class _CollectorHealthCollector:
        def __init__(self, col: Any) -> None:
            self._col = col

        def collect(self) -> Any:
            # Scrape-time values; collector must have queue_depth and dropped_oldest
            depth = self._col.queue_depth if hasattr(self._col, "queue_depth") else 0
            dropped = getattr(self._col, "dropped_oldest", 0)
            yield GaugeMetricFamily(
                "profilis_queue_depth",
                "Current number of events in the collector buffer",
                value=depth,
            )
            c = CounterMetricFamily(
                "profilis_events_dropped_total",
                "Total events dropped (queue full, drop-oldest)",
            )
            c.add_metric([], dropped)
            yield c

    registry.register(_CollectorHealthCollector(collector))


def make_asgi_app(registry: Any = None) -> Any:
    """Return an ASGI app that serves /metrics (Prometheus text format).

    Use with Starlette: app.mount("/metrics", make_asgi_app(registry))
    Or with FastAPI: app.mount("/metrics", make_asgi_app(registry))
    """
    _ensure_prometheus()
    try:
        from prometheus_client import make_asgi_app as _make_asgi_app  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        raise ImportError(
            "prometheus_client is required. Install with: pip install profilis[prometheus]"
        ) from None
    return _make_asgi_app(registry)


def make_metrics_blueprint(registry: Any = None, url_prefix: str = "") -> Any:
    """Return a Flask blueprint that serves GET /metrics (Prometheus text format).

    Usage:
      from profilis.exporters.prometheus import make_metrics_blueprint
      app.register_blueprint(make_metrics_blueprint(registry))  # route at /metrics
    """
    _ensure_prometheus()
    from flask import Blueprint, Response  # noqa: PLC0415

    try:
        from prometheus_client import CONTENT_TYPE_LATEST, generate_latest  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        raise ImportError(
            "prometheus_client is required. Install with: pip install profilis[prometheus]"
        ) from None

    bp = Blueprint("profilis_metrics", __name__, url_prefix=url_prefix)

    @bp.route("/metrics", methods=["GET"])
    def metrics() -> Response:
        reg = registry
        if reg is None:
            try:
                from prometheus_client import REGISTRY  # noqa: PLC0415

                reg = REGISTRY
            except ImportError:
                raise RuntimeError("No registry provided and REGISTRY not available") from None
        body = generate_latest(reg)
        return Response(body, mimetype=CONTENT_TYPE_LATEST)

    return bp
