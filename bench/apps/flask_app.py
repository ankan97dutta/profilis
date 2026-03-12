from __future__ import annotations

import atexit
import contextlib
import json
import os
import signal

from flask import Flask, jsonify, request

from bench.apps.common import do_work, read_cfg, start_stats_writer
from profilis.core.async_collector import AsyncCollector
from profilis.flask.adapter import ProfilisFlask

app = Flask("profilis-bench-flask")
cfg = read_cfg()


def sink(_batch: list[dict]) -> None:
    return


collector = AsyncCollector(sink, queue_size=cfg.queue_size, flush_interval=cfg.flush_interval)

if cfg.enabled:
    ProfilisFlask(
        app, collector=collector, exclude_routes=["/health", "/metrics"], sample=cfg.sample
    )


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/work")
def work() -> object:
    n = int(request.args.get("n", "2000"))
    return jsonify({"ok": True, "out": do_work(n)})


@app.get("/metrics")
def metrics() -> dict[str, int]:
    return {
        "enqueued": int(getattr(collector, "enqueued", 0)),
        "processed": int(getattr(collector, "processed", 0)),
        "dropped_oldest": int(getattr(collector, "dropped_oldest", 0)),
        "flush_errors": int(getattr(collector, "flush_errors", 0)),
        "queue_depth": int(getattr(collector, "queue_depth", 0)),
    }


start_stats_writer(metrics)


@atexit.register
def _dump_collector_stats() -> None:
    payload = metrics()
    payload["framework"] = "flask"
    payload["profilis_enabled"] = bool(cfg.enabled)
    print("BENCH_COLLECTOR " + json.dumps(payload, sort_keys=True))


def _handle_signal(_signum: int, _frame: object) -> None:
    with contextlib.suppress(Exception):
        _dump_collector_stats()
    with contextlib.suppress(Exception):
        collector.close()
    raise SystemExit(0)


if __name__ == "__main__":
    host = os.getenv("BENCH_HOST", "127.0.0.1")
    port = int(os.getenv("BENCH_PORT", "9011"))
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)
    app.run(host=host, port=port, debug=False, threaded=True)
