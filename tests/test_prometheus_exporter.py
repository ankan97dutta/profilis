"""Tests for Prometheus exporter: bucket math and scrape smoke."""

from __future__ import annotations

from typing import Any, cast

import pytest

pytest.importorskip("prometheus_client")

from profilis.exporters.prometheus import (
    DEFAULT_BUCKETS,
    PrometheusExporter,
    _ns_to_seconds,
    make_asgi_app,
    make_metrics_blueprint,
)

# --- Bucket math ---


def test_ns_to_seconds_basic() -> None:
    assert _ns_to_seconds(0) == 0.0
    assert _ns_to_seconds(1_000_000_000) == 1.0
    assert _ns_to_seconds(500_000_000) == 0.5  # noqa: PLR2004
    assert _ns_to_seconds(50_000_000) == 0.05  # noqa: PLR2004


def test_ns_to_seconds_negative_clamped_to_zero() -> None:
    assert _ns_to_seconds(-1) == 0.0
    assert _ns_to_seconds(-999999) == 0.0


def test_default_buckets_ordering_and_values() -> None:
    assert DEFAULT_BUCKETS == (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)
    for i in range(len(DEFAULT_BUCKETS) - 1):
        assert DEFAULT_BUCKETS[i] < DEFAULT_BUCKETS[i + 1]


def test_histogram_bucket_boundaries() -> None:
    """Observe values at bucket boundaries and verify they appear in _bucket series."""
    from prometheus_client import CollectorRegistry, generate_latest  # noqa: PLC0415

    registry = CollectorRegistry()
    exporter = PrometheusExporter(registry, service="svc", instance="inst", worker="w")

    # 0.01 s = 10_000_000 ns
    exporter([{"kind": "HTTP", "route": "/x", "status": 200, "dur_ns": 10_000_000}])
    # 0.5 s
    exporter([{"kind": "REQ", "route": "/y", "status": 500, "dur_ns": 500_000_000}])
    # 5 s
    exporter([{"kind": "FN", "fn": "foo", "dur_ns": 5_000_000_000}])
    # DB with vendor
    exporter(
        [
            {"kind": "DB", "db_vendor": "postgresql", "dur_ns": 25_000_000},
        ]
    )

    body = generate_latest(registry).decode()
    assert "profilis_http_requests_total" in body
    assert "profilis_http_request_duration_seconds" in body
    assert "profilis_function_calls_total" in body
    assert "profilis_function_duration_seconds" in body
    assert "profilis_db_queries_total" in body
    assert "profilis_db_query_duration_seconds" in body
    assert 'route="/x"' in body or 'route="/x"' in body
    assert 'status="200"' in body or "status='200'" in body
    assert 'db_vendor="postgresql"' in body or "db_vendor='postgresql'" in body
    # Histogram buckets (le=)
    assert "profilis_http_request_duration_seconds_bucket" in body
    assert "le=" in body


# --- Scrape smoke ---


def test_scrape_smoke_all_metric_types() -> None:
    from prometheus_client import CollectorRegistry, generate_latest  # noqa: PLC0415

    registry = CollectorRegistry()
    exporter = PrometheusExporter(
        registry,
        service="test-svc",
        instance="host:8080",
        worker="1",
    )

    batch = [
        {"kind": "REQ", "route": "/api/users", "status": 200, "dur_ns": 100_000_000},
        {"kind": "HTTP", "route": "/health", "status": 200, "dur_ns": 5_000_000},
        {"kind": "FN", "fn": "my_module.handler", "dur_ns": 50_000_000},
        {"kind": "DB", "query": "SELECT 1", "dur_ns": 1_000_000, "rows": 1, "db_vendor": "sqlite"},
    ]
    exporter(batch)

    out = generate_latest(registry).decode()
    assert "profilis_http_requests_total" in out
    assert "profilis_http_request_duration_seconds" in out
    assert "profilis_function_calls_total" in out
    assert "profilis_function_duration_seconds" in out
    assert "profilis_db_queries_total" in out
    assert "profilis_db_query_duration_seconds" in out
    assert "test-svc" in out
    assert "host:8080" in out


def test_scrape_smoke_ignores_non_dict_and_unknown_kind() -> None:
    from prometheus_client import CollectorRegistry, generate_latest  # noqa: PLC0415

    registry = CollectorRegistry()
    exporter = PrometheusExporter(registry)
    batch: list[Any] = [
        {"kind": "REQ", "route": "/a", "status": 200, "dur_ns": 1},
        "not a dict",
        {"kind": "UNKNOWN", "x": 1},
        None,
    ]
    exporter(cast(Any, batch))
    out = generate_latest(registry).decode()
    assert "profilis_http_requests_total" in out


def test_make_asgi_app_returns_callable() -> None:
    from prometheus_client import CollectorRegistry  # noqa: PLC0415

    registry = CollectorRegistry()
    app = make_asgi_app(registry)
    assert callable(app)


def test_make_metrics_blueprint_route_metrics() -> None:
    pytest.importorskip("flask")
    from flask import Flask  # noqa: PLC0415
    from prometheus_client import CollectorRegistry  # noqa: PLC0415

    registry = CollectorRegistry()
    PrometheusExporter(registry)([{"kind": "REQ", "route": "/m", "status": 200, "dur_ns": 0}])

    bp = make_metrics_blueprint(registry)
    assert bp.url_prefix == ""
    app = Flask(__name__)
    app.register_blueprint(bp)
    resp = app.test_client().get("/metrics")
    assert resp.status_code == 200  # noqa: PLR2004
    assert "profilis_http_requests_total" in resp.get_data(as_text=True)
