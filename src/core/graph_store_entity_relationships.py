"""Relationship CRUD/query operations for GraphStore."""

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING, Any, Callable, List, Optional

import networkx as nx

from src.core.graph_store_sqlite import require_connection

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphRelationship


class GraphStoreRelationshipOps:
    """Own relationship CRUD/query behavior for GraphStore."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        get_graph: Callable[[], Optional[nx.MultiDiGraph]],
        lock: Any,
        row_to_relationship: Callable[[Optional[sqlite3.Row]], Optional[GraphRelationship]],
        build_limit_offset_clause: Callable[[List[Any], Optional[int], int], str],
        upsert_relationship_row: Callable[[sqlite3.Cursor, GraphRelationship], None],
    ) -> None:
        self._get_connection = get_connection
        self._get_graph = get_graph
        self._lock = lock
        self._row_to_relationship = row_to_relationship
        self._build_limit_offset_clause = build_limit_offset_clause
        self._upsert_relationship_row = upsert_relationship_row

    def _require_connection(self) -> sqlite3.Connection:
        return require_connection(self._get_connection())

    def _require_graph(self) -> nx.MultiDiGraph:
        graph = self._get_graph()
        if graph is None:
            raise RuntimeError("GraphStore graph is not initialized")
        return graph

    async def create_relationship(self, rel: GraphRelationship) -> str:
        """Create a relationship between entities."""
        conn = self._require_connection()
        graph = self._require_graph()
        rel.id = rel.id or str(uuid.uuid4())

        with self._lock:
            cursor = conn.cursor()
            self._upsert_relationship_row(cursor, rel)
            conn.commit()

            if rel.source_id in graph and rel.target_id in graph:
                graph.add_edge(
                    rel.source_id,
                    rel.target_id,
                    key=rel.id,
                    id=rel.id,
                    type=rel.type,
                    properties=rel.properties,
                    confidence=rel.confidence,
                    created_at=rel.created_at.isoformat(),
                )

        return rel.id

    async def get_relationships(
        self,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[GraphRelationship]:
        """Get relationships."""
        cursor = self._require_connection().cursor()

        if entity_id:
            cursor.execute(
                """SELECT * FROM relationships
                   WHERE source_id = ? OR target_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (entity_id, entity_id, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM relationships ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )

        return [
            rel
            for row in cursor.fetchall()
            if (rel := self._row_to_relationship(row)) is not None
        ]

    async def count_relationships_between_entities(self, entity_ids: List[str]) -> int:
        """Count relationships whose endpoints are both inside a given entity set."""
        if not entity_ids:
            return 0

        placeholders = ",".join("?" for _ in entity_ids)
        cursor = self._require_connection().cursor()
        cursor.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM relationships
            WHERE source_id IN ({placeholders})
              AND target_id IN ({placeholders})
            """,
            (*entity_ids, *entity_ids),
        )
        row = cursor.fetchone()
        return row["count"] if row else 0

    async def query_relationships_between_entities(
        self,
        entity_ids: List[str],
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[GraphRelationship]:
        """Query relationships whose endpoints both belong to a given entity set."""
        if not entity_ids:
            return []

        placeholders = ",".join("?" for _ in entity_ids)
        params: List[Any] = [*entity_ids, *entity_ids]
        query = f"""
            SELECT *
            FROM relationships
            WHERE source_id IN ({placeholders})
              AND target_id IN ({placeholders})
            ORDER BY created_at
        """
        query += self._build_limit_offset_clause(params, limit, offset)

        cursor = self._require_connection().cursor()
        cursor.execute(query, params)
        return [
            rel
            for row in cursor.fetchall()
            if (rel := self._row_to_relationship(row)) is not None
        ]

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        conn = self._require_connection()
        graph = self._require_graph()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT source_id, target_id FROM relationships WHERE id = ?",
                (relationship_id,),
            )
            row = cursor.fetchone()

            if row:
                cursor.execute("DELETE FROM relationships WHERE id = ?", (relationship_id,))
                conn.commit()
                if graph.has_edge(row["source_id"], row["target_id"], key=relationship_id):
                    graph.remove_edge(row["source_id"], row["target_id"], key=relationship_id)

        return True
