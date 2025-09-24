# tests/test_neo4j_instrumentation.py
import asyncio
import time
from typing import Any, Union

import pytest

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.neo4j.instrumentation import (
    Neo4jConfig,
    instrument_neo4j_session,
)


class FakeSummary:
    def __init__(self, counters: dict[str, Any]):
        # counters-like object: we can just attach attributes
        self.nodes_created = counters.get("nodes_created")
        self.properties_set = counters.get("properties_set")
        self.contains_updates = counters.get("contains_updates")


class FakeResultSync:
    def __init__(self, summary: Union[FakeSummary, None] = None):
        self._summary = summary

    def summary(self) -> Union[FakeSummary, None]:
        return self._summary


class FakeResultAsync:
    def __init__(self, summary: Union[FakeSummary, None] = None):
        self._summary = summary

    async def summary(self) -> Union[FakeSummary, None]:
        # simulate small awaitable
        await asyncio.sleep(0)
        return self._summary


def make_collector_sink() -> tuple[AsyncCollector[Any], list[Any]]:
    items: list[Any] = []
    col: AsyncCollector[Any] = AsyncCollector(
        lambda b: items.extend(b), queue_size=100, flush_interval=0.02
    )
    return col, items


def test_sync_run_success_records_counters() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = Neo4jConfig(preview_len=120, redact_cypher=False)

    # Create fake session with run that returns FakeResultSync
    class Session:
        def run(self, cypher: str, params: Union[dict[str, Any], None] = None) -> FakeResultSync:
            return FakeResultSync(
                FakeSummary({"nodes_created": 3, "properties_set": 5, "contains_updates": True})
            )

    sess = Session()
    instrument_neo4j_session(sess, em, cfg)

    res = sess.run("CREATE (n:Test) RETURN n", {})
    # call summary to mimic user behaviour
    res.summary()
    time.sleep(0.05)
    assert any(
        isinstance(i, dict)
        and i.get("kind") == "DB_META"
        and i.get("success") is True
        and i.get("counters")
        for i in items
    )
    col.close()


def test_sync_run_exception_emits_error() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = Neo4jConfig()

    class Session:
        def run(self, cypher: str, params: Union[dict[str, Any], None] = None) -> None:
            raise RuntimeError("boom-sync")

    sess = Session()
    instrument_neo4j_session(sess, em, cfg)

    with pytest.raises(RuntimeError):
        sess.run("MATCH (n) RETURN n")
    time.sleep(0.05)
    assert any(
        isinstance(i, dict)
        and i.get("kind") == "DB_META"
        and i.get("success") is False
        and i.get("error")
        for i in items
    )
    col.close()


@pytest.mark.asyncio
async def test_async_run_success_records_counters() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = Neo4jConfig(preview_len=120, redact_cypher=False)

    class AsyncSession:
        async def run(
            self, cypher: str, params: Union[dict[str, Any], None] = None
        ) -> FakeResultAsync:
            return FakeResultAsync(FakeSummary({"nodes_created": 1, "properties_set": 2}))

    sess = AsyncSession()
    instrument_neo4j_session(sess, em, cfg)

    res = await sess.run("CREATE (n) RETURN n", {})
    # call summary coroutine
    await res.summary()
    await asyncio.sleep(0.05)
    assert any(
        isinstance(i, dict)
        and i.get("kind") == "DB_META"
        and i.get("success") is True
        and i.get("counters")
        for i in items
    )
    col.close()


@pytest.mark.asyncio
async def test_async_run_exception_emits_error() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = Neo4jConfig()

    class AsyncSession:
        async def run(self, cypher: str, params: Union[dict[str, Any], None] = None) -> None:
            raise ValueError("boom-async")

    sess = AsyncSession()
    instrument_neo4j_session(sess, em, cfg)

    with pytest.raises(ValueError):
        await sess.run("MATCH (n) RETURN n")
    await asyncio.sleep(0.05)
    assert any(
        isinstance(i, dict)
        and i.get("kind") == "DB_META"
        and i.get("success") is False
        and i.get("error")
        for i in items
    )
    col.close()
