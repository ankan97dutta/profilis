"""
Demo: Profilis built-in UI with live data.

Run:
  uv run python scripts/demo_ui.py

Open:
  http://127.0.0.1:5000/profilis/?token=secret123   (auth enabled)

What this demo does:
- Registers the built-in UI blueprint at /profilis
- Records *real* per-request latencies into StatsStore using Flask hooks
- Simulates background traffic so the dashboard is not blank when idle
- Records recent errors into the error ring (shown on the dashboard)
"""

from __future__ import annotations

import random
import threading
import time
from time import time_ns
from typing import Union

from flask import Flask, Response, g, jsonify, request

from profilis.core.stats import StatsStore
from profilis.flask.ui import ErrorItem, make_ui_blueprint, record_error

# Constants
HTTP_SERVER_ERROR = 500
ERROR_RATE = 0.1

# ------------------- App + UI setup -------------------
app = Flask(__name__)
stats = StatsStore()  # 15-minute rolling window by default

# Mount UI under /profilis with a demo bearer token
bp = make_ui_blueprint(stats, ui_prefix="/profilis")
app.register_blueprint(bp)


# ------------------- Instrument real requests -------------------
@app.before_request
def _demo_before() -> None:
    g._start_ns = time_ns()


@app.after_request
def _demo_after(response: Response) -> Response:
    start = getattr(g, "_start_ns", None)
    if start is not None:
        dur_ns = time_ns() - start
        is_error = response.status_code >= HTTP_SERVER_ERROR
        stats.record(dur_ns, error=is_error)
    return response


@app.teardown_request
def _demo_teardown(exc: Union[BaseException, None]) -> None:
    if exc is not None:
        # Push into the recent error ring for the dashboard
        try:
            route = request.path or "-"
        except Exception:
            route = "-"
        record_error(
            ErrorItem(
                ts_ns=time_ns(),
                route=route,
                status=HTTP_SERVER_ERROR,
                exception_type=type(exc).__name__,
                exception_value=str(exc),
                traceback="",
            )
        )


# ------------------- Demo routes -------------------
@app.get("/ok")
def ok() -> Response:
    # Simulate light work
    time.sleep(0.02)  # 20ms
    return jsonify({"ok": True})


@app.get("/slow")
def slow() -> Response:
    # Simulate variable latency
    time.sleep(random.uniform(0.2, 0.6))
    return jsonify({"slow": True})


@app.get("/boom")
def boom() -> Response:
    # Simulate a failure that surfaces in the dashboard error table
    raise RuntimeError("demo boom")


# ------------------- Background load generator -------------------
_stop = threading.Event()


def _background_load() -> None:
    rng = random.Random()
    while not _stop.is_set():
        # Generate synthetic events directly into StatsStore to keep charts alive
        dur_ms = rng.choice([5, 10, 15, 30, 60, 120, 250])
        stats.record(int(dur_ms * 1e6), error=(rng.random() < ERROR_RATE))
        time.sleep(0.25)  # 4 samples/sec


def main() -> None:
    t = threading.Thread(target=_background_load, daemon=True)
    t.start()
    try:
        app.run(port=5000, debug=True)
    finally:
        _stop.set()
        t.join(timeout=1)


if __name__ == "__main__":
    main()
