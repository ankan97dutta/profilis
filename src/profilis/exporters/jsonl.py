"""JSONL exporter with size/time-based rotation.

Design:
- Append to an *active* temp file: profilis-active.jsonl.tmp
- On rotation, atomically rename temp -> profilis-YYYYmmdd-HHMMSS.jsonl
- Thread-safe via an internal lock; safe as an AsyncCollector sink by exposing __call__(batch).
- Uses orjson if available; falls back to stdlib json with ensure_ascii=False for unicode safety.
"""

from __future__ import annotations

import contextlib
import errno
import json
import os
import threading
import time
import warnings
from collections.abc import Iterable
from datetime import datetime
from typing import Any, BinaryIO, cast

try:  # optional perf
    import orjson as _orjson
except Exception:  # pragma: no cover
    _orjson = None  # type: ignore[assignment]

__all__ = ["JSONLExporter"]


class JSONLExporter:
    def __init__(
        self,
        dir: str = "./logs",
        *,
        rotate_bytes: int = 10_000_000,  # 10 MB
        rotate_secs: float = 300.0,  # 5 minutes
        prefix: str = "profilis",
        active_name: str = "profilis-active.jsonl.tmp",
    ) -> None:
        self.dir = os.path.abspath(dir)
        self.rotate_bytes = int(rotate_bytes)
        self.rotate_secs = float(rotate_secs)
        self.prefix = prefix
        self.active_name = active_name

        os.makedirs(self.dir, exist_ok=True)

        self._lock = threading.Lock()
        self._fh: BinaryIO | None = None
        self._opened_at = 0.0
        self._bytes = 0
        self._disk_full_noop = False
        self._open_active()

    # -------- sink interface (AsyncCollector calls this) --------
    def __call__(self, batch: Iterable[dict[str, Any]]) -> None:
        self.write_batch(batch)

    # ---------------------------- API ----------------------------
    def write_batch(self, batch: Iterable[dict[str, Any]]) -> None:
        enc = _dumps
        newline = bytes([10])

        with self._lock:
            if self._disk_full_noop:
                return
            try:
                self._maybe_rotate_locked()
                fh = self._fh
                assert fh is not None
                for obj in batch:
                    b = enc(obj)
                    fh.write(b)
                    fh.write(newline)
                    self._bytes += len(b) + 1
                fh.flush()
                self._maybe_rotate_locked()
            except OSError as e:
                if e.errno in (errno.ENOSPC, errno.EDQUOT):
                    self._disk_full_noop = True
                    warnings.warn(
                        "JSONLExporter: disk full (ENOSPC/EDQUOT); writes are now no-op until restart.",
                        UserWarning,
                        stacklevel=0,
                    )
                else:
                    raise

    def close(self) -> None:
        with self._lock:
            if self._fh is not None:
                self._finalize_rotation_locked()  # rename whatever is active
                # _finalize_rotation_locked closes the file

    def finalize(self) -> None:
        """Finalize any pending rotation - useful for collector cleanup."""
        with self._lock:
            if self._fh is not None:
                self._finalize_rotation_locked()

    # ------------------------ Internals -------------------------
    def _active_path(self) -> str:
        return os.path.join(self.dir, self.active_name)

    def _open_active(self) -> None:
        # Open (or create) the active temp file in append-binary mode
        path = self._active_path()
        # Ensure file exists; open in a way that doesn't truncate existing
        self._fh = open(path, "ab", buffering=0)  # noqa: SIM115
        self._opened_at = time.time()
        self._bytes = os.path.getsize(path) if os.path.exists(path) else 0

    def _timestamp_name(self) -> str:
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{self.prefix}-{ts}.jsonl"

    def _should_rotate(self) -> bool:
        if self._fh is None:
            return True
        if self.rotate_bytes > 0 and self._bytes >= self.rotate_bytes:
            return True
        return bool(self.rotate_secs > 0 and time.time() - self._opened_at >= self.rotate_secs)

    def _maybe_rotate_locked(self) -> None:
        if self._should_rotate():
            self._finalize_rotation_locked()
            self._open_active()

    def _finalize_rotation_locked(self) -> None:
        # Close current active and atomically rename it to a timestamped final file
        fh = self._fh
        if fh is None:
            return
        fh.flush()
        os.fsync(fh.fileno())
        fh.close()
        self._fh = None
        src = self._active_path()
        if os.path.exists(src) and os.path.getsize(src) > 0:
            dst = os.path.join(self.dir, self._timestamp_name())
            # os.replace is atomic on POSIX/Windows when same filesystem
            os.replace(src, dst)
        else:
            # Remove empty active file (no events written)
            with contextlib.suppress(FileNotFoundError):
                os.remove(src)
        # Reset counters after rotation
        self._bytes = 0
        self._opened_at = time.time()  # Update timestamp when rotation actually happens


# ---- Encoding helpers ----


def _dumps(obj: dict[str, Any]) -> bytes:
    if _orjson is not None:
        return cast(
            bytes, cast(Any, _orjson).dumps(obj, option=cast(Any, _orjson).OPT_NON_STR_KEYS)
        )  # stdlib fallback: ensure unicode-safe, compact
    s = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)  # type: ignore[unreachable]
    return s.encode("utf-8")
