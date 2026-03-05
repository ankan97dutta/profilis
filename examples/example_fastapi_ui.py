"""
FastAPI example with Profilis built-in UI.

Run:
    uvicorn examples.example_fastapi_ui:app --reload

Visit:
    http://127.0.0.1:8000/ok
    http://127.0.0.1:8000/slow   (variable latency)
    http://127.0.0.1:8000/boom  (simulate error, appears in dashboard)
    http://127.0.0.1:8000/profilis   (Profilis dashboard)
"""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from time import time_ns
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from profilis.core.stats import StatsStore
from profilis.fastapi.ui import ErrorItem, make_ui_router, record_error

# Constants
HTTP_SERVER_ERROR = 500

app = FastAPI(title="Profilis FastAPI UI Demo")
stats = StatsStore()

# Mount the Profilis UI at /profilis (optional: bearer_token="secret" for auth)
ui_router = make_ui_router(stats, prefix="/profilis")
app.include_router(ui_router)


# ------------------- Request timing → StatsStore -------------------
@app.middleware("http")
async def _record_request_timing(
    request: Request, call_next: Callable[[Request], Awaitable[Any]]
) -> Any:
    start_ns = time_ns()
    try:
        response = await call_next(request)
        dur_ns = time_ns() - start_ns
        status = response.status_code if hasattr(response, "status_code") else 200
        stats.record(dur_ns, error=status >= HTTP_SERVER_ERROR)
        return response
    except Exception:
        dur_ns = time_ns() - start_ns
        stats.record(dur_ns, error=True)
        raise


# ------------------- Record exceptions into dashboard error ring -------------------
@app.exception_handler(Exception)
async def _record_exception(request: Request, exc: Exception) -> JSONResponse:
    record_error(
        ErrorItem(
            ts_ns=time_ns(),
            route=request.url.path or "-",
            status=HTTP_SERVER_ERROR,
            exception_type=type(exc).__name__,
            exception_value=repr(exc),
            traceback="",
        )
    )
    # Re-raise so FastAPI returns 500
    return JSONResponse(
        status_code=HTTP_SERVER_ERROR,
        content={"detail": str(exc)},
    )


# ------------------- Demo routes -------------------
@app.get("/ok")
async def ok() -> dict[str, Any]:
    await asyncio.sleep(0.02)  # 20ms
    return {"ok": True}


@app.get("/slow")
async def slow() -> dict[str, Any]:
    await asyncio.sleep(random.uniform(0.2, 0.6))
    return {"slow": True}


@app.get("/boom")
async def boom() -> None:
    raise RuntimeError("demo boom (FastAPI)")


if __name__ == "__main__":
    import uvicorn

    # Run from project root: uvicorn examples.example_fastapi_ui:app --reload
    uvicorn.run(app, host="0.0.0.0", port=8000)
