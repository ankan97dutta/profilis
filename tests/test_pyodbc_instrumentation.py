# tests/test_pyodbc_instrumentation.py
import time
from typing import Any, Optional

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.pyodbc.instrumentation import PyODBCConfig, instrument_pyodbc_cursor


class DummyCursor:
    def __init__(self) -> None:
        self.rowcount = -1
        self.called: list[tuple[str, str, Any]] = []

    def execute(self, sql: str, params: Optional[Any] = None) -> str:
        self.called.append(("execute", sql, params))
        # simulate DB side effect
        self.rowcount = 1
        return "EXECUTE-RESULT"

    def executemany(self, sql: str, seq: Optional[list[tuple[Any, ...]]]) -> str:
        self.called.append(("executemany", sql, seq))
        self.rowcount = len(seq) if seq is not None else -1
        return "EXECUTEMANY-RESULT"


def test_execute_wrap_records_and_passes_through() -> None:
    received: list[Any] = []
    col: AsyncCollector[dict[str, Any]] = AsyncCollector(
        lambda b: received.extend(b), queue_size=100, flush_interval=0.05
    )
    em = Emitter(col)
    cfg = PyODBCConfig(
        vendor_label="test-db", redact_statements=True, preview_len=80, redact_params=True
    )

    cur = DummyCursor()
    instrument_pyodbc_cursor(cur, em, cfg)

    res = cur.execute("SELECT * FROM users WHERE id = 42", (42,))
    assert res == "EXECUTE-RESULT"
    # wait for collector to flush small batch
    time.sleep(0.1)
    # Should have at least one DB event and one DB_META enqueued
    kinds = [r.get("kind") if isinstance(r, dict) else None for r in received]
    assert "DB_META" in kinds or any(
        hasattr(r, "get") and r.get("kind") == "DB_META" for r in received
    )
    col.close()


def test_executemany_wrap_records_and_passes_through() -> None:
    received: list[Any] = []
    col: AsyncCollector[dict[str, Any]] = AsyncCollector(
        lambda b: received.extend(b), queue_size=100, flush_interval=0.05
    )
    em = Emitter(col)
    cfg = PyODBCConfig(
        vendor_label="test-db", redact_statements=False, preview_len=80, redact_params=False
    )

    cur = DummyCursor()
    instrument_pyodbc_cursor(cur, em, cfg)

    res = cur.executemany("INSERT INTO t(x) VALUES(?)", [(1,), (2,), (3,)])
    assert res == "EXECUTEMANY-RESULT"
    time.sleep(0.1)
    # expect DB and DB_META presence
    assert any(isinstance(r, dict) and r.get("kind") == "DB_META" for r in received)
    col.close()
