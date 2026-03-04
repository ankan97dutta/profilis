"""Thin FastAPI adapter on top of the ASGI middleware.

This module provides a convenience function `instrument_fastapi` which registers
the ProfilisASGIMiddleware with a FastAPI app and ensures route templates are
captured reliably (APIRouter, mounted apps, dependencies). It intentionally
does not re-implement timing logic — it delegates to ProfilisASGIMiddleware.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from fastapi import FastAPI

from profilis.asgi.middleware import ASGIConfig, ProfilisASGIMiddleware
from profilis.core.emitter import Emitter

if TYPE_CHECKING:
    from starlette.types import Receive, Scope, Send


def instrument_fastapi(
    app: FastAPI,
    emitter: Emitter,
    config: ASGIConfig | None = None,
    *,
    route_excludes: Iterable[str] | None = None,
) -> None:
    """
    Instrument a FastAPI app with Profilis ASGI middleware.

    - Registers ProfilisASGIMiddleware as outer middleware so it observes the final
      Starlette/FastAPI response lifecycle (captures http.response.start).
    - Accepts optional route_excludes to skip recording certain paths (e.g., mounted UI).
    - Works with APIRouter, dependency-injected endpoints, background tasks, and streaming responses.
    """
    cfg = config or ASGIConfig()
    # merge excludes if provided
    if route_excludes:
        cfg.route_excludes = list(cfg.route_excludes or []) + list(route_excludes)

    # FastAPI/Starlette expects middleware to be classes or callables; ProfilisASGIMiddleware is ASGI-compatible.
    # We add it as "first" middleware so it wraps all sub-apps / mounted apps.
    # FastAPI.app is a Starlette app under the hood; use add_middleware to integrate cleanly.
    try:
        # FastAPI supports add_middleware with a middleware factory/class and kwargs
        app.add_middleware(ProfilisASGIMiddleware, emitter=emitter, config=cfg)
    except Exception:
        # fallback: directly wrap the app's asgi_app (non-invasive)
        # store original app so tests can still access it
        # original = app.__call__  # unused variable removed
        middleware = ProfilisASGIMiddleware(app, emitter, cfg)

        async def wrapped_scope(scope: Scope, receive: Receive, send: Send) -> None:
            await middleware(scope, receive, send)

        app.__call__ = wrapped_scope  # type: ignore
