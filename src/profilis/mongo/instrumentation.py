# src/profilis/mongo/instrumentation.py
"""MongoDB instrumentation (PyMongo + Motor) via pymongo.monitoring.CommandListener.

Records CommandStarted, CommandSucceeded and CommandFailed events and emits
DB_META-like payloads via the provided Emitter.
"""

from __future__ import annotations

import contextlib
from typing import Any

try:
    # pymongo types (available if pymongo is installed)
    from pymongo.monitoring import (
        CommandFailedEvent,
        CommandListener,
        CommandStartedEvent,
        CommandSucceededEvent,
    )
except Exception:  # pragma: no cover - typing fallback for tests without pymongo installed
    CommandListener = object  # type: ignore[assignment]
    CommandStartedEvent = object  # type: ignore[assignment]
    CommandSucceededEvent = object  # type: ignore[assignment]
    CommandFailedEvent = object  # type: ignore[assignment]

from profilis.core.emitter import Emitter
from profilis.runtime import now_ns


class MongoConfig:
    def __init__(
        self,
        *,
        vendor_label: str = "mongodb",
        preview_len: int = 160,
        redact_collection: bool = False,
    ) -> None:
        self.vendor_label = vendor_label
        self.preview_len = int(preview_len)
        self.redact_collection = bool(redact_collection)


def _preview_target(event: Any, max_len: int, redact_collection: bool) -> str:
    """Build preview like "<find> db.collection" with optional redaction."""
    try:
        cmd_name = (
            getattr(event, "command_name", None)
            or getattr(event, "command", {}).get("find")
            or "<cmd>"
        )
        db_name = getattr(event, "database_name", "") or ""
        # Try to get collection name: many commands include collection as top-level key or in command document
        collection = ""
        cmd_doc = getattr(event, "command", None) or {}
        if isinstance(cmd_doc, dict):
            # common keys: 'find', 'insert', 'update', 'delete', 'aggregate'
            for k in ("find", "insert", "update", "delete", "aggregate"):
                v = cmd_doc.get(k)
                if v:
                    # for aggregate, collection is often in 'aggregate' but sometimes pipeline used; fallback to first stage
                    if isinstance(v, str):
                        collection = v
                    elif isinstance(v, dict):
                        # sometimes command value is document with 'find' options
                        collection = v.get("collection") or ""
                    # for aggregate, v may be the collection name; else try command.get('pipeline')
                    if collection:
                        break
            # Some commands specify 'ns' or have 'collection' keys
            if not collection:
                collection = cmd_doc.get("collection") or cmd_doc.get("ns") or ""
        if redact_collection and collection:
            collection = "?"
        target = f"<{cmd_name}> {db_name}.{collection if collection else '<unknown>'}"
        if len(target) > max_len:
            return target[: max_len - 1] + "…"
        return target
    except Exception:
        return "<unserializable-target>"


def _extract_counters(reply: Any) -> dict[str, Any]:
    """From reply document, extract known counters if present."""
    if not isinstance(reply, dict):
        return {}
    out = {}
    for key in (
        "n",
        "nModified",
        "nMatched",
        "nInserted",
        "nRemoved",
        "ok",
        "writeErrors",
    ):
        if key in reply:
            out[key] = reply.get(key)
    # Some replies embed "cursor" with "firstBatch" length for find
    cursor = reply.get("cursor")
    if isinstance(cursor, dict) and "firstBatch" in cursor:
        out.setdefault("firstBatch_len", len(cursor.get("firstBatch", [])))
    return out


class ProfilisCommandListener(CommandListener):
    """A CommandListener that emits DB_META items via an Emitter.

    Usage:
        listener = ProfilisCommandListener(emitter, MongoConfig(...))
        client = MongoClient(..., event_listeners=[listener])  # sync PyMongo
        # or for Motor:
        client = AsyncIOMotorClient(..., event_listeners=[listener])  # async Motor
    """

    def __init__(self, emitter: Emitter, config: MongoConfig | None = None) -> None:
        self._emitter = emitter
        self._cfg = config or MongoConfig()
        # In-flight map: request_id -> start_ts_ns
        self._inflight: dict[int, int] = {}

    def started(self, event: CommandStartedEvent) -> None:
        try:
            req_id = getattr(event, "request_id", None)
            if req_id is None:
                return
            self._inflight[req_id] = now_ns()
        except Exception:
            # never throw from instrumentation
            return

    def succeeded(self, event: CommandSucceededEvent) -> None:
        req_id = getattr(event, "request_id", None)
        start = self._inflight.pop(req_id) if req_id is not None else None
        dur = (now_ns() - start) if start is not None else -1
        try:
            target = _preview_target(event, self._cfg.preview_len, self._cfg.redact_collection)
            counters = _extract_counters(getattr(event, "reply", {}) or {})
            meta = {
                "kind": "DB_META",
                "vendor": self._cfg.vendor_label,
                "command": getattr(event, "command_name", None) or "<unknown>",
                "target": target,
                "success": True,
                "counters": counters,
                "dur_ns": dur,
                "ts_ns": now_ns(),
            }
            # Emit a short metric (like other adapters) and enqueue the meta
            with contextlib.suppress(Exception):
                # Keep compatibility with previous Emitter.emit_db(stmt, dur_ns, rows)
                # rows unknown for Mongo; supply -1
                self._emitter.emit_db(target, dur_ns=dur, rows=-1)
            with contextlib.suppress(Exception):
                self._emitter._collector.enqueue(meta)
        except Exception:
            # swallow errors to avoid breaking app
            return

    def failed(self, event: CommandFailedEvent) -> None:
        req_id = getattr(event, "request_id", None)
        start = self._inflight.pop(req_id) if req_id is not None else None
        dur = (now_ns() - start) if start is not None else -1
        try:
            target = _preview_target(event, self._cfg.preview_len, self._cfg.redact_collection)
            # Extract exception info; CommandFailedEvent contains 'failure' attribute and 'command_name'
            exc_info = None
            # some event implementations contain .failure (an exception instance) or .failure_details
            failure = getattr(event, "failure", None) or getattr(event, "failure_details", None)
            if failure is not None:
                try:
                    exc_info = {"repr": repr(failure), "str": str(failure)}
                except Exception:
                    exc_info = {"repr": "<unserializable-failure>"}
            else:
                # fallback: try to extract error document from event
                reply = getattr(event, "reply", None) or {}
                if isinstance(reply, dict) and "errmsg" in reply:
                    exc_info = {"errmsg": str(reply.get("errmsg", ""))}
            meta = {
                "kind": "DB_META",
                "vendor": self._cfg.vendor_label,
                "command": getattr(event, "command_name", None) or "<unknown>",
                "target": target,
                "success": False,
                "error": exc_info,
                "dur_ns": dur,
                "ts_ns": now_ns(),
            }
            with contextlib.suppress(Exception):
                self._emitter.emit_db(target, dur_ns=dur, rows=-1)
            with contextlib.suppress(Exception):
                self._emitter._collector.enqueue(meta)
        except Exception:
            return
