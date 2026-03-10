"""SQLAlchemy engine instrumentation (sync & async) with statement redaction.

- Hooks before/after_cursor_execute on Engine and AsyncEngine.sync_engine
- Emits DB metrics via Emitter with redacted statements and rowcount
- Redaction replaces string & numeric literals with '?' and trims to max length
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine

try:  # SQLAlchemy 1.4/2.x async engine
    from sqlalchemy.ext.asyncio import AsyncEngine  # type: ignore
except Exception:  # pragma: no cover
    AsyncEngine = None  # type: ignore

from profilis.core.emitter import Emitter
from profilis.runtime import now_ns

__all__ = [
    "instrument_async_engine",
    "instrument_engine",
    "redact_statement",
]

# ------------------------ Redaction ------------------------
_STRINGS_RE = re.compile(r"('([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\")")
_NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
_WS_RE = re.compile(r"\s+")


def redact_statement(sql: str, *, max_len: int = 200) -> str:
    """Redact string and numeric literals and trim length.

    Example:
      INSERT INTO users (name, age) VALUES ('Alice', 42)
      -> INSERT INTO users (name, age) VALUES (?, ?)
    """
    s = _STRINGS_RE.sub("?", sql)
    s = _NUM_RE.sub("?", s)
    s = _WS_RE.sub(" ", s).strip()
    if max_len > 0 and len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


# ---------------------- Instrumentation --------------------
def instrument_engine(
    engine: Engine,
    emitter: Emitter,
    *,
    redact: bool = True,
    max_len: int = 200,
) -> None:
    """Attach before/after hooks to a synchronous SQLAlchemy Engine.

    Emits `DB` with fields: query (redacted), dur_ns, rows
    """

    @event.listens_for(engine, "before_cursor_execute")
    def _before(  # noqa: PLR0913
        conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any
    ) -> None:
        context._profilis_start_ns = now_ns()  # type: ignore[attr-defined]

    @event.listens_for(engine, "after_cursor_execute")
    def _after(  # noqa: PLR0913
        conn: Any, cursor: Any, statement: Any, parameters: Any, context: Any, executemany: Any
    ) -> None:
        start_ns = getattr(context, "_profilis_start_ns", None)
        if start_ns is None:
            return

        try:
            dur = now_ns() - start_ns
            stmt = redact_statement(statement, max_len=max_len) if redact else str(statement)
            rows = getattr(cursor, "rowcount", -1)
            _eng = getattr(conn, "engine", None)
            db_vendor = getattr(getattr(_eng, "dialect", None), "name", None) if _eng else None
            emitter.emit_db(
                stmt,
                dur_ns=dur,
                rows=int(rows) if rows is not None else -1,
                db_vendor=db_vendor,
            )
        finally:
            if hasattr(context, "_profilis_start_ns"):
                delattr(context, "_profilis_start_ns")


def instrument_async_engine(
    async_engine: AsyncEngine,
    emitter: Emitter,
    *,
    redact: bool = True,
    max_len: int = 200,
) -> None:
    """Attach hooks to an AsyncEngine by instrumenting its sync_engine."""
    sync_eng = async_engine.sync_engine  # type: ignore[attr-defined]
    instrument_engine(sync_eng, emitter, redact=redact, max_len=max_len)
