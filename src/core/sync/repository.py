"""Repository wrapper around GraphStore sync metadata operations."""

from typing import Any, Dict, List, Optional

from src.core.graph_store import GraphStore
from src.core.graph_store_models import GraphEntity, GraphRelationship


class SyncRepository:
    """Thin repository for sync metadata and evidence operations."""

    def __init__(self, graph_store: GraphStore):
        self.graph_store = graph_store

    async def get_memory_registry(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return await self.graph_store.get_memory_registry(memory_id)

    async def get_memory_by_external_key(
        self,
        source_system: str,
        workspace_id: Optional[str],
        external_id: str
    ) -> Optional[Dict[str, Any]]:
        return await self.graph_store.get_memory_registry_by_external_key(
            source_system,
            workspace_id,
            external_id,
        )

    async def get_memory_sync_state(self, memory_id: str) -> Optional[Dict[str, Any]]:
        return await self.graph_store.get_memory_sync_state(memory_id)

    async def save_memory(
        self,
        registry_row: Dict[str, Any],
        sync_state_row: Dict[str, Any],
        entities: Optional[List[GraphEntity]] = None,
        mentions: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[GraphRelationship]] = None,
        relationship_evidence: Optional[List[Dict[str, Any]]] = None,
        change_log_row: Optional[Dict[str, Any]] = None,
        replace_evidence: bool = False,
    ):
        await self.graph_store.upsert_memory_record(
            registry_row=registry_row,
            sync_state_row=sync_state_row,
            entities=entities,
            mentions=mentions,
            relationships=relationships,
            relationship_evidence=relationship_evidence,
            change_log_row=change_log_row,
            replace_evidence=replace_evidence,
        )

    async def tombstone_memory(
        self,
        memory_id: str,
        deleted_at: str,
        updated_at: str,
        server_version: int,
        sync_state_updates: Dict[str, Any],
        change_log_row: Optional[Dict[str, Any]] = None,
    ):
        await self.graph_store.tombstone_memory_record(
            memory_id=memory_id,
            deleted_at=deleted_at,
            updated_at=updated_at,
            server_version=server_version,
            sync_state_updates=sync_state_updates,
            change_log_row=change_log_row,
        )

    async def list_changes(
        self,
        source_system: str,
        workspace_id: Optional[str],
        cursor_seq: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        return await self.graph_store.list_sync_changes(
            source_system,
            workspace_id,
            cursor_seq,
            limit,
        )

    async def list_active_workspace_records(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        return await self.graph_store.list_active_workspace_records(source_system, workspace_id)

    async def get_state_summary(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        return await self.graph_store.get_sync_state_summary(source_system, workspace_id)
