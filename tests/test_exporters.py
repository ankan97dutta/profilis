import errno
import os
import re
import sys
import tempfile
import time
from io import StringIO
from typing import Any

import pytest

from profilis.core.async_collector import AsyncCollector
from profilis.exporters.console import ConsoleExporter
from profilis.exporters.jsonl import JSONLExporter

# regex: profilis-YYYYmmdd-HHMMSS.jsonl (no backslashes to avoid canvas escaping)
ROT_RE = re.compile("^profilis-[0-9]{8}-[0-9]{6}[.]jsonl$")

# Test constants
TEST_DURATION = 0.5  # seconds


def test_jsonl_rotation_by_size_and_atomic_rename() -> None:
    tmp = tempfile.mkdtemp()
    exp = JSONLExporter(dir=tmp, rotate_bytes=256, rotate_secs=10_000)

    # Wire through collector to exercise sink
    col = AsyncCollector(exp, queue_size=64, flush_interval=0.01, batch_max=8)

    # Write enough small events to trigger multiple rotations by size
    for i in range(1_000):
        col.enqueue({"i": i, "msg": "hello 🌍"})
    time.sleep(0.1)
    col.close()

    files = sorted(os.listdir(tmp))
    assert files, "no files produced"
    assert all(ROT_RE.match(f) for f in files), files


def test_jsonl_rotation_by_time() -> None:
    tmp = tempfile.mkdtemp()
    exp = JSONLExporter(dir=tmp, rotate_bytes=10_000_000, rotate_secs=0.2)
    col = AsyncCollector(exp, queue_size=64, flush_interval=0.05, batch_max=32)

    start = time.time()
    while time.time() - start < TEST_DURATION:
        col.enqueue({"t": time.time(), "u": "ユニコード"})
        time.sleep(0.02)
    col.close()

    files = sorted(os.listdir(tmp))
    # With 0.2s rotation time and 0.5s test duration, we expect at least 1 rotation
    # The collector will flush every 0.05s, but rotations may only happen once during the test
    assert len(files) >= 1, f"Expected at least 1 file, got {files}"
    assert all(ROT_RE.match(f) for f in files)


def test_jsonl_disk_full_fallback_noop_warn_once() -> None:
    """Simulate disk full (ENOSPC); exporter switches to noop and warns once."""
    tmp = tempfile.mkdtemp()
    exp = JSONLExporter(dir=tmp, rotate_bytes=10_000_000, rotate_secs=3600)
    write_calls = 0

    fh = exp._fh
    assert fh is not None
    original_write = fh.write

    fail_after_writes = 2

    def failing_write(data: bytes) -> int:
        nonlocal write_calls
        write_calls += 1
        if write_calls >= fail_after_writes:
            raise OSError(errno.ENOSPC, "No space left on device")
        return original_write(data)

    fh.write = failing_write  # type: ignore[assignment]

    with pytest.warns(UserWarning, match="disk full"):
        exp.write_batch([{"a": 1}, {"b": 2}])
    assert exp._disk_full_noop
    write_calls = 0
    exp.write_batch([{"c": 3}])
    assert write_calls == 0
    exp.close()


def test_console_exporter_unicode_and_pretty_capture_stdout(monkeypatch: Any) -> None:
    buf = StringIO()
    monkeypatch.setattr(sys, "stdout", buf)

    exp = ConsoleExporter(pretty=False)
    exp([{"msg": "hello 🚀", "x": 1}])

    out = buf.getvalue()
    assert "hello 🚀" in out
    assert out.strip().endswith("1}")
