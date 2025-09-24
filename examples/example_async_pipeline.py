"""Minimal integration: runtime context + AsyncCollector + JSONL sink.

Run:
  uv run python scripts/demo_async_pipeline.py  # or `python ...`

What it shows:
- Creates a global AsyncCollector that writes JSONL batches to `./demo-out.jsonl`
- Uses runtime.use_span(trace_id, span_id) to tag events
- Fires concurrent async tasks that enqueue events without blocking
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass

from profilis.core.async_collector import AsyncCollector
from profilis.runtime import get_span_id, get_trace_id, now_ns, span_id, use_span


# -------------------- Event model --------------------
@dataclass
class Event:
    ts_ns: int
    trace_id: str | None
    span_id: str | None
    level: str
    msg: str
    attrs: dict[str, object]


def make_event(level: str, msg: str, **attrs: object) -> Event:
    return Event(
        ts_ns=now_ns(),
        trace_id=get_trace_id(),
        span_id=get_span_id(),
        level=level,
        msg=msg,
        attrs=attrs,
    )


# -------------------- Sink: JSONL file --------------------
_OUT = os.path.abspath("demo-out.jsonl")


def _jsonl_sink(batch: list[Event]) -> None:
    # Append a batch as JSON lines; fast and simple for a demo
    with open(_OUT, "a", encoding="utf-8") as f:
        for ev in batch:
            f.write(json.dumps(asdict(ev), separators=(",", ":")) + "\n")


# Global collector (bounded, drop-oldest, batches by 128, flush every 100ms)
collector = AsyncCollector(_jsonl_sink, queue_size=2048, batch_max=128, flush_interval=0.1)


# -------------------- Demo workload --------------------
async def worker(name: str, n: int) -> None:
    # Each worker gets its own span; share a trace for the whole run
    with use_span(span_id=span_id()):
        for i in range(n):
            # Non-blocking enqueue under pressure
            collector.enqueue(make_event("INFO", "tick", worker=name, i=i))
            # Do real work here…
            if i % 50 == 0:
                await asyncio.sleep(0)


async def main() -> None:
    # One trace for the whole run
    with use_span(trace_id=span_id()):
        await asyncio.gather(
            worker("A", 1000),
            worker("B", 1000),
            worker("C", 1000),
        )
        # Enqueue a final summary event
        collector.enqueue(make_event("INFO", "demo-complete"))

    # Ensure everything is flushed for the demo
    collector.close()
    print(f"Wrote events → {_OUT}")


if __name__ == "__main__":
    asyncio.run(main())
