import asyncio
from typing import Optional

import pytest

from profilis.runtime.context import (
    get_span_id,
    get_trace_id,
    use_span,
)


async def _leaf_expect(trace_id: Optional[str], span_id: Optional[str]) -> None:
    # Values should propagate across awaits
    await asyncio.sleep(0)
    assert get_trace_id() == trace_id
    assert get_span_id() == span_id


async def _child_work(trace_id: Optional[str], span_id: Optional[str]) -> None:
    await _leaf_expect(trace_id, span_id)


def test_context_manager_sets_and_resets_sync() -> None:
    assert get_trace_id() is None and get_span_id() is None
    with use_span(trace_id="t1", span_id="s1"):
        assert get_trace_id() == "t1"
        assert get_span_id() == "s1"
    # Resets after context exit
    assert get_trace_id() is None and get_span_id() is None


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_context_propagation_across_awaits() -> None:
    async def task_one() -> None:
        with use_span("tA", "sA"):
            await _child_work("tA", "sA")

    async def task_two() -> None:
        with use_span("tB", "sB"):
            await _child_work("tB", "sB")

    # Run concurrently; contexts must not leak between tasks
    await asyncio.gather(task_one(), task_two())


@pytest.mark.asyncio  # type: ignore[untyped-decorator]
async def test_context_is_task_local() -> None:
    async def worker(name: str, tval: Optional[str], sval: Optional[str]) -> None:
        with use_span(tval, sval):
            # Sibling task should see its own values
            await asyncio.sleep(0)
            assert get_trace_id() == tval
            assert get_span_id() == sval

    await asyncio.gather(
        worker("A", "tX", "sX"),
        worker("B", "tY", "sY"),
    )
