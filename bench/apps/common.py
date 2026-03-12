from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BenchCfg:
    enabled: bool
    queue_size: int
    flush_interval: float
    sample: float


def read_cfg() -> BenchCfg:
    enabled = os.getenv("PROFILIS_ENABLED", "0").strip() not in ("0", "false", "False", "")
    return BenchCfg(
        enabled=enabled,
        queue_size=int(os.getenv("PROFILIS_QUEUE_SIZE", "2048")),
        flush_interval=float(os.getenv("PROFILIS_FLUSH_INTERVAL", "0.1")),
        sample=float(os.getenv("PROFILIS_SAMPLE", "1.0")),
    )


def do_work(n: int = 2000) -> int:
    acc = 0
    for i in range(n):
        acc += (i * 31) % 97
    return acc


def start_stats_writer(get_stats: callable) -> None:  # type: ignore[name-defined]
    path = os.getenv("BENCH_STATS_FILE", "").strip()
    if not path:
        return

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    def loop() -> None:
        while True:
            try:
                tmp = p.with_suffix(p.suffix + ".tmp")
                tmp.write_text(json_dumps(get_stats()), encoding="utf-8")
                tmp.replace(p)
            except Exception:
                pass
            time.sleep(0.5)

    t = threading.Thread(target=loop, daemon=True)
    t.start()


def json_dumps(obj: object) -> str:
    return json.dumps(obj, sort_keys=True)
