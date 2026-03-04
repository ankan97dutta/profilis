"""Microbenchmark emitter enqueue cost."""

import time
from typing import Any

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter

received: list[Any] = []
col = AsyncCollector[dict[str, Any]](
    received.extend, queue_size=10000, flush_interval=1.0, batch_max=1000
)
em = Emitter(col)

N = 10000
start = time.perf_counter()
for _i in range(N):
    em.emit_fn("bench", 1234)
end = time.perf_counter()

dur = (end - start) / N
print(f"enqueue avg: {dur * 1e6:.2f} µs/event")
col.close()
