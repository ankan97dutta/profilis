from __future__ import annotations

import json
import os

from sanic import Sanic
from sanic.request import Request
from sanic.response import json as sanic_json

from bench.apps.common import do_work, read_cfg, start_stats_writer
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.sanic.adapter import SanicConfig, instrument_sanic_app

app = Sanic("profilis-bench-sanic")
cfg = read_cfg()


def sink(_batch: list[dict]) -> None:
    return


collector = AsyncCollector(sink, queue_size=cfg.queue_size, flush_interval=cfg.flush_interval)
emitter = Emitter(collector)

if cfg.enabled:
    instrument_sanic_app(
        app,
        emitter,
        SanicConfig(sampling_rate=cfg.sample, route_excludes=["/health", "/metrics"]),
    )

start_stats_writer(
    lambda: {
        "enqueued": int(getattr(collector, "enqueued", 0)),
        "processed": int(getattr(collector, "processed", 0)),
        "dropped_oldest": int(getattr(collector, "dropped_oldest", 0)),
        "flush_errors": int(getattr(collector, "flush_errors", 0)),
        "queue_depth": int(getattr(collector, "queue_depth", 0)),
        "framework": "sanic",
        "profilis_enabled": bool(cfg.enabled),
    }
)


@app.get("/health")  # type: ignore[untyped-decorator]
async def health(_request: Request):
    return sanic_json({"ok": True})


@app.get("/work")  # type: ignore[untyped-decorator]
async def work(request: Request):
    n = int(request.args.get("n", "2000"))
    return sanic_json({"ok": True, "out": do_work(n)})


@app.get("/metrics")  # type: ignore[untyped-decorator]
async def metrics(_request: Request):
    return sanic_json(
        {
            "enqueued": int(getattr(collector, "enqueued", 0)),
            "processed": int(getattr(collector, "processed", 0)),
            "dropped_oldest": int(getattr(collector, "dropped_oldest", 0)),
            "flush_errors": int(getattr(collector, "flush_errors", 0)),
            "queue_depth": int(getattr(collector, "queue_depth", 0)),
        }
    )


@app.after_server_stop
async def _dump_collector_stats(_app: Sanic, _loop) -> None:  # type: ignore[no-untyped-def]
    payload = {
        "enqueued": int(getattr(collector, "enqueued", 0)),
        "processed": int(getattr(collector, "processed", 0)),
        "dropped_oldest": int(getattr(collector, "dropped_oldest", 0)),
        "flush_errors": int(getattr(collector, "flush_errors", 0)),
        "queue_depth": int(getattr(collector, "queue_depth", 0)),
        "framework": "sanic",
        "profilis_enabled": bool(cfg.enabled),
    }
    print("BENCH_COLLECTOR " + json.dumps(payload, sort_keys=True))
    collector.close()


if __name__ == "__main__":
    host = os.getenv("BENCH_HOST", "127.0.0.1")
    port = int(os.getenv("BENCH_PORT", "9011"))
    app.run(host=host, port=port, debug=False, single_process=True)
