# src/profilis/pyodbc/instrumentation.py
"""pyodbc raw wrapper (execute / executemany)

Non-invasive instrumentation: wrap cursor methods on a per-cursor basis.
"""

from __future__ import annotations

import contextlib
import re
from dataclasses import dataclass
from typing import Any

from profilis.core.emitter import Emitter
from profilis.runtime import now_ns

# Reuse redact_statement from SQLAlchemy helper in repo
try:
    from profilis.sqlalchemy.instrumentation import redact_statement
except Exception:
    # Fallback: simple redaction if import fails (should not in normal repo)
    _STRINGS_RE = re.compile(r"('([^'\\]|\\.)*'|\"([^\"\\]|\\.)*\")")
    _NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
    _WS_RE = re.compile(r"\s+")

    def redact_statement(sql: str, *, max_len: int = 200) -> str:
        s = _STRINGS_RE.sub("?", sql)
        s = _NUM_RE.sub("?", s)
        s = _WS_RE.sub(" ", s).strip()
        if max_len > 0 and len(s) > max_len:
            return s[: max_len - 1] + "…"
        return s


@dataclass
class PyODBCConfig:
    vendor_label: str = "pyodbc"
    redact_statements: bool = True
    preview_len: int = 200
    redact_params: bool = True


@dataclass
class DBExecutionInfo:
    stmt: str
    params: Any
    dur: int
    rows: int
    exc: Exception | None


def _truncate_string(s: str, max_len: int) -> str:
    """Truncate string if it exceeds max_len."""
    if len(s) > max_len:
        return s[: max_len - 1] + "…"
    return s


def _format_sequence_items(items: list[Any], redact: bool, max_len: int) -> list[str]:
    """Format items in a sequence for preview."""
    if redact:
        return ["?" for _ in items]

    formatted_items = []
    for item in items:
        s = repr(item)
        formatted_items.append(_truncate_string(s, max_len))
    return formatted_items


def _format_mapping_items(params: dict[Any, Any], redact: bool, max_len: int) -> list[str]:
    """Format items in a mapping for preview."""
    if redact:
        keys = sorted(list(params.keys()))
        return [f"{k}:?" for k in keys]

    kvs = []
    for k, v in dict(params).items():
        s = repr(v)
        formatted_value = _truncate_string(s, max_len)
        kvs.append(f"{k}:{formatted_value}")
    return kvs


def _params_preview(params: Any, redact: bool, max_len: int) -> str:
    """Create a short preview string for bound parameters.

    If redact==True, we replace values with '?' but preserve shapes (lists/tuples).
    Otherwise we attempt to convert to str and truncate.
    """
    try:
        if params is None:
            return "[]"

        # pyodbc typically receives sequences or single tuple
        if isinstance(params, (list, tuple)):
            items = _format_sequence_items(list(params), redact, max_len)
            preview = "[" + ", ".join(items) + "]"
            return _truncate_string(preview, max_len)

        # If mapping-like (pyodbc doesn't commonly use dicts, but be defensive)
        if hasattr(params, "items"):
            items = _format_mapping_items(dict(params), redact, max_len)
            preview = "{" + ", ".join(items) + "}"
            return _truncate_string(preview, max_len)

        # Fallback: scalar
        s = repr(params)
        if redact:
            return "?"
        return _truncate_string(s, max_len)
    except Exception:
        return "[unserializable-params]"


def _format_sql_statement(sql: Any, config: PyODBCConfig) -> str:
    """Format SQL statement for logging."""
    try:
        if config.redact_statements and isinstance(sql, str):
            return redact_statement(sql, max_len=config.preview_len)
        elif isinstance(sql, str) and len(sql) > config.preview_len:
            return str(sql)[: config.preview_len] + "…"
        else:
            return str(sql)
    except Exception:
        return "<unserializable-sql>"


def _get_row_count(cursor: Any) -> int:
    """Get row count from cursor, handling exceptions."""
    try:
        return int(getattr(cursor, "rowcount", -1) or -1)
    except Exception:
        return -1


def _emit_db_metrics(emitter: Emitter, stmt: str, dur: int, rows: int) -> None:
    """Emit DB metrics, suppressing any exceptions."""
    with contextlib.suppress(Exception):
        emitter.emit_db(stmt, dur_ns=dur, rows=rows)


