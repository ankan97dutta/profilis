"""Shared UI core: error ring and ErrorItem (framework-agnostic)."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass


@dataclass
class ErrorItem:
    ts_ns: int
    route: str
    status: int
    exception_type: str | None
    exception_value: str
    traceback: str


class _ErrorRing:
    def __init__(self, maxlen: int = 200) -> None:
        self._buf: deque[ErrorItem] = deque(maxlen=maxlen)

    def record(self, item: ErrorItem) -> None:
        self._buf.append(item)

    def dump(self) -> list[dict[str, str | int | None]]:
        return [asdict(x) for x in list(self._buf)][-50:]


# Singleton-ish registry (simple module-level reference)
_ERROR_RING: _ErrorRing | None = _ErrorRing(maxlen=500)


def get_error_ring() -> _ErrorRing | None:
    return _ERROR_RING


def record_error(item: ErrorItem) -> None:
    ring = get_error_ring()
    if ring:
        ring.record(item)
