"""ASGI middleware for Starlette (and other ASGI frameworks) that records HTTP metrics.

Features:
- Intercepts 'http' scopes only (skips websocket)
- Resolves route path from scope['route'].path_format when available
- Captures method, path/route, status, latency (ns), exception type when present
- Uses profilis runtime context to allow trace/span propagation
- Configurable sampling, route excludes (prefix/regex), per-route overrides, always-sample-errors (5xx)
"""

from __future__ import annotations

import contextlib
import traceback
import typing as t
from dataclasses import dataclass

from profilis.core.emitter import Emitter
from profilis.runtime import get_current_parent_span_id, now_ns
from profilis.sampling import (
    _compile_excludes,
    _compile_overrides,
    clamp_sampling_rate,
    get_effective_rate,
    make_rng,
)
from profilis.sampling import (
    should_exclude_route as sampling_should_exclude_route,
)
from profilis.sampling import (
    should_record_request as sampling_should_record_request,
)
from profilis.sampling import (
    should_sample_request as sampling_should_sample_request,
)

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
    def __init__(  # noqa: PLR0913
        self,
        *,
        sampling_rate: float = 1.0,
        route_excludes: t.Iterable[str] | None = None,
        route_overrides: t.Iterable[tuple[str, float]] | None = None,
        always_sample_errors: bool = True,
        random_seed: int | None = None,
        rng: t.Callable[[], float] | None = None,
    ) -> None:
        """
        sampling_rate: float in [0.0, 1.0] probability of capturing a request.
                       1.0 captures all; 0.0 captures none (except 5xx if always_sample_errors).
        route_excludes: iterable of route prefixes or exact strings to skip; use "re:..." for regex.
        route_overrides: iterable of (pattern, rate) for per-route sampling; first match wins; "re:..." for regex.
        always_sample_errors: if True, 5xx and exceptions are always recorded.
        random_seed: optional seed for deterministic sampling (tests).
        rng: optional callable () -> float in [0,1) for deterministic tests; overrides random_seed if set.
        """
        self.sampling_rate = clamp_sampling_rate(sampling_rate)
        self.route_excludes = list(route_excludes or [])
        self.route_overrides = list(route_overrides or [])
        self.always_sample_errors = bool(always_sample_errors)
        self.random_seed = random_seed
        self.rng = rng


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
        self._excludes_compiled = _compile_excludes(self.cfg.route_excludes)
        self._overrides_compiled = _compile_overrides(self.cfg.route_overrides)
        self._rng = make_rng(random_seed=self.cfg.random_seed, rng=self.cfg.rng)

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

    def _should_sample_request(self, path: str) -> bool:
        """Determine if this request should be sampled (uses per-route rate when overrides match)."""
        rate = get_effective_rate(path, self._overrides_compiled, self.cfg.sampling_rate)
        return sampling_should_sample_request(rate, self._rng)

    def _should_record_request(
        self, sampled: bool, status_code: int | None, error_info: dict[str, str] | None
    ) -> bool:
        """Determine if this request should be recorded (sampled or 5xx when always_sample_errors)."""
        return sampling_should_record_request(
            sampled,
            status_code,
            error_info,
            self.cfg.always_sample_errors,
            HTTP_ERROR_STATUS_THRESHOLD,
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

        # Check if route should be excluded (prefix or regex)
        if sampling_should_exclude_route(path, self._excludes_compiled):
            await self.app(scope, receive, send)
            return

        # Determine sampling (global or per-route override)
        sampled = self._should_sample_request(path)

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
