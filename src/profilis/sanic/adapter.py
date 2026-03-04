"""Sanic native adapter for Profilis.

- Registers request/response/exception middleware that records HTTP metrics.
- Optionally mounts an ASGI UI app at a given path (best-effort; depends on Sanic version).
"""

from __future__ import annotations

import contextlib
import logging
import traceback
import typing as t
from collections.abc import Awaitable, Callable

from sanic import Sanic

from profilis.core.emitter import Emitter
from profilis.runtime import now_ns
from profilis.runtime.context import get_current_parent_span_id

log = logging.getLogger("profilis.sanic")

# HTTP status used to treat response as server error (PLR2004)
HTTP_INTERNAL_SERVER_ERROR = 500


class SanicConfig:
    def __init__(
        self,
        *,
        sampling_rate: float = 1.0,
        route_excludes: t.Iterable[str] | None = None,
        always_sample_errors: bool = True,
    ) -> None:
        self.sampling_rate = float(sampling_rate)
        self.route_excludes = list(route_excludes or [])
        self.always_sample_errors = bool(always_sample_errors)


def _should_exclude_route(path: str, excludes: t.Iterable[str]) -> bool:
    if not excludes:
        return False
    for pat in excludes:
        if not pat:
            continue
        if path.startswith(pat) or path == pat:
            return True
    return False


