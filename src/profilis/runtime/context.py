"""Async-safe trace/span context using ContextVar.


Provides minimal helpers + a context manager for ergonomic usage without locks.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

__all__ = [
    "get_current_parent_span_id",
    "get_span_id",
    "get_trace_id",
    "reset_span_id",
    "reset_trace_id",
    "set_span_id",
    "set_trace_id",
    "use_span",
]

# None means "unset". Keep defaults at module import for speed; ContextVar is async-safe.
_TRACE_ID: ContextVar[str | None] = ContextVar("profilis_trace_id", default=None)
_SPAN_ID: ContextVar[str | None] = ContextVar("profilis_span_id", default=None)


# --- Getters ---
def get_trace_id() -> str | None:
    return _TRACE_ID.get()


def get_span_id() -> str | None:
    return _SPAN_ID.get()


# --- Setters returning tokens for manual reset ---
def set_trace_id(value: str | None) -> Token[str | None]:
    return _TRACE_ID.set(value)


def set_span_id(value: str | None) -> Token[str | None]:
    return _SPAN_ID.set(value)


# --- Reset helpers ---


def reset_trace_id(token: Token[str | None]) -> None:
    _TRACE_ID.reset(token)


def reset_span_id(token: Token[str | None]) -> None:
    _SPAN_ID.reset(token)


# --- Ergonomic context manager ---
@contextmanager
def use_span(trace_id: str | None = None, span_id: str | None = None) -> Iterator[None]:
    """Temporarily set trace/span IDs (async-safe). Resets on exit.


    Parameters may be None to leave a value unchanged.
    """
    ttoken = stoken = None
    try:
        if trace_id is not None:
            ttoken = set_trace_id(trace_id)
        if span_id is not None:
            stoken = set_span_id(span_id)
        yield
    finally:
        # Reset only what we set
        if stoken is not None:
            reset_span_id(stoken)
        if ttoken is not None:
            reset_trace_id(ttoken)


def get_current_parent_span_id() -> str | None:
    """
    Return the current span id (preferred) or trace id as a fallback.

    Rationale:
      - Adapters that need to link DB events to traces can call this single, dependency-free helper.
      - This centralizes span/trace access and keeps telemetry plumbing testable.
    """
    span = get_span_id()
    if span:
        return span
    return get_trace_id()
