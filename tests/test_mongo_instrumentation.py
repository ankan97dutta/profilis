# tests/test_mongo_instrumentation.py
import time
from typing import Any

from profilis.core.async_collector import AsyncCollector
from profilis.core.emitter import Emitter
from profilis.mongo.instrumentation import MongoConfig, ProfilisCommandListener


# Minimal fake event classes resembling pymongo.monitoring events
class FakeStarted:
    def __init__(
        self,
        request_id: int,
        database_name: str,
        command_name: str,
        command: dict[str, Any],
    ) -> None:
        self.request_id = request_id
        self.database_name = database_name
        self.command_name = command_name
        self.command = command


class FakeSucceeded:
    def __init__(
        self,
        request_id: int,
        database_name: str,
        command_name: str,
        command: dict[str, Any],
        reply: dict[str, Any],
    ) -> None:
        self.request_id = request_id
        self.database_name = database_name
        self.command_name = command_name
        self.command = command
        self.reply = reply


class FakeFailed:
    def __init__(
        self,
        request_id: int,
        database_name: str,
        command_name: str,
        command: dict[str, Any],
        **kwargs: Any,
    ) -> None:
        self.request_id = request_id
        self.database_name = database_name
        self.command_name = command_name
        self.command = command
        self.failure = kwargs.get("failure")
        self.reply = kwargs.get("reply")


def make_collector_sink() -> tuple[AsyncCollector[dict[str, Any]], list[Any]]:
    items: list[Any] = []
    col: AsyncCollector[dict[str, Any]] = AsyncCollector[dict[str, Any]](
        lambda b: items.extend(b), queue_size=100, flush_interval=0.02
    )
    return col, items


def test_successed_instrumentation_records_meta() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = MongoConfig(preview_len=120, redact_collection=False)
    listener = ProfilisCommandListener(em, cfg)

    req_id = 1
    started = FakeStarted(req_id, "mydb", "find", {"find": "users", "filter": {"x": 1}})
    listener.started(started)  # type: ignore[arg-type]
    # simulate some time
    time.sleep(0.01)
    succeeded = FakeSucceeded(
        req_id, "mydb", "find", {"find": "users"}, {"cursor": {"firstBatch": [1, 2, 3]}}
    )
    listener.succeeded(succeeded)  # type: ignore[arg-type]
    # wait for collector
    time.sleep(0.05)
    assert any(
        isinstance(i, dict) and i.get("kind") == "DB_META" and i.get("success") is True
        for i in items
    )
    col.close()


def test_failed_instrumentation_records_error() -> None:
    col, items = make_collector_sink()
    em = Emitter(col)
    cfg = MongoConfig(preview_len=80, redact_collection=True)
    listener = ProfilisCommandListener(em, cfg)

    req_id = 5
    started = FakeStarted(req_id, "sales", "update", {"update": "orders", "updates": []})
    listener.started(started)  # type: ignore[arg-type]
    time.sleep(0.005)
    failed = FakeFailed(
        req_id,
        "sales",
        "update",
        {"update": "orders"},
        failure=Exception("boom"),
        reply={"errmsg": "something"},
    )
    listener.failed(failed)  # type: ignore[arg-type]
    time.sleep(0.05)
    assert any(
        isinstance(i, dict)
        and i.get("kind") == "DB_META"
        and i.get("success") is False
        and i.get("error")
        for i in items
    )
    col.close()
