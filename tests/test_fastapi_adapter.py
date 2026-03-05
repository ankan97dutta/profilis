import asyncio
import time
from typing import Any

import pytest
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.testclient import TestClient

from profilis.asgi.middleware import ASGIConfig
from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.fastapi.adapter import instrument_fastapi
from profilis.runtime.context import get_span_id, use_span


def make_collector_sink() -> tuple[AsyncCollector[dict[str, Any]], list[Any]]:
    items: list[Any] = []
    col: AsyncCollector[dict[str, Any]] = AsyncCollector(
        items.extend, queue_size=100, flush_interval=0.02
    )
    return col, items


# Constants for magic numbers
HTTP_OK = 200
HTTP_INTERNAL_SERVER_ERROR = 500
TEST_ITEM_ID = 42
MIN_EXPECTED_HTTP_ITEMS = 3


async def sample_dep() -> str:
    return "dep-val"


def test_fastapi_routes_async_and_background_tasks() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)

    app = FastAPI()

    # APIRouter with path param and dependency to ensure template extraction works
    router = APIRouter(prefix="/api")

    @router.get("/items/{item_id}")
    async def get_item(
        item_id: int, background: BackgroundTasks, dep: str = Depends(sample_dep)
    ) -> dict[str, Any]:
        # schedule a background task that toggles something (no side effects here)
        def bg_job(x: int) -> None:
            # simulate small work
            pass

        background.add_task(bg_job, item_id)

        return {"item_id": item_id, "dep": dep}

    app.include_router(router)

    # Streaming response route
    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def generator() -> Any:
            for i in range(3):
                await asyncio.sleep(0)
                yield f"chunk-{i}\n"

        return StreamingResponse(generator(), media_type="text/plain")

    # simple root route
    @app.get("/")
    async def root() -> PlainTextResponse:
        return PlainTextResponse("root")

    # instrument app
    instrument_fastapi(app, em, ASGIConfig(sampling_rate=1.0, always_sample_errors=True))

    client = TestClient(app)

    # call async endpoint with background task
    r = client.get(f"/api/items/{TEST_ITEM_ID}")
    assert r.status_code == HTTP_OK
    assert r.json()["item_id"] == TEST_ITEM_ID

    # streaming endpoint
    r2 = client.get("/stream")
    assert r2.status_code == HTTP_OK
    assert "chunk-0" in r2.text

    # root
    r3 = client.get("/")
    assert r3.status_code == HTTP_OK

    # wait briefly for collector
    time.sleep(0.05)

    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert len(http_items) >= MIN_EXPECTED_HTTP_ITEMS

    # find the route template for the param route — should be '/api/items/{item_id}' or path_format depending on framework
    assert any("/api/items" in (i.get("route") or i.get("path") or "") for i in http_items)

    col.close()


def test_fastapi_exception_and_span_propagation() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)

    app = FastAPI()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("boom!")

    instrument_fastapi(app, em, ASGIConfig(sampling_rate=0.0, always_sample_errors=True))

    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/boom")

    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(i.get("status") == HTTP_INTERNAL_SERVER_ERROR for i in http_items)

    # test span propagation
    app2 = FastAPI()

    @app2.get("/traced")
    async def traced() -> dict[str, Any]:
        return {"span": get_span_id()}

    instrument_fastapi(app2, em, ASGIConfig(sampling_rate=1.0))
    client2 = TestClient(app2)
    with use_span(trace_id="T1", span_id="S-FAPI"):
        r = client2.get("/traced")
        assert r.status_code == HTTP_OK

    time.sleep(0.05)
    http_items = [i for i in items if isinstance(i, dict) and i.get("kind") == "HTTP"]
    assert any(i.get("parent_span_id") == "S-FAPI" for i in http_items)
    col.close()
