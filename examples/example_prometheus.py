"""
Flask example with Prometheus exporter: /metrics and composite sink.

Run (requires profilis[prometheus,flask]):
    pip install -e ".[prometheus,flask]"
    FLASK_APP=examples.example_prometheus flask run

Visit:
    http://127.0.0.1:5000/ok
    http://127.0.0.1:5000/slow
    http://127.0.0.1:5000/metrics   (Prometheus scrape endpoint)

For ASGI (e.g. Starlette/FastAPI), mount the metrics app:
    from profilis.exporters.prometheus import make_asgi_app
    app.mount("/metrics", make_asgi_app(registry))
"""

from __future__ import annotations

import time
from typing import Any

from flask import Flask

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.exporters.console import ConsoleExporter
from profilis.exporters.prometheus import (
    PrometheusExporter,
    make_metrics_blueprint,
    register_collector_health_metrics,
)
from profilis.flask.adapter import ProfilisFlask

# ------------------- Prometheus registry + composite sink -------------------
try:
    from prometheus_client import CollectorRegistry
except ImportError:
    raise SystemExit("Install Prometheus support: pip install profilis[prometheus,flask]") from None

registry = CollectorRegistry()
console = ConsoleExporter(pretty=False)
prom = PrometheusExporter(
    registry,
    service="example-app",
    instance="localhost:5000",
    worker="",
)


def sink(batch: list[dict[str, Any]]) -> None:
    console(batch)
    prom(batch)


collector = AsyncCollector(sink, queue_size=256, flush_interval=0.2, batch_max=64)
register_collector_health_metrics(registry, collector)
emitter = Emitter(collector)

# ------------------- Flask app -------------------
app = Flask(__name__)
ProfilisFlask(
    app,
    collector=collector,
    exclude_routes=["/metrics"],
    sample=1.0,
)
app.register_blueprint(make_metrics_blueprint(registry))


# ------------------- Routes -------------------
@app.get("/ok")
def ok() -> str:
    return "ok"


@app.get("/slow")
def slow() -> str:
    time.sleep(0.05)
    return "slow"


if __name__ == "__main__":
    app.run(port=5000, debug=True)