def _emit_db_meta(emitter: Emitter, config: PyODBCConfig, exec_info: DBExecutionInfo) -> None:
    """Emit DB metadata, suppressing any exceptions."""
    meta = {
        "kind": "DB_META",
        "vendor": config.vendor_label,
        "query": exec_info.stmt,
        "params_preview": _params_preview(
            exec_info.params, redact=config.redact_params, max_len=config.preview_len
        ),
        "dur_ns": exec_info.dur,
        "rows": exec_info.rows,
        "error": exec_info.exc is not None,
        "ts_ns": now_ns(),
    }
    with contextlib.suppress(Exception):
        emitter._collector.enqueue(meta)


def _create_wrapped_execute(
    original_execute: Any, cursor: Any, emitter: Emitter, config: PyODBCConfig
) -> Any:
    """Create wrapped execute function."""

    def _wrap_execute(*args: Any, **kwargs: Any) -> Any:
        sql = args[0] if args else ""
        params = args[1] if len(args) > 1 else kwargs.get("params")

        start = now_ns()
        exc = None
        try:
            return original_execute(*args, **kwargs)
        except Exception as e:
            exc = e
            raise
        finally:
            dur = now_ns() - start
            stmt = _format_sql_statement(sql, config)
            rows = _get_row_count(cursor)
            _emit_db_metrics(emitter, stmt, dur, rows)
            exec_info = DBExecutionInfo(stmt=stmt, params=params, dur=dur, rows=rows, exc=exc)
            _emit_db_meta(emitter, config, exec_info)

    return _wrap_execute


def _create_wrapped_executemany(
    original_executemany: Any, cursor: Any, emitter: Emitter, config: PyODBCConfig
) -> Any:
    """Create wrapped executemany function."""

    def _wrap_executemany(*args: Any, **kwargs: Any) -> Any:
        sql = args[0] if args else ""
        params_seq = args[1] if len(args) > 1 else kwargs.get("params")

        start = now_ns()
        exc = None
        try:
            return original_executemany(*args, **kwargs)
        except Exception as e:
            exc = e
            raise
        finally:
            dur = now_ns() - start
            stmt = _format_sql_statement(sql, config)
            rows = _get_row_count(cursor)
            _emit_db_metrics(emitter, stmt, dur, rows)
            exec_info = DBExecutionInfo(stmt=stmt, params=params_seq, dur=dur, rows=rows, exc=exc)
            _emit_db_meta(emitter, config, exec_info)

    return _wrap_executemany


def instrument_pyodbc_cursor(cursor: Any, emitter: Emitter, config: PyODBCConfig) -> Any:
    """Wraps a *cursor instance* to instrument execute/executemany.

    Returns the same cursor object but with wrapped methods (non-invasive).
    """
    # Ensure idempotent: do not double-wrap
    if getattr(cursor, "_profilis_wrapped", False):
        return cursor
    cursor._profilis_wrapped = True

    original_execute = getattr(cursor, "execute", None)
    original_executemany = getattr(cursor, "executemany", None)

    # Replace methods on the cursor instance
    if original_execute is not None:
        cursor.execute = _create_wrapped_execute(original_execute, cursor, emitter, config)
    if original_executemany is not None:
        cursor.executemany = _create_wrapped_executemany(
            original_executemany, cursor, emitter, config
        )

    return cursor


def instrument_pyodbc_connection(connection: Any, emitter: Emitter, config: PyODBCConfig) -> None:
    """Instrument a pyodbc connection by wrapping its .cursor() method.

    On each .cursor() call we will return a cursor with wrapped execute/executemany.
    This avoids monkeypatching a module/class globally and is safe for tests/CI.
    """
    original_cursor = getattr(connection, "cursor", None)
    if original_cursor is None:
        return

    if getattr(connection, "_profilis_cursor_wrapped", False):
        return
    connection._profilis_cursor_wrapped = True

    def _cursor_wrap(*args: Any, **kwargs: Any) -> Any:
        cur = original_cursor(*args, **kwargs)
        with contextlib.suppress(Exception):
            # Instrumentation must not break the connection
            instrument_pyodbc_cursor(cur, emitter, config)
        return cur

    connection.cursor = _cursor_wrap
