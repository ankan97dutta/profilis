"""Minimal core runtime API for IDs, clocks, and async-safe context.


Acceptance:
- No locks on the hot path
- Async-safe via ContextVar


Public API surface exported here for convenience.
"""

from .clock import now_ns
from .context import (
    get_current_parent_span_id,
    get_span_id,
    get_trace_id,
    reset_span_id,
    reset_trace_id,
    set_span_id,
    set_trace_id,
    use_span,
)
from .ids import span_id

__all__ = [
    "get_current_parent_span_id",
    "get_span_id",
    "get_trace_id",
    "now_ns",
    "reset_span_id",
    "reset_trace_id",
    "set_span_id",
    "set_trace_id",
    "span_id",
    "use_span",
]
