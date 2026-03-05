"""Built-in UI: JSON endpoint + HTML dashboard (Flask).

- /metrics.json -> StatsStore snapshot
- /errors.json -> recent error ring (last N)
- / -> HTML dashboard with KPIs + sparkline, theme toggle, recent errors table
- Supports bearer token auth (optional), saves token from `?token` to localStorage
- Configurable ui_enabled and ui_prefix

Uses shared UI from profilis.ui (ErrorItem, record_error, DASHBOARD_HTML).
"""

from __future__ import annotations

import json

from flask import Blueprint, Response, abort, request

from profilis.core.stats import StatsStore
from profilis.ui import DASHBOARD_HTML, get_error_ring, record_error
from profilis.ui._core import ErrorItem

__all__ = ["ErrorItem", "make_ui_blueprint", "record_error"]


def make_ui_blueprint(
    stats: StatsStore, *, bearer_token: str | None = None, ui_prefix: str = ""
) -> Blueprint:
    bp = Blueprint("profilis_ui", __name__, url_prefix=ui_prefix)

    def _check_auth() -> None:
        if bearer_token is None:
            return
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            abort(401)
        token = auth.split(" ", 1)[1]
        if token != bearer_token:
            abort(401)

    def _jsonify(
        data: dict[str, str | int | float | list[dict[str, str | int | None]] | None],
    ) -> Response:
        return Response(json.dumps(data), mimetype="application/json")

    @bp.route("/metrics.json")
    def metrics_json() -> Response:
        _check_auth()
        return _jsonify(stats.snapshot())

    @bp.route("/errors.json")
    def errors_json() -> Response:
        _check_auth()
        ring = get_error_ring()
        empty_list: list[dict[str, str | int | None]] = []
        return _jsonify({"errors": ring.dump() if ring else empty_list})

    @bp.route("/")
    def dashboard() -> Response:
        _check_auth()
        return Response(DASHBOARD_HTML, mimetype="text/html")

    return bp
