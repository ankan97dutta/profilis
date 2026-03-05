"""Built-in UI: JSON endpoints + HTML dashboard (FastAPI).

- /metrics.json -> StatsStore snapshot
- /errors.json -> recent error ring (last N)
- / -> HTML dashboard with KPIs + sparkline, theme toggle, recent errors table
- Supports bearer token auth (optional), saves token from `?token` to localStorage
- Configurable prefix when including the router

Uses shared UI from profilis.ui (ErrorItem, record_error, DASHBOARD_HTML).
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from profilis.core.stats import StatsStore
from profilis.ui import DASHBOARD_HTML, get_error_ring, record_error
from profilis.ui._core import ErrorItem

__all__ = ["ErrorItem", "make_ui_router", "record_error"]


def make_ui_router(
    stats: StatsStore, *, bearer_token: str | None = None, prefix: str = ""
) -> APIRouter:
    """Create a FastAPI APIRouter that serves the Profilis dashboard and JSON endpoints.

    Usage:
        stats = StatsStore()
        router = make_ui_router(stats, prefix="/profilis")
        app.include_router(router)
    """
    router = APIRouter(prefix=prefix)

    def _check_auth(request: Request) -> PlainTextResponse | None:
        if bearer_token is None:
            return None
        auth = request.headers.get("authorization") or request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return PlainTextResponse("Unauthorized", status_code=401)
        token = auth.split(" ", 1)[1]
        if token != bearer_token:
            return PlainTextResponse("Unauthorized", status_code=401)
        return None

    @router.get("/metrics.json", response_model=None)
    def metrics_json(request: Request) -> JSONResponse | PlainTextResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        return JSONResponse(content=stats.snapshot())

    @router.get("/errors.json", response_model=None)
    def errors_json(request: Request) -> JSONResponse | PlainTextResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        ring = get_error_ring()
        empty_list: list[dict[str, str | int | None]] = []
        payload = {"errors": ring.dump() if ring else empty_list}
        return JSONResponse(content=payload)

    @router.get("/", response_model=None)
    def dashboard(request: Request) -> HTMLResponse | PlainTextResponse:
        auth_resp = _check_auth(request)
        if auth_resp is not None:
            return auth_resp
        return HTMLResponse(content=DASHBOARD_HTML)

    return router
