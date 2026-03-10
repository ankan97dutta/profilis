"""AsyncCollector: bounded, drop-oldest queue with background batch writer.

- Non-blocking enqueue (drops oldest when full)
- Background writer thread batches and flushes to a provided sink
- atexit handler drains remaining items
- Graceful shutdown: best-effort flush with timeout; never blocks exit beyond timeout
- Collector crash handling: after consecutive sink failures, sink is disabled (noop)

Configuration:
- queue_size (int): max buffer size (default 2048)
- flush_interval (float): seconds between periodic flush attempts (default 0.5s)
- batch_max (int): maximum batch size per sink call (default 256)
- max_consecutive_sink_failures (int): after this many failures, disable sink (default 5)
"""

from __future__ import annotations

import atexit
import contextlib
import threading
import time
import warnings
from collections import deque
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

__all__ = ["AsyncCollector"]


def _noop_sink(batch: list[object]) -> None:
    """No-op sink used when the real sink is disabled after repeated failures."""
    pass


class AsyncCollector(Generic[T]):
    def __init__(  # noqa: PLR0913
        self,
        sink: Callable[[list[T]], None],
        *,
        queue_size: int = 2048,
        flush_interval: float = 0.5,
        batch_max: int = 256,
        name: str = "profilis-collector",
        max_consecutive_sink_failures: int = 5,
    ) -> None:
        if queue_size <= 0:
            raise ValueError("queue_size must be > 0")
        if batch_max <= 0:
            raise ValueError("batch_max must be > 0")
        if flush_interval <= 0:
            raise ValueError("flush_interval must be > 0")
        if max_consecutive_sink_failures < 1:
            raise ValueError("max_consecutive_sink_failures must be >= 1")

        self._sink = sink
        self._original_sink = sink
        self._buf: deque[T] = deque()
        self._max = int(queue_size)
        self._batch_max = int(batch_max)
        self._interval = float(flush_interval)
        self._max_consecutive_failures = int(max_consecutive_sink_failures)

        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)

        # Stats (best-effort; not locked on read)
        self.enqueued = 0
        self.processed = 0
        self.dropped_oldest = 0
        self.flush_errors = 0
        self._consecutive_failures = 0
        self._sink_disabled = False

        # Start worker and register atexit
        self._thread.start()
        atexit.register(self._atexit)

    @property
    def queue_depth(self) -> int:
        """Current number of items in the buffer (thread-safe)."""
        with self._lock:
            return len(self._buf)

    # -------------------------- Public API --------------------------
    def enqueue(self, item: T) -> None:
        """Non-blocking enqueue.

        If the buffer is full, drop the oldest item and append the new one.
        This method never blocks on back-pressure.
        """
        with self._lock:
            if len(self._buf) >= self._max:
                # Drop-oldest
                try:
                    self._buf.popleft()
                    self.dropped_oldest += 1
                except IndexError:
                    # Very unlikely race if another thread drained; ignore
                    pass
            self._buf.append(item)
            self.enqueued += 1
        # Nudge the writer to flush sooner
        self._wakeup.set()

    def close(self, *, timeout: float = 2.0) -> None:
        """Stop the background thread and best-effort flush with timeout; never block exit beyond timeout."""
        if not self._stop.is_set():
            self._stop.set()
            self._wakeup.set()
            deadline = time.monotonic() + timeout
            self._thread.join(timeout=timeout)
            # Best-effort drain within remaining time; never block beyond deadline
            remaining = deadline - time.monotonic()
            if remaining > 0:
                self._drain_all(deadline=deadline)
            # Close the original sink if it has a close method
            _sink = self._original_sink
            if _sink is not None and _sink is not _noop_sink and hasattr(_sink, "close"):
                with contextlib.suppress(Exception):
                    _sink.close()
            if _sink is not None and _sink is not _noop_sink and hasattr(_sink, "finalize"):
                with contextlib.suppress(Exception):
                    _sink.finalize()

    # ------------------------- Internal ----------------------------
    def _atexit(self) -> None:
        # atexit safety: try to stop and drain without raising
        with contextlib.suppress(Exception):
            self.close()

    def _run(self) -> None:
        interval = self._interval
        while not self._stop.is_set():
            self._wakeup.wait(timeout=interval)
            self._wakeup.clear()
            if self._sink_disabled:
                # Still drain the queue so we don't grow unbounded; sink is noop
                self._flush_batches()
                continue
            try:
                self._flush_batches()
                self._consecutive_failures = 0
            except Exception:
                self.flush_errors += 1
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._max_consecutive_failures:
                    self._sink_disabled = True
                    self._sink = _noop_sink  # type: ignore[assignment]
                    warnings.warn(
                        f"AsyncCollector disabled sink after {self._consecutive_failures} "
                        "consecutive failures; events will be dropped until restart.",
                        UserWarning,
                        stacklevel=0,
                    )
                time.sleep(min(0.05, interval))

    def _pop_many(self, n: int) -> list[T]:
        items: list[T] = []
        with self._lock:
            for _ in range(min(n, len(self._buf))):
                try:
                    items.append(self._buf.popleft())
                except IndexError:
                    break
        return items

    def _flush_batches(self) -> None:
        batch_max = self._batch_max
        while True:
            batch = self._pop_many(batch_max)
            if not batch:
                return
            self._sink(batch)  # type: ignore[arg-type]
            self.processed += len(batch)

    def _drain_all(self, *, deadline: float | None = None) -> None:
        """Drain buffer to sink; if deadline is set, stop when past deadline to avoid blocking exit."""
        batch_max = self._batch_max * 4
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                break
            batch = self._pop_many(batch_max)
            if not batch:
                break
            try:
                self._sink(batch)  # type: ignore[arg-type]
                self.processed += len(batch)
            except Exception:
                self.flush_errors += 1
