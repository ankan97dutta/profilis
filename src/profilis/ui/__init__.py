"""Shared Profilis UI: error ring, dashboard HTML, and framework-agnostic types.

Use this package for ErrorItem, record_error, get_error_ring, and DASHBOARD_HTML.
Framework-specific blueprints/routers are in profilis.flask.ui, profilis.sanic.ui,
and profilis.fastapi.ui.
"""

from profilis.ui._core import ErrorItem, get_error_ring, record_error
from profilis.ui._html import DASHBOARD_HTML

__all__ = [
    "DASHBOARD_HTML",
    "ErrorItem",
    "get_error_ring",
    "record_error",
]
