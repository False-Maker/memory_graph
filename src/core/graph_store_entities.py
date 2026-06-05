"""Entity/relationship operations facade for GraphStore."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import networkx as nx

from src.core.graph_store_entity_nodes import GraphStoreNodeOps
from src.core.graph_store_entity_relationships import GraphStoreRelationshipOps

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphEntity, GraphRelationship


class GraphStoreEntityOps:
    """Own entity and relationship behavior for GraphStore."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        get_graph: Callable[[], Optional[nx.MultiDiGraph]],
        lock: Any,
        row_to_entity: Callable[[Optional[sqlite3.Row]], Optional[GraphEntity]],
        row_to_relationship: Callable[[Optional[sqlite3.Row]], Optional[GraphRelationship]],
        build_limit_offset_clause: Callable[[List[Any], Optional[int], int], str],
        upsert_entity_row: Callable[[sqlite3.Cursor, GraphEntity], None],
        upsert_relationship_row: Callable[[sqlite3.Cursor, GraphRelationship], None],
    ) -> None:
        self._node_ops = GraphStoreNodeOps(
            get_connection=get_connection,
            get_graph=get_graph,
            lock=lock,
            row_to_entity=row_to_entity,
            build_limit_offset_clause=build_limit_offset_clause,
            upsert_entity_row=upsert_entity_row,
        )
        self._relationship_ops = GraphStoreRelationshipOps(
            get_connection=get_connection,
            get_graph=get_graph,
            lock=lock,
            row_to_relationship=row_to_relationship,
            build_limit_offset_clause=build_limit_offset_clause,
            upsert_relationship_row=upsert_relationship_row,
        )

    async def create_entity(self, entity: GraphEntity) -> str:
        """Create a new entity."""
        return await self._node_ops.create_entity(entity)

    async def get_entity(self, entity_id: str) -> Optional[GraphEntity]:
        """Get entity by ID."""
        return await self._node_ops.get_entity(entity_id)

    async def find_entities_by_name(
        self,
        name: str,
        limit: Optional[int] = 10,
    ) -> List[GraphEntity]:
        """Find entities by case-insensitive exact name match."""
        return await self._node_ops.find_entities_by_name(name, limit=limit)

    async def count_entities(
        self,
        entity_types: Optional[List[str]] = None,
    ) -> int:
        """Count entities, optionally filtered by type."""
        return await self._node_ops.count_entities(entity_types=entity_types)

    async def query_entities(
        self,
        entity_types: Optional[List[str]] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[GraphEntity]:
        """Query entities with optional pagination and type filtering."""
        return await self._node_ops.query_entities(
            entity_types=entity_types,
            limit=limit,
            offset=offset,
        )

    async def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[GraphEntity]:
        """Get entities by type."""
        return await self._node_ops.get_entities(entity_type=entity_type, limit=limit)

    async def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get neighbors of an entity using NetworkX."""
        return await self._node_ops.get_neighbors(entity_id, depth=depth)

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity and its relationships."""
        return await self._node_ops.delete_entity(entity_id)

    async def create_relationship(self, rel: GraphRelationship) -> str:
        """Create a relationship between entities."""
        return await self._relationship_ops.create_relationship(rel)

    async def get_relationships(
        self,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[GraphRelationship]:
        """Get relationships."""
        return await self._relationship_ops.get_relationships(entity_id=entity_id, limit=limit)

    async def count_relationships_between_entities(self, entity_ids: List[str]) -> int:
        """Count relationships whose endpoints are both inside a given entity set."""
        return await self._relationship_ops.count_relationships_between_entities(entity_ids)

    async def query_relationships_between_entities(
        self,
        entity_ids: List[str],
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[GraphRelationship]:
        """Query relationships whose endpoints both belong to a given entity set."""
        return await self._relationship_ops.query_relationships_between_entities(
            entity_ids=entity_ids,
            limit=limit,
            offset=offset,
        )

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship."""
        return await self._relationship_ops.delete_relationship(relationship_id)
