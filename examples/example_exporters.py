"""
Demo: using AsyncCollector with JSONLExporter and ConsoleExporter.

Run:
    python scripts/demo_exporters.py
"""

import time

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.console import ConsoleExporter
from profilis.exporters.jsonl import JSONLExporter

# Setup exporters
jsonl = JSONLExporter(dir="./logs", rotate_bytes=1024, rotate_secs=5)
console = ConsoleExporter(pretty=True)

# Setup collectors
jsonl_collector = AsyncCollector(jsonl, queue_size=128, flush_interval=0.2, batch_max=16)
console_collector = AsyncCollector(console, queue_size=128, flush_interval=0.2, batch_max=16)

# Emit some test events
emitter_jsonl = Emitter(jsonl_collector)
emitter_console = Emitter(console_collector)

for i in range(20):
    emitter_jsonl.emit_req("/demo", 200, dur_ns=1000 * i)
    emitter_console.emit_fn("work", dur_ns=2000 * i, error=(i % 5 == 0))
    time.sleep(0.1)

# Close collectors to flush and rotate
jsonl_collector.close()
console_collector.close()
print("Demo complete. Check ./logs for rotated JSONL files.")
