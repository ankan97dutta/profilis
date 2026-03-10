"""
ASGI (FastAPI) example with Prometheus exporter: /metrics and composite sink.

Run (requires profilis[prometheus,fastapi]):
    pip install -e ".[prometheus,fastapi]"
    uvicorn examples.example_prometheus_asgi:app --reload

Visit:
    http://127.0.0.1:8000/ok
    http://127.0.0.1:8000/slow
    http://127.0.0.1:8000/metrics   (Prometheus scrape endpoint)
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

from fastapi import FastAPI

from profilis.asgi.middleware import ASGIConfig
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.console import ConsoleExporter
from profilis.exporters.prometheus import PrometheusExporter, make_asgi_app
from profilis.fastapi.adapter import instrument_fastapi

# ------------------- Prometheus registry + composite sink -------------------
try:
    from prometheus_client import CollectorRegistry
except ImportError:
    raise SystemExit(
        "Install Prometheus support: pip install profilis[prometheus,fastapi]"
    ) from None

registry = CollectorRegistry()
console = ConsoleExporter(pretty=False)
prom = PrometheusExporter(
    registry,
    service="example-asgi",
    instance="localhost:8000",
    worker="",
)


def sink(batch: list[dict[str, Any]]) -> None:
    console(batch)
    prom(batch)


collector = AsyncCollector(sink, queue_size=256, flush_interval=0.2, batch_max=64)
emitter = Emitter(collector)

# ------------------- FastAPI app -------------------
app = FastAPI(title="Profilis ASGI + Prometheus")

instrument_fastapi(
    app,
    emitter=emitter,
    config=ASGIConfig(sampling_rate=1.0, always_sample_errors=True),
    route_excludes=["/metrics"],
)
app.mount("/metrics", make_asgi_app(registry))


# ------------------- Routes -------------------
@app.get("/ok")
async def ok() -> dict[str, str]:
    await asyncio.sleep(0.02)
    return {"status": "ok"}


@app.get("/slow")
async def slow() -> dict[str, str]:
    await asyncio.sleep(random.uniform(0.05, 0.15))
    return {"status": "slow"}


@app.on_event("shutdown")
async def shutdown() -> None:
    collector.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
