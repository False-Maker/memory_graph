"""Temporal knowledge graph persistence on top of the shared SQLite graph store."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.core.config import get_settings
from src.core.graph_store_schema import connect_graph_store, get_graph_db_path


@dataclass
class TemporalTriple:
    """One temporal relation attached to an entity."""

    id: str
    entity_id: str
    relation_type: str
    target_entity_id: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    confidence: float = 1.0
    source: Optional[str] = None
    created_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TemporalStats:
    """Aggregate statistics for temporal triples."""

    total_triples: int
    entities_with_temporal_data: int
    open_intervals: int
    bounded_intervals: int


class TemporalKnowledgeGraph:
    """Manage temporal triples in the shared graph SQLite database."""

    def __init__(self, db_path: Optional[Path] = None):
        settings = get_settings()
        self._db_path = Path(db_path) if db_path else get_graph_db_path(settings)
        self._conn = connect_graph_store(self._db_path)
        self._lock = threading.Lock()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_datetime(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            normalized = value
        elif isinstance(value, date):
            normalized = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            raw = raw.replace("Z", "+00:00")
            try:
                normalized = datetime.fromisoformat(raw)
            except ValueError:
                normalized = datetime.combine(date.fromisoformat(raw), datetime.min.time(), tzinfo=timezone.utc)
        else:
            raise ValueError(f"Unsupported datetime value: {value!r}")

        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=timezone.utc)
        return normalized.isoformat()

    @staticmethod
    def _row_to_temporal_triple(row: sqlite3.Row) -> TemporalTriple:
        metadata = row["metadata"]
        return TemporalTriple(
            id=str(row["id"]),
            entity_id=str(row["entity_id"]),
            relation_type=str(row["relation_type"]),
            target_entity_id=row["target_entity_id"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            confidence=float(row["confidence"] or 1.0),
            source=row["source"],
            created_at=str(row["created_at"]),
            metadata=json.loads(metadata) if isinstance(metadata, str) and metadata else {},
        )

    async def upsert_triple(
        self,
        *,
        triple_id: Optional[str],
        entity_id: str,
        relation_type: str,
        target_entity_id: Optional[str] = None,
        valid_from: Any = None,
        valid_to: Any = None,
        confidence: float = 1.0,
        source: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> TemporalTriple:
        normalized_entity_id = str(entity_id or "").strip()
        normalized_relation_type = str(relation_type or "").strip()
        normalized_target_id = str(target_entity_id).strip() if target_entity_id else None
        if not normalized_entity_id:
            raise ValueError("entity_id is required")
        if not normalized_relation_type:
            raise ValueError("relation_type is required")

        valid_from_iso = self._normalize_datetime(valid_from)
        valid_to_iso = self._normalize_datetime(valid_to)
        if valid_from_iso and valid_to_iso and valid_from_iso > valid_to_iso:
            raise ValueError("valid_from must be earlier than or equal to valid_to")

        triple_id = str(triple_id or f"ttrip_{uuid.uuid4().hex[:16]}")
        metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        created_at = self._now_iso()

        with self._lock:
            existing = self._conn.execute(
                "SELECT created_at FROM temporal_triples WHERE id = ?",
                (triple_id,),
            ).fetchone()
            if existing is not None:
                created_at = str(existing["created_at"])

            try:
                self._conn.execute(
                    """
                    INSERT OR REPLACE INTO temporal_triples (
                        id,
                        entity_id,
                        relation_type,
                        target_entity_id,
                        valid_from,
                        valid_to,
                        confidence,
                        source,
                        created_at,
                        metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        triple_id,
                        normalized_entity_id,
                        normalized_relation_type,
                        normalized_target_id,
                        valid_from_iso,
                        valid_to_iso,
                        float(confidence),
                        source,
                        created_at,
                        metadata_json,
                    ),
                )
                self._conn.commit()
            except sqlite3.IntegrityError as exc:
                raise ValueError(str(exc)) from exc

            row = self._conn.execute(
                "SELECT * FROM temporal_triples WHERE id = ?",
                (triple_id,),
            ).fetchone()

        return self._row_to_temporal_triple(row)

    async def get_entity_timeline(self, entity_id: str) -> list[TemporalTriple]:
        normalized_entity_id = str(entity_id or "").strip()
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                FROM temporal_triples
                WHERE entity_id = ?
                ORDER BY COALESCE(valid_from, created_at) ASC, created_at ASC
                """,
                (normalized_entity_id,),
            ).fetchall()
        return [self._row_to_temporal_triple(row) for row in rows]

    async def get_entity_state_as_of(self, entity_id: str, as_of: Any) -> list[TemporalTriple]:
        normalized_entity_id = str(entity_id or "").strip()
        as_of_iso = self._normalize_datetime(as_of)
        if as_of_iso is None:
            raise ValueError("as_of is required")

        with self._lock:
            rows = self._conn.execute(
                """
                SELECT *
                FROM temporal_triples
                WHERE entity_id = ?
                  AND (valid_from IS NULL OR valid_from <= ?)
                  AND (valid_to IS NULL OR valid_to >= ?)
                ORDER BY COALESCE(valid_from, created_at) ASC, created_at ASC
                """,
                (normalized_entity_id, as_of_iso, as_of_iso),
            ).fetchall()
        return [self._row_to_temporal_triple(row) for row in rows]

    async def delete_triple(self, triple_id: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM temporal_triples WHERE id = ?", (triple_id,))
            self._conn.commit()
            return cursor.rowcount > 0

    async def get_stats(self) -> TemporalStats:
        with self._lock:
            total_triples = int(self._conn.execute("SELECT COUNT(*) FROM temporal_triples").fetchone()[0])
            entities_with_temporal_data = int(
                self._conn.execute("SELECT COUNT(DISTINCT entity_id) FROM temporal_triples").fetchone()[0]
            )
            open_intervals = int(
                self._conn.execute("SELECT COUNT(*) FROM temporal_triples WHERE valid_to IS NULL").fetchone()[0]
            )
            bounded_intervals = int(
                self._conn.execute(
                    "SELECT COUNT(*) FROM temporal_triples WHERE valid_from IS NOT NULL OR valid_to IS NOT NULL"
                ).fetchone()[0]
            )
        return TemporalStats(
            total_triples=total_triples,
            entities_with_temporal_data=entities_with_temporal_data,
            open_intervals=open_intervals,
            bounded_intervals=bounded_intervals,
        )

    def close(self) -> None:
        self._conn.close()


_temporal_kg: Optional[TemporalKnowledgeGraph] = None


def get_temporal_kg() -> TemporalKnowledgeGraph:
    """Get the shared temporal knowledge graph singleton."""
    global _temporal_kg
    if _temporal_kg is None:
        _temporal_kg = TemporalKnowledgeGraph()
    return _temporal_kg


def reset_temporal_kg() -> None:
    """Reset the shared temporal knowledge graph singleton."""
    global _temporal_kg
    if _temporal_kg is not None:
        _temporal_kg.close()
    _temporal_kg = None