def instrument_sanic_app(  # noqa: PLR0915
    app: Sanic,
    emitter: Emitter,
    config: SanicConfig | None = None,
    *,
    mount_asgi_app: Callable[..., Awaitable[None]] | None = None,
    mount_path: str = "/_spyglass",
) -> None:
    """
    Attach Profilis middleware to a Sanic app.

    - app: a Sanic instance
    - emitter: Emitter instance
    - config: SanicConfig
    - mount_asgi_app: optional ASGI app (callable) to mount at mount_path if Sanic supports mounting ASGI apps
    - mount_path: where to mount the ASGI app if provided

    The function registers request / response / exception middleware on the app.
    """

    cfg = config or SanicConfig()

    # request middleware: set start timestamp and record method/path
    @app.middleware("request")
    async def _profilis_request_middleware(request: t.Any) -> None:
        # Only HTTP requests; Sanic uses Request objects for http
        try:
            method = getattr(request, "method", "UNKNOWN")
            path = getattr(request, "path", "/")
            if _should_exclude_route(path, cfg.route_excludes):
                # mark excluded to short-circuit in response middleware
                request.ctx._profilis_excluded = True
                return
            request.ctx._profilis_start_ns = now_ns()
            request.ctx._profilis_method = method
            request.ctx._profilis_path = path
            request.ctx._profilis_route = (
                getattr(request, "route", None) and getattr(request.route, "path", None)
            ) or None
        except Exception:
            # never break request handling
            with contextlib.suppress(Exception):
                request.ctx._profilis_excluded = True

    # response middleware: fires on normal response
    @app.middleware("response")
    async def _profilis_response_middleware(request: t.Any, response: t.Any) -> None:
        try:
            if getattr(request.ctx, "_profilis_excluded", False):
                return
            start = getattr(request.ctx, "_profilis_start_ns", None)
            if start is None:
                # nothing recorded
                return
            dur_ns = now_ns() - start
            status = int(getattr(response, "status", 0) or 0)
            method = getattr(request.ctx, "_profilis_method", getattr(request, "method", "UNKNOWN"))
            path = getattr(request.ctx, "_profilis_path", getattr(request, "path", "/"))
            route = getattr(request.ctx, "_profilis_route", None)
            is_error_status = status >= HTTP_INTERNAL_SERVER_ERROR
            should_record = (
                (cfg.sampling_rate >= 1.0)
                or (
                    0.0 < cfg.sampling_rate < 1.0
                    and __import__("random").random() <= cfg.sampling_rate
                )
                or (cfg.always_sample_errors and is_error_status)
            )

            if should_record:
                parent = None
                try:
                    parent = get_current_parent_span_id()
                except Exception:
                    parent = None

                payload = {
                    "kind": "HTTP",
                    "vendor": "sanic",
                    "method": method,
                    "path": path,
                    "route": route,
                    "status": status,
                    "dur_ns": dur_ns,
                    "ts_ns": now_ns(),
                    "error": None,
                    "parent_span_id": parent,
                }
                # Try emit_http if available
                with contextlib.suppress(Exception):
                    emit_fn = getattr(emitter, "emit_http", None)
                    if callable(emit_fn):
                        with contextlib.suppress(Exception):
                            emit_fn(method=method, path=path, status=status, dur_ns=dur_ns)
                with contextlib.suppress(Exception):
                    emitter._collector.enqueue(payload)
        except Exception:
            # swallow any middleware errors
            log.exception("profilis: error in response middleware")

    # exception middleware: capture exception and still emit
    @app.exception(Exception)
    async def _profilis_exception_handler(request: t.Any, exception: BaseException) -> None:
        try:
            if getattr(request.ctx, "_profilis_excluded", False):
                # let default handlers run
                raise exception
            start = getattr(request.ctx, "_profilis_start_ns", None)
            dur_ns = now_ns() - start if start is not None else -1
            method = getattr(request.ctx, "_profilis_method", getattr(request, "method", "UNKNOWN"))
            path = getattr(request.ctx, "_profilis_path", getattr(request, "path", "/"))
            route = getattr(request.ctx, "_profilis_route", None)
            parent = None
            with contextlib.suppress(Exception):
                parent = get_current_parent_span_id()

            tb = traceback.format_exc()
            ts = now_ns()
            payload = {
                "kind": "HTTP",
                "vendor": "sanic",
                "method": method,
                "path": path,
                "route": route,
                "status": HTTP_INTERNAL_SERVER_ERROR,
                "dur_ns": dur_ns,
                "ts_ns": ts,
                "error": {
                    "type": type(exception).__name__,
                    "repr": repr(exception),
                    "traceback": tb,
                },
                "parent_span_id": parent,
            }
            with contextlib.suppress(Exception):
                emit_fn = getattr(emitter, "emit_http", None)
                if callable(emit_fn):
                    with contextlib.suppress(Exception):
                        emit_fn(
                            method=method,
                            path=path,
                            status=HTTP_INTERNAL_SERVER_ERROR,
                            dur_ns=dur_ns,
                        )
            with contextlib.suppress(Exception):
                emitter._collector.enqueue(payload)

            # Best-effort: if the Sanic UI module is available, also push this
            # exception into its error ring so the built-in dashboard can
            # surface recent failures.
            try:
                from profilis.sanic.ui import (  # type: ignore  # noqa: PLC0415
                    ErrorItem,
                    record_error,
                )

                try:
                    route_for_ui = route or path or "-"
                except Exception:
                    route_for_ui = "-"

                record_error(
                    ErrorItem(
                        ts_ns=ts,
                        route=route_for_ui,
                        status=HTTP_INTERNAL_SERVER_ERROR,
                        exception_type=type(exception).__name__,
                        exception_value=repr(exception),
                        traceback=tb,
                    )
                )
            except Exception:
                # UI might not be installed/used; ignore any failures here.
                pass
        except Exception:
            log.exception("profilis: error in exception middleware")
        # re-raise so Sanic's default error handling can continue
        raise exception

    # Optional: attempt to mount ASGI UI app if provided
    if mount_asgi_app is not None:
        # Best-effort: some Sanic versions support adding an ASGI app or a sub-app.
        try:
            # If app has 'add_route' that can accept a handler, mount a wrapper that delegates to ASGI app
            # We'll try to detect if Sanic supports `app.add_route` with async handler.
            async def _asgi_wrapper(request: t.Any) -> t.Any:
                # Attempt to call ASGI app by adapting the Sanic request to an ASGI scope.
                # Implement a minimal bridge using the ASGI app callable that also
                # respects the mount_path so that the mounted ASGI app sees the
                # correct `root_path` and `path` (important for routers and static files).
                full_path = request.path or "/"
                root_path = ""
                path = full_path
                if mount_path and mount_path != "/" and full_path.startswith(mount_path):
                    # Trim the mount prefix for the ASGI app's `path` while
                    # exposing it via `root_path` per ASGI spec so that URL
                    # generation and routing inside the ASGI app work as if it
                    # were mounted under `mount_path`.
                    path = full_path[len(mount_path) :] or "/"
                    root_path = mount_path

                server_host = (
                    getattr(request.app, "hostname", None)
                    or getattr(request, "server_name", None)
                    or "127.0.0.1"
                )
                server_port = getattr(request, "server_port", None) or 0

                scope = {
                    "type": "http",
                    "http_version": getattr(request, "version", "1.1"),
                    "asgi": {"version": "3.0", "spec_version": "2.3"},
                    "method": request.method,
                    "scheme": getattr(request, "scheme", "http"),
                    "path": path,
                    "raw_path": path.encode("utf-8"),
                    "query_string": request.query_string.encode("utf-8"),
                    "root_path": root_path,
                    "headers": [
                        (k.lower().encode("utf-8"), v.encode("utf-8"))
                        for k, v in request.headers.items()
                    ],
                    "client": (request.remote_addr and (request.remote_addr, 0)) or None,
                    "server": (server_host, server_port),
                }
                # We'll implement a naive ASGI call that collects the ASGI response and returns a Sanic response.
                body_chunks: list[bytes] = []
                status = 200
                headers: list[tuple[str, str]] = []
                receive_queue: list[dict[str, t.Any]] = []
                sent_start = False

                async def _receive() -> dict[str, t.Any]:
                    # First event: http.request with body
                    if receive_queue:
                        return receive_queue.pop(0)
                    body = await request.body()
                    receive_queue.append({"type": "http.request", "body": body, "more_body": False})
                    return receive_queue.pop(0)

                async def _send(message: dict[str, t.Any]) -> None:
                    nonlocal sent_start, status, headers
                    if message["type"] == "http.response.start":
                        status = int(message.get("status", 200))
                        headers = [
                            (k.decode("utf-8"), v.decode("utf-8"))
                            for k, v in message.get("headers", [])
                        ]
                        sent_start = True
                    elif message["type"] == "http.response.body":
                        body_chunks.append(message.get("body", b""))
                    else:
                        # ignore other message types
                        pass

                # Call ASGI app
                try:
                    await mount_asgi_app(scope, _receive, _send)
                except Exception:
                    log.exception("profilis: error while delegating to mounted ASGI app")
                    return request.app.response_class("internal", status=500)

                body = b"".join(body_chunks)

                # create Sanic response
                # Try to import Sanic's response types lazily to avoid hard dependency at module import
                try:
                    from sanic.response import raw  # noqa: PLC0415

                    # Extract content-type from ASGI headers if present so that we
                    # don't fall back to Sanic's default "application/octet-stream"
                    # (which can cause browsers to download instead of render).
                    response_headers: list[tuple[str, str]] = []
                    content_type: str | None = None
                    for name, value in headers:
                        if name.lower() == "content-type" and content_type is None:
                            content_type = value
                        else:
                            response_headers.append((name, value))

                    if content_type is None:
                        # Reasonable default for HTML UIs; real ASGI apps can and
                        # should set an explicit Content-Type header.
                        content_type = "text/html; charset=utf-8"

                    return raw(
                        body,
                        headers=response_headers or None,
                        status=status,
                        content_type=content_type,
                    )
                except Exception:
                    # Fallback simpler response
                    return request.app.response_class(body, status=status)

            try:
                # try app.add_route or app.add_subapp if available
                if hasattr(app, "add_route"):
                    app.add_route(_asgi_wrapper, mount_path)
                elif hasattr(app, "add_subapp"):
                    # some Sanic versions support sub-apps
                    getattr(app, "create_sub_app", None)
                    # fallback: register route
                    app.add_route(_asgi_wrapper, mount_path)
                else:
                    log.warning(
                        "profilis.sanic: cannot mount ASGI app automatically on this Sanic version"
                    )
            except Exception:
                log.exception("profilis.sanic: failed to mount ASGI app; skipping mount")
        except Exception:
            log.exception("profilis.sanic: error while preparing ASGI mount")
