import math
import time
from typing import Any

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.core.stats import PERCENT_MAX, SPARKLINE_BINS, StatsStore


def test_stats_percentiles_properties() -> None:
    s = StatsStore(window_sec=60)
    # inject known durations
    for i in range(1, 101):
        s.record(i * 1_000_000, error=(i % 10 == 0))
    snap = s.snapshot()
    assert 0 <= snap["error_pct"] <= PERCENT_MAX
    assert math.isclose(snap["p50"], 50.0, rel_tol=0.1)
    assert snap["p95"] >= snap["p50"]


def test_sparkline_and_rps() -> None:
    s = StatsStore(window_sec=60)
    now = time.time()
    for i in range(30):
        s._events.append((now - i, i, False))
    snap = s.snapshot()
    assert len(snap["spark"]) == SPARKLINE_BINS
    assert isinstance(snap["rps"], float)


def test_emitter_enqueue(monkeypatch: Any) -> None:
    received: list[Any] = []
    col = AsyncCollector[dict[str, Any]](
        received.extend, queue_size=32, flush_interval=0.01, batch_max=8
    )
    em = Emitter(col)
    em.emit_req("/home", 200, 1000)
    em.emit_fn("work", 2000, error=True)
    em.emit_db("SELECT 1", 3000, rows=1)
    time.sleep(0.05)
    col.close()
    assert any(ev["kind"] == "REQ" for ev in received)
    assert any(ev["kind"] == "FN" for ev in received)
    assert any(ev["kind"] == "DB" for ev in received)
