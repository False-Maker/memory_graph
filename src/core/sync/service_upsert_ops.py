"""Upsert/conflict flow helpers for the generic sync service."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, Optional

from src.core.sync.models import CanonicalGraphPayload


class SyncServiceUpsertOps:
    """Own upsert/conflict flows for SyncService."""

    def __init__(
        self,
        *,
        source_system: str,
        builders: Any,
        graph_evidence: Any,
        now_iso: Callable[[], str],
        get_vector_store: Callable[[], Any],
        get_llm_manager: Callable[[], Any],
        extractor_cls: type,
        mark_community_dirty: Callable[..., Any],
    ) -> None:
        self._source_system = source_system
        self._builders = builders
        self._graph_evidence = graph_evidence
        self._now_iso = now_iso
        self._get_vector_store = get_vector_store
        self._get_llm_manager = get_llm_manager
        self._extractor_cls = extractor_cls
        self._mark_community_dirty = mark_community_dirty

    async def record_conflict(
        self,
        *,
        repository: Any,
        existing: Dict[str, Any],
        current_sync_state: Optional[Dict[str, Any]],
        workspace_id: str,
        record: Any,
        current_content: Optional[str],
        current_metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Persist a conflict marker without replacing graph evidence."""
        changed_at = self._now_iso()
        registry_row = dict(existing)
        sync_state_row = self._builders.build_conflict_sync_state_row(
            memory_id=existing["memory_id"],
            current_sync_state=current_sync_state,
            record=record,
            changed_at=changed_at,
        )
        payload = self._builders.build_payload_from_registry(
            existing,
            current_sync_state,
            current_content,
            current_vector_metadata=current_metadata,
        )
        change_log_row = self._builders.build_change_log_row(
            memory_id=existing["memory_id"],
            workspace_id=workspace_id,
            external_id=record.external_id,
            change_type="conflict",
            server_version=existing["server_version"],
            occurred_at=changed_at,
            payload=payload,
            client_mutation_id=record.client_mutation_id,
            origin="server",
        )
        await repository.save_memory(
            registry_row=registry_row,
            sync_state_row=sync_state_row,
            change_log_row=change_log_row,
            replace_evidence=False,
        )

    async def process_upsert_record(
        self,
        *,
        repository: Any,
        workspace_id: str,
        record: Any,
    ) -> Dict[str, Any]:
        """Run the upsert flow for one external sync record."""
        vector_store = self._get_vector_store()
        llm = self._get_llm_manager()
        extractor = self._extractor_cls(llm)

        existing = await repository.get_memory_by_external_key(
            self._source_system,
            workspace_id,
            record.external_id,
        )
        current_sync_state = (
            await repository.get_memory_sync_state(existing["memory_id"])
            if existing else None
        )
        current_doc = (
            await vector_store.get_memory(existing["memory_id"])
            if existing else None
        )

        is_deleted = bool(existing and existing.get("deleted_at"))
        content_changed = existing is None or existing.get("content_checksum") != record.content_checksum
        metadata_changed = (
            existing is None
            or self._builders.metadata_changed(
                existing,
                current_sync_state,
                getattr(current_doc, "metadata", None) if current_doc else None,
                record,
            )
            or is_deleted
        )
        vector_missing = bool(existing and current_doc is None and not is_deleted)

        if existing and not content_changed and not metadata_changed and not vector_missing:
            return {
                "external_id": record.external_id,
                "memory_id": existing["memory_id"],
                "result": "noop",
                "server_version": existing["server_version"],
                "sync_status": (current_sync_state or {}).get("sync_status", "synced"),
            }

        if existing and (content_changed or metadata_changed or vector_missing):
            if record.base_server_version is None:
                return {
                    "external_id": record.external_id,
                    "memory_id": existing["memory_id"],
                    "result": "rejected",
                    "server_version": existing["server_version"],
                    "sync_status": (current_sync_state or {}).get("sync_status", "synced"),
                    "detail": "base_server_version is required for updates",
                }

            if record.base_server_version != existing["server_version"]:
                await self.record_conflict(
                    repository=repository,
                    existing=existing,
                    current_sync_state=current_sync_state,
                    workspace_id=workspace_id,
                    record=record,
                    current_content=current_doc.content if current_doc else None,
                    current_metadata=(getattr(current_doc, "metadata", None) if current_doc else None),
                )
                return {
                    "external_id": record.external_id,
                    "memory_id": existing["memory_id"],
                    "result": "conflict",
                    "server_version": existing["server_version"],
                    "sync_status": "conflict",
                    "detail": "base_server_version does not match current server version",
                }

        memory_id = existing["memory_id"] if existing else f"mem_{uuid.uuid4().hex[:12]}"
        previous_version = existing["server_version"] if existing else 0
        next_version = previous_version + 1
        changed_at = self._now_iso()
        created_at = existing["created_at"] if existing else changed_at
        vector_metadata = self._builders.build_vector_metadata(workspace_id, record)

        replace_evidence = content_changed or existing is None or is_deleted or vector_missing
        reusable_embedding = (
            current_doc.embedding
            if current_doc is not None and not content_changed and current_doc.embedding
            else None
        )
        canonical_payload = CanonicalGraphPayload()
        should_extract = self._builders.should_extract_graph_evidence(record.source_path)

        if replace_evidence:
            embedding = reusable_embedding
            if embedding is None:
                embeddings = await llm.embed([self._builders.embedding_text(record.content)])
                embedding = embeddings[0]
            if should_extract:
                extraction = await extractor.extract(record.content)
                canonical_payload = self._graph_evidence.canonicalize_extraction(
                    extraction=extraction,
                    content=record.content,
                    created_at=changed_at,
                )
            await vector_store.upsert_memory(
                memory_id=memory_id,
                content=record.content,
                embedding=embedding,
                metadata=vector_metadata,
            )
        else:
            await vector_store.update_memory(
                memory_id=memory_id,
                metadata=vector_metadata,
            )

        registry_row = self._builders.build_registry_row(
            memory_id=memory_id,
            workspace_id=workspace_id,
            record=record,
            server_version=next_version,
            created_at=created_at,
            updated_at=changed_at,
            deleted_at=None,
        )
        sync_state_row = self._builders.build_sync_state_row(
            memory_id=memory_id,
            record=record,
            changed_at=changed_at,
            sync_status="synced",
            tombstone=0,
        )
        change_type = "created" if not existing else ("restored" if is_deleted else "updated")
        change_log_row = self._builders.build_change_log_row(
            memory_id=memory_id,
            workspace_id=workspace_id,
            external_id=record.external_id,
            change_type=change_type,
            server_version=next_version,
            occurred_at=changed_at,
            payload=self._builders.build_payload(workspace_id, record),
            client_mutation_id=record.client_mutation_id,
        )

        await repository.save_memory(
            registry_row=registry_row,
            sync_state_row=sync_state_row,
            entities=canonical_payload.entities,
            mentions=canonical_payload.mentions,
            relationships=canonical_payload.relationships,
            relationship_evidence=canonical_payload.relationship_evidence,
            change_log_row=change_log_row,
            replace_evidence=replace_evidence,
        )

        if replace_evidence:
            await self._mark_community_dirty(record_type=record.record_type, memory_id=memory_id)

        return {
            "external_id": record.external_id,
            "memory_id": memory_id,
            "result": "created" if not existing else "updated",
            "server_version": next_version,
            "sync_status": "synced",
        }
