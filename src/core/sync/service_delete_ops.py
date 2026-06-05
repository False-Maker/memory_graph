"""Delete/tombstone flow helpers for the generic sync service."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional


class SyncServiceDeleteOps:
    """Own delete/tombstone flows for SyncService."""

    def __init__(
        self,
        *,
        source_system: str,
        builders: Any,
        now_iso: Callable[[], str],
        maybe_await: Callable[[Any], Any],
        get_graph_store: Callable[[], Any],
    ) -> None:
        self._source_system = source_system
        self._builders = builders
        self._now_iso = now_iso
        self._maybe_await = maybe_await
        self._get_graph_store = get_graph_store

    async def mark_community_dirty(
        self,
        *,
        record_type: Optional[str],
        memory_id: str,
        suffix: Optional[str] = None,
    ) -> None:
        """Mark derived communities stale for one synced memory."""
        reason = f"{self._source_system}:{record_type or 'memory'}:{memory_id}"
        if suffix:
            reason = f"{reason}:{suffix}"
        await self._maybe_await(self._get_graph_store().mark_community_dirty(reason=reason))

    async def tombstone_existing_record(
        self,
        *,
        repository: Any,
        vector_store: Any,
        existing: Dict[str, Any],
        current_sync_state: Optional[Dict[str, Any]],
        workspace_id: str,
        external_id: str,
        client_mutation_id: str,
        base_server_version: int,
        external_revision: Optional[str],
    ) -> int:
        """Delete vector state, tombstone graph state, and mark communities dirty."""
        current_doc = await vector_store.get_memory(existing["memory_id"])
        payload = self._builders.build_payload_from_registry(
            registry_row=existing,
            sync_state_row=current_sync_state,
            content=current_doc.content if current_doc else None,
            current_vector_metadata=(getattr(current_doc, "metadata", None) if current_doc else None),
        )
        await vector_store.delete_memory(existing["memory_id"])

        changed_at = self._now_iso()
        next_version = existing["server_version"] + 1
        sync_state_row = self._builders.build_tombstone_sync_state_row(
            memory_id=existing["memory_id"],
            current_sync_state=current_sync_state,
            changed_at=changed_at,
            client_mutation_id=client_mutation_id,
            base_server_version=base_server_version,
            external_revision=external_revision,
            external_updated_at=(current_sync_state or {}).get("external_updated_at"),
        )
        change_log_row = self._builders.build_change_log_row(
            memory_id=existing["memory_id"],
            workspace_id=workspace_id,
            external_id=external_id,
            change_type="deleted",
            server_version=next_version,
            occurred_at=changed_at,
            payload=payload,
            client_mutation_id=client_mutation_id,
        )
        await repository.tombstone_memory(
            memory_id=existing["memory_id"],
            deleted_at=changed_at,
            updated_at=changed_at,
            server_version=next_version,
            sync_state_updates=sync_state_row,
            change_log_row=change_log_row,
        )
        await self.mark_community_dirty(
            record_type=existing.get("record_type"),
            memory_id=existing["memory_id"],
            suffix="deleted",
        )
        return next_version
