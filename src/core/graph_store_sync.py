"""Sync metadata operations for GraphStore."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.core.graph_store_sync_mutations import GraphStoreSyncMutationOps
from src.core.graph_store_sync_queries import GraphStoreSyncQueryOps

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphEntity, GraphRelationship


class GraphStoreSyncOps:
    """Own the memory registry and sync state subdomain for GraphStore."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        lock: Any,
        row_to_dict: Callable[[Optional[sqlite3.Row]], Optional[Dict[str, Any]]],
        upsert_entity_row: Callable[[sqlite3.Cursor, GraphEntity], None],
        upsert_relationship_row: Callable[[sqlite3.Cursor, GraphRelationship], None],
        prune_orphan_graph_objects: Callable[[sqlite3.Cursor], None],
        load_graph: Callable[[], None],
    ) -> None:
        self._query_ops = GraphStoreSyncQueryOps(
            get_connection=get_connection,
            row_to_dict=row_to_dict,
        )
        self._mutation_ops = GraphStoreSyncMutationOps(
            get_connection=get_connection,
            lock=lock,
            upsert_entity_row=upsert_entity_row,
            upsert_relationship_row=upsert_relationship_row,
            prune_orphan_graph_objects=prune_orphan_graph_objects,
            load_graph=load_graph,
        )

    async def get_memory_registry(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a registry row by memory ID."""
        return await self._query_ops.get_memory_registry(memory_id)

    async def get_memory_registry_by_external_key(
        self,
        source_system: str,
        workspace_id: Optional[str],
        external_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a registry row by external sync key."""
        return await self._query_ops.get_memory_registry_by_external_key(
            source_system=source_system,
            workspace_id=workspace_id,
            external_id=external_id,
        )

    async def get_memory_sync_state(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get sync state for a memory."""
        return await self._query_ops.get_memory_sync_state(memory_id)

    async def get_memory_context(self, memory_id: str) -> Dict[str, Any]:
        """Get related entities and communities for a memory."""
        return await self._query_ops.get_memory_context(memory_id)

    async def get_entity_memory_ids(
        self,
        entity_id: str,
        limit: Optional[int] = 20,
    ) -> List[str]:
        """Return non-deleted memory IDs that mention an entity."""
        return await self._query_ops.get_entity_memory_ids(entity_id, limit=limit)

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
        await self._mutation_ops.upsert_memory_record(
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
        await self._mutation_ops.tombstone_memory_record(
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
        return await self._query_ops.list_sync_changes(
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
        return await self._query_ops.list_active_workspace_records(
            source_system=source_system,
            workspace_id=workspace_id,
        )

    async def get_sync_state_summary(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        """Get aggregate sync state for a workspace."""
        return await self._query_ops.get_sync_state_summary(
            source_system=source_system,
            workspace_id=workspace_id,
        )
