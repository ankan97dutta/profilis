from __future__ import annotations

import pytest

pytest.importorskip("pytest_benchmark")

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter

MAX_MEAN_S = 0.0005  # 0.5ms


def test_emitter_emit_req_microbench(benchmark) -> None:  # type: ignore[no-untyped-def]
    def sink(_batch: list[dict[str, object]]) -> None:
        return

    collector = AsyncCollector(sink, queue_size=8192, flush_interval=10.0, batch_max=1024)
    emitter = Emitter(collector)

    def emit_one() -> None:
        emitter.emit_req(route="/work", status=200, dur_ns=123_456)

    benchmark(emit_one)

    # Guardrail: keep very conservative for CI runners.
    assert benchmark.stats.stats.mean < MAX_MEAN_S
    collector.close()
