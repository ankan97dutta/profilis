"""ASGI middleware for Starlette (and other ASGI frameworks) that records HTTP metrics.

Features:
- Intercepts 'http' scopes only (skips websocket)
- Resolves route path from scope['route'].path_format when available
- Captures method, path/route, status, latency (ns), exception type when present
- Uses profilis runtime context to allow trace/span propagation
- Configurable sampling, route excludes, always-sample-errors
"""

from __future__ import annotations

import contextlib
import traceback
import typing as t
from dataclasses import dataclass
from random import random

from profilis.core.emitter import Emitter
from profilis.runtime import get_current_parent_span_id, now_ns

if t.TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

# Constants
HTTP_ERROR_STATUS_THRESHOLD = 500
DEFAULT_ERROR_STATUS = 500


@dataclass
class RequestInfo:
    """Container for request information."""

    method: str
    path: str
    route: str | None
    status_code: int | None
    dur_ns: int
    error_info: dict[str, str] | None


class ASGIConfig:
    def __init__(
        self,
        *,
        sampling_rate: float = 1.0,
        route_excludes: t.Iterable[str] | None = None,
        always_sample_errors: bool = True,
    ) -> None:
        """
        sampling_rate: float in [0.0, 1.0] probability of capturing a request.
                       1.0 captures all; 0.0 captures none (except errors if always_sample_errors).
        route_excludes: iterable of route prefixes or exact strings to skip (e.g. '/static', '/health').
        always_sample_errors: if True, requests that raise exceptions or yield status >=500 are always recorded.
        """
        self.sampling_rate = float(sampling_rate)
        self.route_excludes = list(route_excludes or [])
        self.always_sample_errors = bool(always_sample_errors)


def _should_exclude_route(route: str, excludes: t.Iterable[str]) -> bool:
    if not excludes:
        return False
    for pat in excludes:
        if not pat:
            continue
        # prefix match first for convenience; also allow exact match
        if route.startswith(pat) or route == pat:
            return True
    return False


class ProfilisASGIMiddleware:
    """ASGI middleware that records HTTP request metrics and enqueues them via Emitter.

    Usage:
        app = Starlette()
        emitter = Emitter(AsyncCollector(...))
        middleware = ProfilisASGIMiddleware(app, emitter, ASGIConfig(...))
        app.add_middleware(middleware)  # or mount wrapper in frameworks
    """

    def __init__(self, app: ASGIApp, emitter: Emitter, config: ASGIConfig | None = None) -> None:
        self.app = app
        self.emitter = emitter
        self.cfg = config or ASGIConfig()

    def _extract_request_info(self, scope: Scope) -> tuple[str, str | None, str]:
        """Extract method, route, and path from ASGI scope."""
        method = scope.get("method", "UNKNOWN")
        route: str | None = None
        try:
            route_obj = scope.get("route")
            if route_obj is not None:
                route = getattr(route_obj, "path_format", None) or getattr(route_obj, "path", None)
        except Exception:
            route = None
        path: str = str(route or scope.get("path", "/"))
        return method, route, path

    def _should_sample_request(self) -> bool:
        """Determine if this request should be sampled."""
        return (
            (random() <= self.cfg.sampling_rate)
            if (0.0 < self.cfg.sampling_rate < 1.0)
            else (self.cfg.sampling_rate >= 1.0)
        )

    def _should_record_request(
        self, sampled: bool, status_code: int | None, error_info: dict[str, str] | None
    ) -> bool:
        """Determine if this request should be recorded."""
        sc = int(status_code or 0)
        is_error_status = sc >= HTTP_ERROR_STATUS_THRESHOLD
        return sampled or (
            self.cfg.always_sample_errors and (error_info is not None or is_error_status)
        )

    def _create_payload(
        self, req_info: RequestInfo
    ) -> dict[str, str | int | dict[str, str] | None]:
        """Create the payload for recording."""
        sc = int(req_info.status_code or 0)
        try:
            parent_span_id = get_current_parent_span_id()
        except Exception:
            parent_span_id = None

        return {
            "kind": "HTTP",
            "vendor": "http",
            "method": req_info.method,
            "path": req_info.path,
            "route": req_info.route,
            "status": sc,
            "dur_ns": req_info.dur_ns,
            "ts_ns": now_ns(),
            "error": req_info.error_info,
            "parent_span_id": parent_span_id,
        }

    def _emit_request_data(
        self, req_info: RequestInfo, payload: dict[str, str | int | dict[str, str] | None]
    ) -> None:
        """Emit request data using the emitter."""
        sc = int(req_info.status_code or 0)

        # Prefer a dedicated emit_http method if present
        try:
            emit_fn = getattr(self.emitter, "emit_http", None)
            if callable(emit_fn):
                try:
                    emit_fn(
                        method=req_info.method,
                        path=req_info.path,
                        status=sc,
                        dur_ns=req_info.dur_ns,
                    )
                except TypeError:
                    # older signature possibility - try positional
                    with contextlib.suppress(Exception):
                        emit_fn(req_info.path, dur_ns=req_info.dur_ns, status=sc)
        except Exception:
            # never bubble emitter errors
            pass

        # always enqueue meta payload as fallback / canonical representation
        with contextlib.suppress(Exception):
            self.emitter._collector.enqueue(payload)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Only handle http requests; pass through other scope types untouched
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        # Extract request information
        method, route, path = self._extract_request_info(scope)

        # Check if route should be excluded
        if _should_exclude_route(path, self.cfg.route_excludes):
            await self.app(scope, receive, send)
            return

        # Determine sampling
        sampled = self._should_sample_request()

        # Create send wrapper to capture status
        status_code: int | None = None

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message.get("type") == "http.response.start":
                status_code = int(message.get("status", 0))
            await send(message)

        start_ns = now_ns()
        error_info: dict[str, str] | None = None

        try:
            # Run the application
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # Capture exception details
            tb = traceback.format_exc()
            error_info = {"type": type(exc).__name__, "repr": repr(exc), "traceback": tb}
            status_code = DEFAULT_ERROR_STATUS
            raise
        finally:
            # Record the request if needed
            dur_ns = now_ns() - start_ns
            if self._should_record_request(sampled, status_code, error_info):
                req_info = RequestInfo(method, path, route, status_code, dur_ns, error_info)
                payload = self._create_payload(req_info)
                self._emit_request_data(req_info, payload)
