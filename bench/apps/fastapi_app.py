from __future__ import annotations

import json

from fastapi import FastAPI, Request

from bench.apps.common import do_work, read_cfg, start_stats_writer
from profilis.asgi.middleware import ASGIConfig
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.fastapi.adapter import instrument_fastapi

app = FastAPI(title="profilis-bench-fastapi")
cfg = read_cfg()


def sink(_batch: list[dict]) -> None:
    return


collector = AsyncCollector(sink, queue_size=cfg.queue_size, flush_interval=cfg.flush_interval)
emitter = Emitter(collector)

if cfg.enabled:
    instrument_fastapi(
        app,
        emitter,
        ASGIConfig(sampling_rate=cfg.sample, route_excludes=["/health", "/metrics"]),
    )


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/work")
async def work(request: Request) -> dict[str, int | bool]:
    n = int(request.query_params.get("n", "2000"))
    return {"ok": True, "out": do_work(n)}


@app.get("/metrics")
async def metrics() -> dict[str, int]:
    return {
        "enqueued": int(getattr(collector, "enqueued", 0)),
        "processed": int(getattr(collector, "processed", 0)),
        "dropped_oldest": int(getattr(collector, "dropped_oldest", 0)),
        "flush_errors": int(getattr(collector, "flush_errors", 0)),
        "queue_depth": int(getattr(collector, "queue_depth", 0)),
    }


start_stats_writer(
    lambda: {
        "enqueued": int(getattr(collector, "enqueued", 0)),
        "processed": int(getattr(collector, "processed", 0)),
        "dropped_oldest": int(getattr(collector, "dropped_oldest", 0)),
        "flush_errors": int(getattr(collector, "flush_errors", 0)),
        "queue_depth": int(getattr(collector, "queue_depth", 0)),
        "framework": "fastapi",
        "profilis_enabled": bool(cfg.enabled),
    }
)


@app.on_event("shutdown")
async def _dump_collector_stats() -> None:
    payload = await metrics()
    payload["framework"] = "fastapi"
    payload["profilis_enabled"] = bool(cfg.enabled)
    print("BENCH_COLLECTOR " + json.dumps(payload, sort_keys=True))
    collector.close()
