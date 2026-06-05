"""SQLite-backed store for query run traces."""

from __future__ import annotations

import os
import json
import sqlite3
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional
from uuid import uuid4

from src.core.config import get_settings
from src.core.graph_store_schema import get_graph_db_path


STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
DEFAULT_MAX_QUERY_TRACE_RUNS = 200
_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS query_runs (
        run_id TEXT PRIMARY KEY,
        status TEXT NOT NULL,
        question TEXT,
        top_k INTEGER NOT NULL DEFAULT 0,
        include_sources INTEGER NOT NULL DEFAULT 1,
        session_id TEXT,
        strategy TEXT,
        retrieval_mode TEXT,
        llm_provider TEXT,
        llm_model TEXT,
        llm_duration_ms INTEGER NOT NULL DEFAULT 0,
        processing_time_ms INTEGER NOT NULL DEFAULT 0,
        layer_requested TEXT,
        layer_used TEXT,
        layer_fallback_chain TEXT,
        context_token_estimate INTEGER NOT NULL DEFAULT 0,
        layer_build_duration_ms INTEGER NOT NULL DEFAULT 0,
        entities_count INTEGER NOT NULL DEFAULT 0,
        source_hit_count INTEGER NOT NULL DEFAULT 0,
        community_hit_count INTEGER NOT NULL DEFAULT 0,
        failure_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_query_runs_created_at
    ON query_runs(created_at DESC, run_id DESC)
    """,
)
_SCHEMA_COMPAT_COLUMNS = (
    ("layer_requested", "ALTER TABLE query_runs ADD COLUMN layer_requested TEXT"),
    ("layer_used", "ALTER TABLE query_runs ADD COLUMN layer_used TEXT"),
    ("layer_fallback_chain", "ALTER TABLE query_runs ADD COLUMN layer_fallback_chain TEXT"),
    ("context_token_estimate", "ALTER TABLE query_runs ADD COLUMN context_token_estimate INTEGER NOT NULL DEFAULT 0"),
    ("layer_build_duration_ms", "ALTER TABLE query_runs ADD COLUMN layer_build_duration_ms INTEGER NOT NULL DEFAULT 0"),
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalize_non_negative_int(value: Any, default: int = 0) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, normalized)


def _normalize_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_fallback_chain(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = [value]
    else:
        parsed = value

    if not isinstance(parsed, list):
        return None

    normalized: list[str] = []
    for item in parsed:
        text = _normalize_optional_str(item)
        if text is not None:
            normalized.append(text)
    return normalized


def _serialize_fallback_chain(value: list[str] | None) -> str | None:
    normalized = _normalize_fallback_chain(value)
    if normalized is None:
        return None
    return json.dumps(normalized, ensure_ascii=False)


def _deserialize_fallback_chain(value: Any) -> list[str] | None:
    return _normalize_fallback_chain(value)


def _resolve_default_db_path() -> str:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return ":memory:"
    return str(get_graph_db_path(get_settings()))


@dataclass(frozen=True)
class QueryRunTrace:
    """Immutable trace record for one query run."""

    run_id: str
    status: str = STATUS_RUNNING
    question: str | None = None
    top_k: int = 0
    include_sources: bool = True
    session_id: str | None = None
    strategy: str | None = None
    retrieval_mode: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_duration_ms: int = 0
    processing_time_ms: int = 0
    layer_requested: str | None = None
    layer_used: str | None = None
    layer_fallback_chain: list[str] | None = None
    context_token_estimate: int = 0
    layer_build_duration_ms: int = 0
    entities_count: int = 0
    source_hit_count: int = 0
    community_hit_count: int = 0
    failure_reason: str | None = None
    created_at: str = ""
    updated_at: str = ""
    completed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QueryTraceStore:
    """Thread-safe SQLite-backed query trace store with bounded retention."""

    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        max_runs: int = DEFAULT_MAX_QUERY_TRACE_RUNS,
    ):
        self._db_path = str(db_path) if db_path is not None else _resolve_default_db_path()
        self._max_runs = max(1, _normalize_non_negative_int(max_runs, DEFAULT_MAX_QUERY_TRACE_RUNS))
        self._lock = Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._bootstrap_schema()

    def close(self) -> None:
        self._conn.close()

    def _bootstrap_schema(self) -> None:
        cursor = self._conn.cursor()
        for statement in _SCHEMA_STATEMENTS:
            cursor.execute(statement)
        existing_columns = {
            str(row["name"])
            for row in cursor.execute("PRAGMA table_info(query_runs)")
        }
        for column_name, statement in _SCHEMA_COMPAT_COLUMNS:
            if column_name not in existing_columns:
                cursor.execute(statement)
        self._conn.commit()

    @staticmethod
    def _row_to_trace(row: sqlite3.Row | None) -> QueryRunTrace | None:
        if row is None:
            return None
        return QueryRunTrace(
            run_id=str(row["run_id"]),
            status=str(row["status"]),
            question=row["question"],
            top_k=int(row["top_k"] or 0),
            include_sources=bool(row["include_sources"]),
            session_id=row["session_id"],
            strategy=row["strategy"],
            retrieval_mode=row["retrieval_mode"],
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            llm_duration_ms=int(row["llm_duration_ms"] or 0),
            processing_time_ms=int(row["processing_time_ms"] or 0),
            layer_requested=row["layer_requested"] if "layer_requested" in row.keys() else None,
            layer_used=row["layer_used"] if "layer_used" in row.keys() else None,
            layer_fallback_chain=_deserialize_fallback_chain(row["layer_fallback_chain"] if "layer_fallback_chain" in row.keys() else None),
            context_token_estimate=int(row["context_token_estimate"] or 0) if "context_token_estimate" in row.keys() else 0,
            layer_build_duration_ms=int(row["layer_build_duration_ms"] or 0) if "layer_build_duration_ms" in row.keys() else 0,
            entities_count=int(row["entities_count"] or 0),
            source_hit_count=int(row["source_hit_count"] or 0),
            community_hit_count=int(row["community_hit_count"] or 0),
            failure_reason=row["failure_reason"],
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
            completed_at=row["completed_at"],
        )

    def create_run(
        self,
        *,
        run_id: str | None = None,
        question: Any = None,
        top_k: Any = 0,
        include_sources: Any = True,
        session_id: Any = None,
        strategy: Any = None,
        retrieval_mode: Any = None,
        llm_provider: Any = None,
        llm_model: Any = None,
        llm_duration_ms: Any = 0,
        processing_time_ms: Any = 0,
        layer_requested: Any = None,
        layer_used: Any = None,
        layer_fallback_chain: Any = None,
        context_token_estimate: Any = 0,
        layer_build_duration_ms: Any = 0,
        entities_count: Any = 0,
        source_hit_count: Any = 0,
        community_hit_count: Any = 0,
    ) -> QueryRunTrace:
        normalized_run_id = _normalize_optional_str(run_id) or f"qrun_{uuid4().hex[:12]}"
        now = _now_iso()
        trace = QueryRunTrace(
            run_id=normalized_run_id,
            status=STATUS_RUNNING,
            question=_normalize_optional_str(question),
            top_k=_normalize_non_negative_int(top_k),
            include_sources=_normalize_bool(include_sources, default=True),
            session_id=_normalize_optional_str(session_id),
            strategy=_normalize_optional_str(strategy),
            retrieval_mode=_normalize_optional_str(retrieval_mode),
            llm_provider=_normalize_optional_str(llm_provider),
            llm_model=_normalize_optional_str(llm_model),
            llm_duration_ms=_normalize_non_negative_int(llm_duration_ms),
            processing_time_ms=_normalize_non_negative_int(processing_time_ms),
            layer_requested=_normalize_optional_str(layer_requested),
            layer_used=_normalize_optional_str(layer_used),
            layer_fallback_chain=_normalize_fallback_chain(layer_fallback_chain),
            context_token_estimate=_normalize_non_negative_int(context_token_estimate),
            layer_build_duration_ms=_normalize_non_negative_int(layer_build_duration_ms),
            entities_count=_normalize_non_negative_int(entities_count),
            source_hit_count=_normalize_non_negative_int(source_hit_count),
            community_hit_count=_normalize_non_negative_int(community_hit_count),
            created_at=now,
            updated_at=now,
        )

        with self._lock:
            existing = self.get_run(normalized_run_id)
            if existing is not None:
                raise ValueError(f"Query run already exists: {normalized_run_id}")
            self._conn.execute(
                """
                INSERT INTO query_runs (
                    run_id, status, question, top_k, include_sources, session_id, strategy,
                    retrieval_mode, llm_provider, llm_model, llm_duration_ms, processing_time_ms,
                    layer_requested, layer_used, layer_fallback_chain, context_token_estimate, layer_build_duration_ms,
                    entities_count, source_hit_count, community_hit_count, failure_reason,
                    created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trace.run_id,
                    trace.status,
                    trace.question,
                    trace.top_k,
                    1 if trace.include_sources else 0,
                    trace.session_id,
                    trace.strategy,
                    trace.retrieval_mode,
                    trace.llm_provider,
                    trace.llm_model,
                    trace.llm_duration_ms,
                    trace.processing_time_ms,
                    trace.layer_requested,
                    trace.layer_used,
                    _serialize_fallback_chain(trace.layer_fallback_chain),
                    trace.context_token_estimate,
                    trace.layer_build_duration_ms,
                    trace.entities_count,
                    trace.source_hit_count,
                    trace.community_hit_count,
                    trace.failure_reason,
                    trace.created_at,
                    trace.updated_at,
                    trace.completed_at,
                ),
            )
            self._trim_locked()
            self._conn.commit()
        return trace

    def start_run(self, **kwargs: Any) -> QueryRunTrace:
        return self.create_run(**kwargs)

    def mark_succeeded(
        self,
        run_id: str,
        *,
        question: Any = None,
        top_k: Any = None,
        include_sources: Any = None,
        session_id: Any = None,
        strategy: Any = None,
        retrieval_mode: Any = None,
        llm_provider: Any = None,
        llm_model: Any = None,
        llm_duration_ms: Any = None,
        processing_time_ms: Any = None,
        layer_requested: Any = None,
        layer_used: Any = None,
        layer_fallback_chain: Any = None,
        context_token_estimate: Any = None,
        layer_build_duration_ms: Any = None,
        entities_count: Any = None,
        source_hit_count: Any = None,
        community_hit_count: Any = None,
    ) -> QueryRunTrace:
        return self._finalize_run(
            run_id,
            status=STATUS_SUCCEEDED,
            question=question,
            top_k=top_k,
            include_sources=include_sources,
            session_id=session_id,
            strategy=strategy,
            retrieval_mode=retrieval_mode,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_duration_ms=llm_duration_ms,
            processing_time_ms=processing_time_ms,
            layer_requested=layer_requested,
            layer_used=layer_used,
            layer_fallback_chain=layer_fallback_chain,
            context_token_estimate=context_token_estimate,
            layer_build_duration_ms=layer_build_duration_ms,
            entities_count=entities_count,
            source_hit_count=source_hit_count,
            community_hit_count=community_hit_count,
            failure_reason=None,
        )

    def complete_success(self, run_id: str, **kwargs: Any) -> QueryRunTrace:
        return self.mark_succeeded(run_id, **kwargs)

    def mark_failed(
        self,
        run_id: str,
        *,
        question: Any = None,
        top_k: Any = None,
        include_sources: Any = None,
        session_id: Any = None,
        strategy: Any = None,
        retrieval_mode: Any = None,
        llm_provider: Any = None,
        llm_model: Any = None,
        llm_duration_ms: Any = None,
        processing_time_ms: Any = None,
        layer_requested: Any = None,
        layer_used: Any = None,
        layer_fallback_chain: Any = None,
        context_token_estimate: Any = None,
        layer_build_duration_ms: Any = None,
        entities_count: Any = None,
        source_hit_count: Any = None,
        community_hit_count: Any = None,
        failure_reason: Any = None,
    ) -> QueryRunTrace:
        return self._finalize_run(
            run_id,
            status=STATUS_FAILED,
            question=question,
            top_k=top_k,
            include_sources=include_sources,
            session_id=session_id,
            strategy=strategy,
            retrieval_mode=retrieval_mode,
            llm_provider=llm_provider,
            llm_model=llm_model,
            llm_duration_ms=llm_duration_ms,
            processing_time_ms=processing_time_ms,
            layer_requested=layer_requested,
            layer_used=layer_used,
            layer_fallback_chain=layer_fallback_chain,
            context_token_estimate=context_token_estimate,
            layer_build_duration_ms=layer_build_duration_ms,
            entities_count=entities_count,
            source_hit_count=source_hit_count,
            community_hit_count=community_hit_count,
            failure_reason=failure_reason,
        )

    def complete_failure(self, run_id: str, **kwargs: Any) -> QueryRunTrace:
        return self.mark_failed(run_id, **kwargs)

    def get_run(self, run_id: str) -> Optional[QueryRunTrace]:
        normalized_run_id = _normalize_optional_str(run_id)
        if normalized_run_id is None:
            return None
        cursor = self._conn.cursor()
        cursor.execute("SELECT * FROM query_runs WHERE run_id = ?", (normalized_run_id,))
        return self._row_to_trace(cursor.fetchone())

    def get(self, run_id: str) -> Optional[QueryRunTrace]:
        return self.get_run(run_id)

    def list_recent_runs(self, *, limit: int = 10) -> list[QueryRunTrace]:
        safe_limit = _normalize_non_negative_int(limit, 10)
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM query_runs
            ORDER BY created_at DESC, run_id DESC
            LIMIT ?
            """,
            (safe_limit,),
        )
        return [trace for row in cursor.fetchall() if (trace := self._row_to_trace(row)) is not None]

    def list_recent(self, *, limit: int = 10) -> list[QueryRunTrace]:
        return self.list_recent_runs(limit=limit)

    def _finalize_run(
        self,
        run_id: str,
        *,
        status: str,
        question: Any = None,
        top_k: Any = None,
        include_sources: Any = None,
        session_id: Any = None,
        strategy: Any = None,
        retrieval_mode: Any = None,
        llm_provider: Any = None,
        llm_model: Any = None,
        llm_duration_ms: Any = None,
        processing_time_ms: Any = None,
        layer_requested: Any = None,
        layer_used: Any = None,
        layer_fallback_chain: Any = None,
        context_token_estimate: Any = None,
        layer_build_duration_ms: Any = None,
        entities_count: Any = None,
        source_hit_count: Any = None,
        community_hit_count: Any = None,
        failure_reason: Any = None,
    ) -> QueryRunTrace:
        normalized_run_id = _normalize_optional_str(run_id)
        if normalized_run_id is None:
            raise KeyError("Query run id is required")

        with self._lock:
            current = self.get_run(normalized_run_id)
            if current is None:
                raise KeyError(f"Unknown query run: {normalized_run_id}")

            now = _now_iso()
            updated = replace(
                current,
                status=status,
                question=self._coalesce_optional_str(question, current.question),
                top_k=self._coalesce_non_negative_int(top_k, current.top_k),
                include_sources=current.include_sources if include_sources is None else _normalize_bool(include_sources),
                session_id=self._coalesce_optional_str(session_id, current.session_id),
                strategy=self._coalesce_optional_str(strategy, current.strategy),
                retrieval_mode=self._coalesce_optional_str(retrieval_mode, current.retrieval_mode),
                llm_provider=self._coalesce_optional_str(llm_provider, current.llm_provider),
                llm_model=self._coalesce_optional_str(llm_model, current.llm_model),
                llm_duration_ms=self._coalesce_non_negative_int(llm_duration_ms, current.llm_duration_ms),
                processing_time_ms=self._coalesce_non_negative_int(processing_time_ms, current.processing_time_ms),
                layer_requested=self._coalesce_optional_str(layer_requested, current.layer_requested),
                layer_used=self._coalesce_optional_str(layer_used, current.layer_used),
                layer_fallback_chain=self._coalesce_fallback_chain(layer_fallback_chain, current.layer_fallback_chain),
                context_token_estimate=self._coalesce_non_negative_int(context_token_estimate, current.context_token_estimate),
                layer_build_duration_ms=self._coalesce_non_negative_int(layer_build_duration_ms, current.layer_build_duration_ms),
                entities_count=self._coalesce_non_negative_int(entities_count, current.entities_count),
                source_hit_count=self._coalesce_non_negative_int(source_hit_count, current.source_hit_count),
                community_hit_count=self._coalesce_non_negative_int(community_hit_count, current.community_hit_count),
                failure_reason=_normalize_optional_str(failure_reason) if status == STATUS_FAILED else None,
                updated_at=now,
                completed_at=now,
            )
            self._conn.execute(
                """
                UPDATE query_runs
                SET status = ?, question = ?, top_k = ?, include_sources = ?, session_id = ?, strategy = ?,
                    retrieval_mode = ?, llm_provider = ?, llm_model = ?, llm_duration_ms = ?,
                    processing_time_ms = ?, layer_requested = ?, layer_used = ?, layer_fallback_chain = ?,
                    context_token_estimate = ?, layer_build_duration_ms = ?, entities_count = ?, source_hit_count = ?,
                    community_hit_count = ?, failure_reason = ?, updated_at = ?, completed_at = ?
                WHERE run_id = ?
                """,
                (
                    updated.status,
                    updated.question,
                    updated.top_k,
                    1 if updated.include_sources else 0,
                    updated.session_id,
                    updated.strategy,
                    updated.retrieval_mode,
                    updated.llm_provider,
                    updated.llm_model,
                    updated.llm_duration_ms,
                    updated.processing_time_ms,
                    updated.layer_requested,
                    updated.layer_used,
                    _serialize_fallback_chain(updated.layer_fallback_chain),
                    updated.context_token_estimate,
                    updated.layer_build_duration_ms,
                    updated.entities_count,
                    updated.source_hit_count,
                    updated.community_hit_count,
                    updated.failure_reason,
                    updated.updated_at,
                    updated.completed_at,
                    updated.run_id,
                ),
            )
            self._trim_locked()
            self._conn.commit()
            return updated

    @staticmethod
    def _coalesce_optional_str(value: Any, current: str | None) -> str | None:
        normalized = _normalize_optional_str(value)
        return normalized if normalized is not None else current

    @staticmethod
    def _coalesce_non_negative_int(value: Any, current: int) -> int:
        if value is None:
            return current
        return _normalize_non_negative_int(value, current)

    @staticmethod
    def _coalesce_fallback_chain(value: Any, current: list[str] | None) -> list[str] | None:
        normalized = _normalize_fallback_chain(value)
        return normalized if normalized is not None else current

    def _trim_locked(self) -> None:
        self._conn.execute(
            """
            DELETE FROM query_runs
            WHERE run_id IN (
                SELECT run_id
                FROM query_runs
                ORDER BY created_at DESC, run_id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (self._max_runs,),
        )


_query_trace_store: Optional[QueryTraceStore] = None
_query_trace_store_lock = Lock()


def get_query_trace_store() -> QueryTraceStore:
    """Return the shared query trace store singleton."""
    global _query_trace_store
    if _query_trace_store is None:
        with _query_trace_store_lock:
            if _query_trace_store is None:
                _query_trace_store = QueryTraceStore()
    return _query_trace_store


def reset_query_trace_store() -> None:
    """Reset the shared query trace store singleton."""
    global _query_trace_store
    with _query_trace_store_lock:
        if _query_trace_store is not None:
            _query_trace_store.close()
        _query_trace_store = None
