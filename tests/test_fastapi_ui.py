"""Tests for FastAPI UI router (shared UI from profilis.ui)."""

import time
from typing import Union

from fastapi import FastAPI
from fastapi.testclient import TestClient

from profilis.core.stats import StatsStore
from profilis.fastapi.ui import ErrorItem, make_ui_router, record_error

# HTTP status codes
HTTP_OK = 200
HTTP_UNAUTHORIZED = 401


def _mk_app(token: Union[str, None] = None) -> tuple[FastAPI, StatsStore]:
    app = FastAPI()
    stats = StatsStore()
    router = make_ui_router(stats, bearer_token=token, prefix="/profilis")
    app.include_router(router)
    return app, stats


def test_fastapi_ui_metrics_json_schema_and_snapshot() -> None:
    app, stats = _mk_app()
    client = TestClient(app)
    for i in range(10):
        stats.record(1000 * i, error=(i % 2 == 0))
    r = client.get("/profilis/metrics.json")
    assert r.status_code == HTTP_OK
    data = r.json()
    assert "rps" in data and "p50" in data and "spark" in data


def test_fastapi_ui_dashboard_rendering_smoke() -> None:
    app, _ = _mk_app()
    client = TestClient(app)
    # Dashboard is at prefix root: /profilis or /profilis/
    r = client.get("/profilis")
    assert r.status_code == HTTP_OK
    assert b"Profilis" in r.content


def test_fastapi_ui_auth_check_forbidden() -> None:
    app, _ = _mk_app(token="secret")
    client = TestClient(app)
    r = client.get("/profilis/metrics.json")
    assert r.status_code == HTTP_UNAUTHORIZED
    r2 = client.get("/profilis/metrics.json", headers={"Authorization": "Bearer secret"})
    assert r2.status_code == HTTP_OK


def test_fastapi_ui_errors_ring_endpoint() -> None:
    app, _ = _mk_app()
    record_error(
        ErrorItem(
            ts_ns=time.time_ns(),
            route="/boom",
            status=500,
            exception_type="RuntimeError",
            exception_value="Test error",
            traceback="Test traceback",
        )
    )
    client = TestClient(app)
    r = client.get("/profilis/errors.json")
    assert r.status_code == HTTP_OK
    data = r.json()
    assert "errors" in data and any(e["route"] == "/boom" for e in data["errors"])
