"""Entity CRUD/query operations for GraphStore."""

from __future__ import annotations

import sqlite3
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import networkx as nx

from src.core.graph_store_sqlite import require_connection

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphEntity


class GraphStoreNodeOps:
    """Own entity CRUD/query behavior for GraphStore."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        get_graph: Callable[[], Optional[nx.MultiDiGraph]],
        lock: Any,
        row_to_entity: Callable[[Optional[sqlite3.Row]], Optional[GraphEntity]],
        build_limit_offset_clause: Callable[[List[Any], Optional[int], int], str],
        upsert_entity_row: Callable[[sqlite3.Cursor, GraphEntity], None],
    ) -> None:
        self._get_connection = get_connection
        self._get_graph = get_graph
        self._lock = lock
        self._row_to_entity = row_to_entity
        self._build_limit_offset_clause = build_limit_offset_clause
        self._upsert_entity_row = upsert_entity_row

    def _require_connection(self) -> sqlite3.Connection:
        return require_connection(self._get_connection())

    def _require_graph(self) -> nx.MultiDiGraph:
        graph = self._get_graph()
        if graph is None:
            raise RuntimeError("GraphStore graph is not initialized")
        return graph

    async def create_entity(self, entity: GraphEntity) -> str:
        """Create a new entity."""
        conn = self._require_connection()
        graph = self._require_graph()
        entity.id = entity.id or str(uuid.uuid4())

        with self._lock:
            cursor = conn.cursor()
            self._upsert_entity_row(cursor, entity)
            conn.commit()
            graph.add_node(
                entity.id,
                name=entity.name,
                type=entity.type,
                properties=entity.properties,
                source_text=entity.source_text,
                confidence=entity.confidence,
                created_at=entity.created_at.isoformat(),
            )

        return entity.id

    async def get_entity(self, entity_id: str) -> Optional[GraphEntity]:
        """Get entity by ID."""
        cursor = self._require_connection().cursor()
        cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
        return self._row_to_entity(cursor.fetchone())

    async def find_entities_by_name(
        self,
        name: str,
        limit: Optional[int] = 10,
    ) -> List[GraphEntity]:
        """Find entities by case-insensitive exact name match."""
        normalized_name = (name or "").strip()
        if not normalized_name:
            return []

        cursor = self._require_connection().cursor()
        params: List[Any] = [normalized_name]
        query = """
            SELECT *
            FROM entities
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
            ORDER BY created_at DESC, id ASC
        """
        query += self._build_limit_offset_clause(params, limit, 0)
        cursor.execute(query, params)
        return [
            entity
            for row in cursor.fetchall()
            if (entity := self._row_to_entity(row)) is not None
        ]

    async def count_entities(
        self,
        entity_types: Optional[List[str]] = None,
    ) -> int:
        """Count entities, optionally filtered by type."""
        cursor = self._require_connection().cursor()
        params: List[Any] = []
        query = "SELECT COUNT(*) AS count FROM entities"

        if entity_types:
            placeholders = ",".join("?" for _ in entity_types)
            query += f" WHERE type IN ({placeholders})"
            params.extend(entity_types)

        cursor.execute(query, params)
        row = cursor.fetchone()
        return row["count"] if row else 0

    async def query_entities(
        self,
        entity_types: Optional[List[str]] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[GraphEntity]:
        """Query entities with optional pagination and type filtering."""
        cursor = self._require_connection().cursor()
        params: List[Any] = []
        query = "SELECT * FROM entities"

        if entity_types:
            placeholders = ",".join("?" for _ in entity_types)
            query += f" WHERE type IN ({placeholders})"
            params.extend(entity_types)

        query += " ORDER BY created_at"
        query += self._build_limit_offset_clause(params, limit, offset)

        cursor.execute(query, params)
        return [
            entity
            for row in cursor.fetchall()
            if (entity := self._row_to_entity(row)) is not None
        ]

    async def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[GraphEntity]:
        """Get entities by type."""
        entity_types = [entity_type] if entity_type else None
        entities = await self.query_entities(entity_types=entity_types, limit=limit)
        entities.reverse()
        return entities

    async def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get neighbors of an entity using NetworkX."""
        graph = self._require_graph()
        if entity_id not in graph:
            return []

        neighbors = nx.single_source_shortest_path_length(graph, entity_id, cutoff=depth)

        results = []
        for neighbor_id, distance in neighbors.items():
            if neighbor_id == entity_id:
                continue

            node_data = graph.nodes[neighbor_id]
            rels = []
            for u, v, data in graph.edges(neighbor_id, data=True):
                if u == neighbor_id or v == neighbor_id:
                    rels.append(
                        {
                            "id": data.get("id"),
                            "type": data.get("type"),
                            "target_id": v if u == neighbor_id else u,
                        }
                    )

            results.append(
                {
                    "id": neighbor_id,
                    "name": node_data.get("name"),
                    "type": node_data.get("type"),
                    "distance": distance,
                    "relationships": rels,
                }
            )

        return results

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity and its relationships."""
        conn = self._require_connection()
        graph = self._require_graph()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM relationships WHERE source_id = ? OR target_id = ?",
                (entity_id, entity_id),
            )
            cursor.execute("DELETE FROM entities WHERE id = ?", (entity_id,))
            conn.commit()

            if entity_id in graph:
                graph.remove_edges_from(list(graph.edges(entity_id)))
                graph.remove_node(entity_id)

        return True
