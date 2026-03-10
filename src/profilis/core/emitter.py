"""Emitter: hot-path event creation + enqueue to AsyncCollector.

- Builds tiny dicts for REQ/FN/DB events
- Optimized to minimize allocations (≤15µs/event target)
"""

from __future__ import annotations

from typing import Any

from profilis.core.async_collector import AsyncCollector
from profilis.runtime import get_span_id, get_trace_id, now_ns

__all__ = ["Emitter"]


class Emitter:
    def __init__(self, collector: AsyncCollector[dict[str, Any]]):
        self._collector = collector

    def _base(self, kind: str) -> dict[str, Any]:
        # Tiny dict, no dataclass conversion for hot path
        return {
            "ts_ns": now_ns(),
            "trace_id": get_trace_id(),
            "span_id": get_span_id(),
            "kind": kind,
        }

    def emit_req(self, route: str, status: int, dur_ns: int) -> None:
        ev = self._base("REQ")
        ev.update(route=route, status=status, dur_ns=dur_ns)
        self._collector.enqueue(ev)

    def emit_fn(self, name: str, dur_ns: int, error: bool = False) -> None:
        ev = self._base("FN")
        ev.update(fn=name, dur_ns=dur_ns, error=error)
        self._collector.enqueue(ev)

    def emit_db(
        self,
        query: str,
        dur_ns: int,
        rows: int,
        *,
        db_vendor: str | None = None,
    ) -> None:
        ev = self._base("DB")
        ev.update(query=query, dur_ns=dur_ns, rows=rows)
        if db_vendor is not None:
            ev["db_vendor"] = db_vendor
        self._collector.enqueue(ev)
