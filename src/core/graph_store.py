"""
Graph Store Module
NetworkX + SQLite for storing entities and relationships
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx

from src.core.config import get_settings
from src.core.graph_store_admin import GraphStoreAdminOps
from src.core.graph_store_communities import GraphStoreCommunityOps
from src.core.graph_store_entities import GraphStoreEntityOps
from src.core.graph_store_models import GraphEntity, GraphRelationship, GraphStats
from src.core.graph_store_rows import (
    load_graph_from_connection,
    prune_orphan_graph_objects,
    row_to_dict,
    row_to_entity,
    row_to_relationship,
    upsert_entity_row,
    upsert_relationship_row,
)
from src.core.graph_store_schema import connect_graph_store, get_graph_db_path
from src.core.graph_store_sqlite import (
    build_limit_offset_clause,
    get_child_community_ids_sync,
    table_exists,
)
from src.core.graph_store_sync import GraphStoreSyncOps


class GraphStore:
    """
    Graph Store
    Manage entities and relationships using NetworkX + SQLite
    """

    def __init__(self):
        self.settings = get_settings()
        self._graph: Optional[nx.MultiDiGraph] = None
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._db_path: Path = get_graph_db_path(self.settings)
        self._init_database()
        self._sync_ops = GraphStoreSyncOps(
            get_connection=lambda: self._conn,
            lock=self._lock,
            row_to_dict=row_to_dict,
            upsert_entity_row=upsert_entity_row,
            upsert_relationship_row=upsert_relationship_row,
            prune_orphan_graph_objects=prune_orphan_graph_objects,
            load_graph=self._load_graph,
        )
        self._admin_ops = GraphStoreAdminOps(
            get_connection=lambda: self._conn,
            set_connection=lambda conn: setattr(self, "_conn", conn),
            get_graph=lambda: self._graph,
            lock=self._lock,
            table_exists=lambda name: table_exists(self._conn, name),
            make_stats=GraphStats,
        )
        self._entity_ops = GraphStoreEntityOps(
            get_connection=lambda: self._conn,
            get_graph=lambda: self._graph,
            lock=self._lock,
            row_to_entity=row_to_entity,
            row_to_relationship=row_to_relationship,
            build_limit_offset_clause=build_limit_offset_clause,
            upsert_entity_row=upsert_entity_row,
            upsert_relationship_row=upsert_relationship_row,
        )
        self._community_ops = GraphStoreCommunityOps(
            get_connection=lambda: self._conn,
            lock=self._lock,
            row_to_dict=row_to_dict,
            row_to_entity=row_to_entity,
            build_limit_offset_clause=build_limit_offset_clause,
            get_child_community_ids_sync=lambda community_id: get_child_community_ids_sync(
                self._conn,
                community_id,
            ),
        )

    def _init_database(self) -> None:
        """Initialize SQLite database and bootstrap the in-memory graph."""
        self._conn = connect_graph_store(self._db_path)
        self._load_graph()

    def _load_graph(self) -> None:
        """Reload all SQLite graph data into NetworkX."""
        self._graph = load_graph_from_connection(self._conn)

    # ========================================
    # Entity Operations
    # ========================================

    async def create_entity(self, entity: GraphEntity) -> str:
        """Create a new entity"""
        return await self._entity_ops.create_entity(entity)

    async def get_entity(self, entity_id: str) -> Optional[GraphEntity]:
        """Get entity by ID"""
        return await self._entity_ops.get_entity(entity_id)

    async def find_entities_by_name(
        self,
        name: str,
        limit: Optional[int] = 10,
    ) -> List[GraphEntity]:
        """Find entities by case-insensitive exact name match."""
        return await self._entity_ops.find_entities_by_name(name, limit=limit)

    async def count_entities(
        self,
        entity_types: Optional[List[str]] = None,
    ) -> int:
        """Count entities, optionally filtered by type."""
        return await self._entity_ops.count_entities(entity_types=entity_types)

    async def query_entities(
        self,
        entity_types: Optional[List[str]] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[GraphEntity]:
        """Query entities with optional pagination and type filtering."""
        return await self._entity_ops.query_entities(
            entity_types=entity_types,
            limit=limit,
            offset=offset,
        )

    async def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[GraphEntity]:
        """Get entities by type"""
        return await self._entity_ops.get_entities(entity_type=entity_type, limit=limit)

    async def get_neighbors(
        self,
        entity_id: str,
        depth: int = 1,
    ) -> List[Dict[str, Any]]:
        """Get neighbors of an entity using NetworkX"""
        return await self._entity_ops.get_neighbors(entity_id, depth=depth)

    async def delete_entity(self, entity_id: str) -> bool:
        """Delete entity and its relationships"""
        return await self._entity_ops.delete_entity(entity_id)

    # ========================================
    # Relationship Operations
    # ========================================

    async def create_relationship(self, rel: GraphRelationship) -> str:
        """Create a relationship between entities"""
        return await self._entity_ops.create_relationship(rel)

    async def get_relationships(
        self,
        entity_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[GraphRelationship]:
        """Get relationships"""
        return await self._entity_ops.get_relationships(entity_id=entity_id, limit=limit)

    async def count_relationships_between_entities(self, entity_ids: List[str]) -> int:
        """Count relationships whose endpoints are both inside a given entity set."""
        return await self._entity_ops.count_relationships_between_entities(entity_ids)

    async def query_relationships_between_entities(
        self,
        entity_ids: List[str],
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[GraphRelationship]:
        """Query relationships whose endpoints both belong to a given entity set."""
        return await self._entity_ops.query_relationships_between_entities(
            entity_ids=entity_ids,
            limit=limit,
            offset=offset,
        )

    async def delete_relationship(self, relationship_id: str) -> bool:
        """Delete a relationship"""
        return await self._entity_ops.delete_relationship(relationship_id)

    # ========================================
    # Sync Metadata Operations
    # ========================================

    async def get_memory_registry(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a registry row by memory ID."""
        return await self._sync_ops.get_memory_registry(memory_id)

    async def get_memory_registry_by_external_key(
        self,
        source_system: str,
        workspace_id: Optional[str],
        external_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a registry row by external sync key."""
        return await self._sync_ops.get_memory_registry_by_external_key(
            source_system=source_system,
            workspace_id=workspace_id,
            external_id=external_id,
        )

    async def get_memory_sync_state(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get sync state for a memory."""
        return await self._sync_ops.get_memory_sync_state(memory_id)

    async def get_memory_context(self, memory_id: str) -> Dict[str, Any]:
        """Get related entities and communities for a memory."""
        return await self._sync_ops.get_memory_context(memory_id)

    async def get_entity_memory_ids(
        self,
        entity_id: str,
        limit: Optional[int] = 20,
    ) -> List[str]:
        """Return non-deleted memory IDs that mention an entity."""
        return await self._sync_ops.get_entity_memory_ids(entity_id, limit=limit)

    async def upsert_memory_record(
        self,
        registry_row: Dict[str, Any],
        sync_state_row: Dict[str, Any],
        entities: Optional[List[GraphEntity]] = None,
        mentions: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[GraphRelationship]] = None,
        relationship_evidence: Optional[List[Dict[str, Any]]] = None,
        change_log_row: Optional[Dict[str, Any]] = None,
        replace_evidence: bool = False,
    ) -> None:
        """Persist a memory registry/sync row and optionally replace its graph evidence."""
        await self._sync_ops.upsert_memory_record(
            registry_row=registry_row,
            sync_state_row=sync_state_row,
            entities=entities,
            mentions=mentions,
            relationships=relationships,
            relationship_evidence=relationship_evidence,
            change_log_row=change_log_row,
            replace_evidence=replace_evidence,
        )

    async def tombstone_memory_record(
        self,
        memory_id: str,
        deleted_at: str,
        updated_at: str,
        server_version: int,
        sync_state_updates: Dict[str, Any],
        change_log_row: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a memory as deleted and garbage-collect its graph evidence."""
        await self._sync_ops.tombstone_memory_record(
            memory_id=memory_id,
            deleted_at=deleted_at,
            updated_at=updated_at,
            server_version=server_version,
            sync_state_updates=sync_state_updates,
            change_log_row=change_log_row,
        )

    async def list_sync_changes(
        self,
        source_system: str,
        workspace_id: Optional[str],
        cursor_seq: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """List sync changes ordered by cursor."""
        return await self._sync_ops.list_sync_changes(
            source_system=source_system,
            workspace_id=workspace_id,
            cursor_seq=cursor_seq,
            limit=limit,
        )

    async def list_active_workspace_records(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """List active registry rows for a workspace."""
        return await self._sync_ops.list_active_workspace_records(
            source_system=source_system,
            workspace_id=workspace_id,
        )

    async def get_sync_state_summary(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        """Get aggregate sync state for a workspace."""
        return await self._sync_ops.get_sync_state_summary(
            source_system=source_system,
            workspace_id=workspace_id,
        )

    async def mark_community_dirty(
        self,
        reason: str,
        marked_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark community derivations as stale."""
        return await self._community_ops.mark_community_dirty(
            reason=reason,
            marked_at=marked_at,
        )

    async def mark_community_clean(
        self,
        rebuild_at: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark community derivations as up to date."""
        return await self._community_ops.mark_community_clean(
            rebuild_at=rebuild_at,
            job_id=job_id,
        )

    async def get_community_state(self) -> Dict[str, Any]:
        """Return persisted community rebuild state."""
        return await self._community_ops.get_community_state()

    # ========================================
    # Community Operations
    # ========================================

    async def create_community(self, community) -> str:
        """Create a community."""
        return await self._community_ops.create_community(community)

    async def get_leaf_entity_ids(self, community_id: str) -> List[str]:
        """Return all leaf entity IDs contained by a community."""
        return await self._community_ops.get_leaf_entity_ids(community_id)

    async def get_community(self, community_id: str, include_entity_ids: bool = False):
        """Get community by ID."""
        return await self._community_ops.get_community(
            community_id=community_id,
            include_entity_ids=include_entity_ids,
        )

    async def list_communities(
        self,
        level: Optional[int] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        require_summary: bool = False,
        include_entity_ids: bool = False,
        order_by: str = "rank_desc",
    ) -> List[Dict[str, Any]]:
        """List community records with optional filters."""
        return await self._community_ops.list_communities(
            level=level,
            limit=limit,
            offset=offset,
            require_summary=require_summary,
            include_entity_ids=include_entity_ids,
            order_by=order_by,
        )

    async def get_communities_by_level(self, level: int, limit: int = 100):
        """Get communities by level."""
        return await self._community_ops.get_communities_by_level(level=level, limit=limit)

    async def get_entity_communities(self, entity_id: str) -> List[str]:
        """Return community IDs containing an entity, ordered by level."""
        return await self._community_ops.get_entity_communities(entity_id)

    async def get_community_entities(
        self,
        community_id: str,
        limit: Optional[int] = 50,
    ) -> List[GraphEntity]:
        """Return leaf entities contained by a community."""
        return await self._community_ops.get_community_entities(
            community_id=community_id,
            limit=limit,
        )

    async def get_community_relationships(
        self,
        community_id: str,
        limit: Optional[int] = 50,
    ) -> List[Dict[str, Any]]:
        """Return relationships whose endpoints both belong to a community."""
        return await self._community_ops.get_community_relationships(
            community_id=community_id,
            limit=limit,
        )

    async def update_community_summary(self, community_id: str, summary: str):
        """Update community summary."""
        await self._community_ops.update_community_summary(community_id, summary)

    async def replace_community_memberships(
        self,
        community_id: str,
        entity_ids: List[str],
        created_at: Optional[str] = None,
    ) -> None:
        """Replace entity memberships for a community."""
        await self._community_ops.replace_community_memberships(
            community_id=community_id,
            entity_ids=entity_ids,
            created_at=created_at,
        )

    async def refresh_community_entity_count(self, community_id: str) -> int:
        """Recompute and persist the leaf-entity count for a community."""
        return await self._community_ops.refresh_community_entity_count(community_id)

    async def count_community_memberships(self) -> int:
        """Count direct entity-to-community memberships."""
        return await self._community_ops.count_community_memberships()

    async def set_community_parent(
        self,
        child_id: str,
        parent_id: Optional[str],
    ) -> bool:
        """Set or clear the parent of a community."""
        return await self._community_ops.set_community_parent(child_id, parent_id)

    async def get_community_neighbors(self, community_id: str) -> List[str]:
        """Find neighboring communities through cross-community relationships."""
        return await self._community_ops.get_community_neighbors(community_id)

    async def get_community_ancestors(self, community_id: str) -> List[Dict[str, Any]]:
        """Return ancestor communities, closest first."""
        return await self._community_ops.get_community_ancestors(community_id)

    async def get_community_descendants(
        self,
        community_id: str,
    ) -> List[Dict[str, Any]]:
        """Return descendant communities, immediate children first."""
        return await self._community_ops.get_community_descendants(community_id)

    async def get_community_path(self, community_id: str) -> List[Dict[str, Any]]:
        """Return the path from the root community to the target community."""
        return await self._community_ops.get_community_path(community_id)

    async def detect_communities(self, level: int = 0):
        """Detect communities using Louvain algorithm."""
        return await self._admin_ops.detect_communities(level=level)

    # ========================================
    # Statistics
    # ========================================

    async def get_stats(self) -> GraphStats:
        """Get graph statistics"""
        return await self._admin_ops.get_stats()

    # ========================================
    # Utility Methods
    # ========================================

    async def clear_all(self) -> bool:
        """Clear all entities and relationships"""
        return await self._admin_ops.clear_all()

    async def close(self):
        """Close connection"""
        await self._admin_ops.close()

    async def test_connection(self) -> bool:
        """Test connection"""
        return await self._admin_ops.test_connection()


_graph_store: Optional[GraphStore] = None


def get_graph_store() -> GraphStore:
    """Get Graph Store singleton"""
    global _graph_store
    if _graph_store is None:
        _graph_store = GraphStore()
    return _graph_store


def reset_graph_store() -> None:
    """Reset the cached graph store singleton."""
    global _graph_store
    if _graph_store is not None and _graph_store._conn is not None:
        _graph_store._conn.close()
    _graph_store = None


__all__ = [
    "GraphEntity",
    "GraphRelationship",
    "GraphStats",
    "GraphStore",
    "get_graph_store",
    "reset_graph_store",
]
