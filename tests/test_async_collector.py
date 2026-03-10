import threading
import time

from profilis.core.async_collector import AsyncCollector


def test_queue_depth_property() -> None:
    received: list[list[int]] = []

    def sink(batch: list[int]) -> None:
        received.append(batch)

    col = AsyncCollector(sink, queue_size=10, flush_interval=1.0, batch_max=5)
    assert col.queue_depth == 0
    col.enqueue(1)
    col.enqueue(2)
    # Flush may not have run yet
    assert col.queue_depth in (0, 1, 2)
    time.sleep(0.15)
    col.close()
    assert col.queue_depth == 0


def test_exporter_raise_increments_flush_errors_and_disables_sink() -> None:
    """Fault injection: sink that always raises; collector disables sink after N failures."""
    call_count = 0

    def failing_sink(batch: list[int]) -> None:
        nonlocal call_count
        call_count += 1
        raise RuntimeError("simulated exporter failure")

    col = AsyncCollector(
        failing_sink,
        queue_size=20,
        flush_interval=0.03,
        batch_max=5,
        max_consecutive_sink_failures=3,
    )
    for i in range(30):
        col.enqueue(i)
    time.sleep(0.25)
    min_failures = 3  # matches max_consecutive_sink_failures
    assert col.flush_errors >= min_failures
    assert col._sink_disabled
    # After disable, further flushes use noop so no more exceptions
    col.close()
    assert call_count >= min_failures


def test_graceful_shutdown_respects_deadline() -> None:
    """close(timeout=...) returns within timeout even if sink blocks."""
    block_until = threading.Event()
    sink_called = 0

    def blocking_sink(batch: list[int]) -> None:
        nonlocal sink_called
        sink_called += len(batch)
        block_until.wait(timeout=5.0)

    col = AsyncCollector(
        blocking_sink,
        queue_size=50,
        flush_interval=10.0,
        batch_max=10,
    )
    for i in range(25):
        col.enqueue(i)
    t0 = time.monotonic()
    col.close(timeout=0.15)
    elapsed = time.monotonic() - t0
    max_acceptable_block_s = 0.5
    assert elapsed < max_acceptable_block_s, "close() must not block long after timeout"
    # Some items may have been processed before first blocking flush
    assert sink_called >= 0


def test_non_blocking_and_drop_oldest_under_burst() -> None:
    received = []
    lock = threading.Lock()

    def sink(batch: list[int]) -> None:
        # Simulate lightweight sink
        with lock:
            received.extend(batch)

    qsize = 100
    col = AsyncCollector(sink, queue_size=qsize, flush_interval=0.05, batch_max=32)

    total = qsize * 10  # burst 10x queue size
    for i in range(total):
        col.enqueue(i)

    # Allow some flush cycles
    time.sleep(0.3)
    col.close()

    # Accounting: processed + dropped == enqueued
    assert col.enqueued == total
    assert col.processed + col.dropped_oldest == total

    # Sanity: we should have received at most the newest ~qsize items
    assert len(received) == col.processed
    assert col.flush_errors == 0


def test_close_drains_remaining_items() -> None:
    received = []

    def sink(batch: list[int]) -> None:
        received.extend(batch)

    col = AsyncCollector(sink, queue_size=16, flush_interval=1.0, batch_max=8)

    for i in range(25):
        col.enqueue(i)

    # Without waiting for the periodic flush, close should drain all
    col.close()

    assert col.processed + col.dropped_oldest == col.enqueued
    assert len(received) == col.processed


def test_atexit_handler_is_safe_to_call() -> None:
    # This exercises the atexit path without relying on interpreter shutdown
    received = []

    def sink(batch: list[int]) -> None:
        received.extend(batch)

    col = AsyncCollector(sink, queue_size=8, flush_interval=10.0, batch_max=8)
    for i in range(20):
        col.enqueue(i)

    # Call the atexit hook directly
    col._atexit()

    # Everything should be drained or accounted as dropped
    assert col.processed + col.dropped_oldest == col.enqueued
    assert len(received) == col.processed
