"""Built-in UI: JSON endpoints + HTML dashboard (Sanic).

- /metrics.json -> StatsStore snapshot
- /errors.json -> recent error ring (last N)
- / -> HTML dashboard with KPIs + sparkline, theme toggle, recent errors table
- Supports bearer token auth (optional), saves token from `?token` to localStorage
- Configurable ui_prefix (mounted via Sanic Blueprint)

Uses shared UI from profilis.ui (ErrorItem, record_error, DASHBOARD_HTML).
"""

from __future__ import annotations

from typing import Any

from sanic import Blueprint
from sanic.request import Request
from sanic.response import HTTPResponse, text
from sanic.response import json as sanic_json

from profilis.core.stats import StatsStore
from profilis.ui import DASHBOARD_HTML, get_error_ring, record_error
from profilis.ui._core import ErrorItem

__all__ = ["ErrorItem", "make_ui_blueprint", "record_error"]


def make_ui_blueprint(
    stats: StatsStore, *, bearer_token: str | None = None, ui_prefix: str = ""
) -> Blueprint:
    """Create a Sanic Blueprint that serves the Profilis dashboard and JSON endpoints.

    Usage:
        stats = StatsStore()
        bp = make_ui_blueprint(stats, ui_prefix="/profilis")
        app.blueprint(bp)
    """
    bp = Blueprint("profilis_ui", url_prefix=ui_prefix)

    def _check_auth(request: Request) -> HTTPResponse | None:
        if bearer_token is None:
            return None
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return text("Unauthorized", status=401)
        token = auth.split(" ", 1)[1]
        if token != bearer_token:
            return text("Unauthorized", status=401)
        return None

    def _jsonify(data: dict[str, Any]) -> HTTPResponse:
        return sanic_json(data)

    @bp.get("/metrics.json")  # type: ignore[untyped-decorator]
    async def metrics_json(request: Request) -> HTTPResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        return _jsonify(stats.snapshot())

    @bp.get("/errors.json")  # type: ignore[untyped-decorator]
    async def errors_json(request: Request) -> HTTPResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        ring = get_error_ring()
        empty_list: list[dict[str, str | int | None]] = []
        payload = {"errors": ring.dump() if ring else empty_list}
        return _jsonify(payload)

    @bp.get("/")  # type: ignore[untyped-decorator]
    async def dashboard(request: Request) -> HTTPResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        return HTTPResponse(DASHBOARD_HTML, content_type="text/html; charset=utf-8")

    return bp
