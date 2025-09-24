# src/profilis/neo4j/instrumentation.py
"""Neo4j instrumentation (sync + async) — wraps Session.run / Tx.run and AsyncSession.run / AsyncTx.run.

Non-invasive: wraps session/transaction instance methods to preserve semantics.
Emits metrics via Emitter and enqueues DB_META payloads with counters from summary.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
from typing import Any, Callable, Union

from profilis.core.emitter import Emitter
from profilis.runtime import now_ns

# Attempt to reuse existing redact helper if available in repo
try:
    from profilis.sqlalchemy.instrumentation import redact_statement as _redact
except Exception:

    def _redact(s: Union[str, None], max_len: int = 200) -> str:
        if s is None:
            return ""
        s2 = " ".join(str(s).split())
        return s2[: max_len - 1] + "…" if len(s2) > max_len else s2


# Tracing helper: try to import a repo-level 'tracing' util that exposes current_span or parent id
try:
    from profilis.runtime import get_current_parent_span_id
except Exception:

    def get_current_parent_span_id() -> Union[str, None]:
        return None


class Neo4jConfig:
    def __init__(
        self,
        *,
        vendor_label: str = "neo4j",
        preview_len: int = 200,
        redact_cypher: bool = True,
    ) -> None:
        self.vendor_label = vendor_label
        self.preview_len = int(preview_len)
        self.redact_cypher = bool(redact_cypher)


def _extract_counters_from_summary(summary: Any) -> dict[str, Any]:
    """Best-effort extraction of counters from a result.summary() or summary-like object.

    Neo4j summary object (from bolt driver) exposes 'counters' with attributes:
      nodes_created, nodes_deleted, relationships_created, relationships_deleted,
      properties_set, labels_added, labels_removed, indexes_added, indexes_removed, constraints_added, constraints_removed
    We'll attempt to read these attributes if present.
    """
    if summary is None:
        return {}
    # Some driver results return summary() method; others already provide summary attribute
    s = None
    try:
        if hasattr(summary, "counters") or hasattr(summary, "server") or hasattr(summary, "query"):
            s = (
                summary.counters
                if hasattr(summary, "counters")
                else getattr(summary, "summary", None)
            )
    except Exception:
        s = None

    counters = {}
    if s is None:
        # Maybe user passed the counters object directly
        s = summary
    # defensive attribute reads
    for attr in (
        "nodes_created",
        "nodes_deleted",
        "relationships_created",
        "relationships_deleted",
        "properties_set",
        "labels_added",
        "labels_removed",
        "indexes_added",
        "indexes_removed",
        "constraints_added",
        "constraints_removed",
        "contains_updates",
        "contains_system_updates",
    ):
        try:
            val = getattr(s, attr, None)
            if val is not None:
                counters[attr] = val
        except Exception:
            continue
    return counters


def _build_preview(cypher: Any, cfg: Neo4jConfig) -> str:
    try:
        s = str(cypher)
        if cfg.redact_cypher:
            return _redact(s, max_len=cfg.preview_len)
        return s[: cfg.preview_len - 1] + "…" if len(s) > cfg.preview_len else s
    except Exception:
        return "<unserializable-cypher>"


def _wrap_sync_callable(
    orig: Callable[..., Any], emitter: Emitter, cfg: Neo4jConfig
) -> Callable[..., Any]:
    """Wrap a sync callable (Session.run / Tx.run)."""

    @functools.wraps(orig)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # cypher is typically first arg (query), parameters may be second
        cypher = args[0] if len(args) > 0 else kwargs.get("query") or kwargs.get("cypher")
        params = args[1] if len(args) > 1 else kwargs.get("parameters") or kwargs.get("params")
        start = now_ns()
        exc = None
        try:
            result = orig(*args, **kwargs)
            return result
        except Exception as e:
            exc = e
            raise
        finally:
            dur = now_ns() - start
            stmt_preview = _build_preview(cypher, cfg)
            # try to extract counters from result summary when available (best-effort)
            counters = {}
            try:
                # If the result object (from session.run) supports summary(), attempt to call it
                # But don't call on failure path (could be None)
                if exc is None and "result" in locals():
                    res = locals().get("result")
                    # if result has summary() callable and it won't block
                    if res is not None and hasattr(res, "summary") and callable(res.summary):
                        try:
                            summary = res.summary()
                            counters = _extract_counters_from_summary(summary)
                        except Exception:
                            counters = {}
            except Exception:
                counters = {}

            parent_span_id = None
            try:
                parent_span_id = get_current_parent_span_id()
            except Exception:
                parent_span_id = None

            meta = {
                "kind": "DB_META",
                "vendor": cfg.vendor_label,
                "db_system": "neo4j",
                "query": stmt_preview,
                "params_preview": "[redacted]" if params else "[]",
                "dur_ns": dur,
                "success": exc is None,
                "counters": counters,
                "error": {"type": type(exc).__name__, "repr": repr(exc)}
                if exc is not None
                else None,
                "parent_span_id": parent_span_id,
                "ts_ns": now_ns(),
            }
            with contextlib.suppress(Exception):
                emitter.emit_db(stmt_preview, dur_ns=dur, rows=-1)
            with contextlib.suppress(Exception):
                emitter._collector.enqueue(meta)

    return wrapper


def _wrap_async_callable(
    orig: Callable[..., Any], emitter: Emitter, cfg: Neo4jConfig
) -> Callable[..., Any]:
    """Wrap an async callable (AsyncSession.run / AsyncTx.run)."""

    @functools.wraps(orig)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        cypher = args[0] if len(args) > 0 else kwargs.get("query") or kwargs.get("cypher")
        params = args[1] if len(args) > 1 else kwargs.get("parameters") or kwargs.get("params")
        start = now_ns()
        exc = None
        try:
            result = await orig(*args, **kwargs)
            return result
        except Exception as e:
            exc = e
            raise
        finally:
            dur = now_ns() - start
            stmt_preview = _build_preview(cypher, cfg)
            counters = {}
            try:
                # Some async result objects expose summary() coroutine or attribute
                res = locals().get("result")
                if res is not None:
                    # if summary is coroutine function
                    summary_attr = getattr(res, "summary", None)
                    if callable(summary_attr):
                        try:
                            # Try calling; if it's coroutine, await it
                            maybe = summary_attr()
                            if inspect.isawaitable(maybe):
                                summary = await maybe
                            else:
                                summary = maybe
                            counters = _extract_counters_from_summary(summary)
                        except Exception:
                            counters = {}
            except Exception:
                counters = {}

            parent_span_id = None
            try:
                parent_span_id = get_current_parent_span_id()
            except Exception:
                parent_span_id = None

            meta = {
                "kind": "DB_META",
                "vendor": cfg.vendor_label,
                "db_system": "neo4j",
                "query": stmt_preview,
                "params_preview": "[redacted]" if params else "[]",
                "dur_ns": dur,
                "success": exc is None,
                "counters": counters,
                "error": {"type": type(exc).__name__, "repr": repr(exc)}
                if exc is not None
                else None,
                "parent_span_id": parent_span_id,
                "ts_ns": now_ns(),
            }
            with contextlib.suppress(Exception):
                emitter.emit_db(stmt_preview, dur_ns=dur, rows=-1)
            with contextlib.suppress(Exception):
                emitter._collector.enqueue(meta)

    return wrapper


def instrument_neo4j_session(
    session: Any, emitter: Emitter, config: Union[Neo4jConfig, None] = None
) -> Any:
    """Wrap the session (or tx) instance so that its run() is instrumented.

    Non-invasive: we only wrap methods on the given instance and set a marker
    attribute `_profilis_wrapped` to avoid double-wrapping.
    """
    cfg = config or Neo4jConfig()
    if getattr(session, "_profilis_wrapped", False):
        return session
    session._profilis_wrapped = True

    # Candidates: session.run, session.begin_transaction / session.begin_tx / tx.run
    for attr in ("run", "begin_transaction", "begin_tx", "begin"):
        orig = getattr(session, attr, None)
        if orig is None:
            continue
        # wrap only callables
        if not callable(orig):
            continue
        # For the 'run' method, decide sync vs async by inspecting whether it's coroutinefunction
        if attr == "run":
            if inspect.iscoroutinefunction(orig):
                session.run = _wrap_async_callable(orig, emitter, cfg)
            else:
                session.run = _wrap_sync_callable(orig, emitter, cfg)
        else:
            # For begin/transaction creating functions, we leave them but instrument tx objects later
            # wrap them to instrument returned transaction objects if they return an instance with run()
            @functools.wraps(orig)  # type: ignore[arg-type]
            def begin_wrap(*a: Any, __orig=orig, **kw: Any) -> Any:  # type: ignore[no-untyped-def]
                tx = __orig(*a, **kw)
                with contextlib.suppress(Exception):
                    instrument_neo4j_session(tx, emitter, cfg)
                return tx

            setattr(session, attr, begin_wrap)

    # Also try to instrument a tx property if present (some drivers return tx object with run)
    tx = getattr(session, "transaction", None)
    if tx is not None:
        with contextlib.suppress(Exception):
            instrument_neo4j_session(tx, emitter, cfg)

    return session


def instrument_neo4j_module(
    module: Any, emitter: Emitter, config: Union[Neo4jConfig, None] = None
) -> None:
    """Optional convenience: instrument factory functions so newly-created sessions are instrumented.

    Example:
        instrument_neo4j_module(neo4j, emitter, cfg)
        driver = neo4j.GraphDatabase.driver(...)
        session = driver.session()  # session.run will be instrumented
    """
    cfg = config or Neo4jConfig()
    # Wrap GraphDatabase.driver and driver's session factory if available
    with contextlib.suppress(Exception):
        graphdb = getattr(module, "GraphDatabase", None)
        if graphdb is not None and hasattr(graphdb, "driver"):
            orig_driver = graphdb.driver

            @functools.wraps(orig_driver)  # type: ignore[arg-type]
            def driver_wrap(*args: Any, **kwargs: Any) -> Any:
                drv = orig_driver(*args, **kwargs)
                # instrument driver.session method
                orig_session = getattr(drv, "session", None)
                if orig_session and callable(orig_session):

                    @functools.wraps(orig_session)  # type: ignore[arg-type]
                    def session_wrap(*a: Any, __orig=orig_session, **kw: Any) -> Any:  # type: ignore[no-untyped-def]
                        sess = __orig(*a, **kw)
                        with contextlib.suppress(Exception):
                            instrument_neo4j_session(sess, emitter, cfg)
                        return sess

                    drv.session = session_wrap
                return drv

            graphdb.driver = driver_wrap
