"""Shared memory ingestion and deletion service."""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.entity_extractor import Entity, EntityExtractor, ExtractionResult
from src.core.graph_ingest_helpers import CanonicalGraphEvidenceBuilder, IngestTextUtils
from src.core.graph_store import GraphStore, get_graph_store
from src.core.llm_manager import LLMManager, get_llm_manager
from src.core.memory_record_builders import MemoryRecordBuilders
from src.core.sync.models import CanonicalGraphPayload
from src.core.vector_store import VectorStore, get_vector_store


@dataclass
class MemoryIngestResult:
    """Result of one memory ingest operation."""

    memory_id: str
    entities_count: int
    relationships_count: int
    server_version: int
    result: str


@dataclass
class MemoryDeleteResult:
    """Result of one memory delete operation."""

    memory_id: str
    deleted: bool
    server_version: Optional[int]
    sync_status: str


class MemoryService:
    """Shared service for legacy/manual memory ingestion and deletion."""

    EMBEDDING_TEXT_MAX_CHARS = 4000

    def __init__(
        self,
        llm: Optional[LLMManager] = None,
        vector_store: Optional[VectorStore] = None,
        graph_store: Optional[GraphStore] = None,
    ):
        self.llm = llm or get_llm_manager()
        self.vector_store = vector_store or get_vector_store()
        self.graph_store = graph_store or get_graph_store()
        self.extractor = EntityExtractor(self.llm)
        self._ingest_utils = IngestTextUtils(self.EMBEDDING_TEXT_MAX_CHARS)
        self._graph_evidence = CanonicalGraphEvidenceBuilder(
            normalize_text=self._ingest_utils.normalize_text,
            stable_hash=self._ingest_utils.stable_hash,
        )

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _coerce_datetime(self, value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _serialize_datetime(self, value: Any) -> Optional[str]:
        parsed = self._coerce_datetime(value)
        return parsed.isoformat() if parsed else None

    def _content_checksum(self, content: str) -> str:
        return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"

    def _should_extract_graph_evidence(
        self,
        source_path: Optional[str],
        metadata: Dict[str, Any],
    ) -> bool:
        """Skip graph extraction for generated summary artifacts."""
        return self._ingest_utils.should_extract_graph_evidence(
            source_path,
            skip_extraction=metadata.get("skip_extraction") is True,
        )

    def _metadata_changed(
        self,
        existing: Dict[str, Any],
        current_sync_state: Optional[Dict[str, Any]],
        current_vector_metadata: Optional[Dict[str, Any]],
        metadata: Dict[str, Any],
        source_path: Optional[str],
        record_type: str,
        title: Optional[str],
        tags: List[str],
        timestamp: Optional[str],
        external_revision: Optional[str],
    ) -> bool:
        return MemoryRecordBuilders.metadata_changed(
            existing,
            current_sync_state,
            current_vector_metadata=current_vector_metadata,
            metadata=metadata,
            source_path=source_path,
            record_type=record_type,
            title=title,
            tags=tags,
            timestamp=timestamp,
            external_revision=external_revision,
        )

    def _regex_hints_to_extraction(
        self,
        *,
        metadata: Dict[str, Any],
        content: str,
    ) -> ExtractionResult:
        """Convert regex hints carried by import metadata into extraction entities."""
        raw_hints = metadata.get("regex_entity_hints")
        if not isinstance(raw_hints, list):
            return ExtractionResult()

        entities: List[Entity] = []
        for index, hint in enumerate(raw_hints):
            if not isinstance(hint, dict):
                continue

            name = str(hint.get("text") or hint.get("name") or "").strip()
            if not name:
                continue

            entity_type = self._ingest_utils.normalize_text(hint.get("type")) or "concept"
            properties = {
                "detection_method": "regex",
                "frequency": int(hint.get("frequency", 1) or 1),
            }
            if hint.get("context"):
                properties["context"] = hint["context"]
            if isinstance(hint.get("message_indexes"), list) and hint["message_indexes"]:
                properties["message_indexes"] = list(hint["message_indexes"])
            if isinstance(hint.get("message_roles"), list) and hint["message_roles"]:
                properties["message_roles"] = list(hint["message_roles"])

            entities.append(
                Entity(
                    id=self._ingest_utils.stable_hash(
                        "regex",
                        entity_type,
                        self._ingest_utils.normalize_text(name),
                        str(index),
                    ),
                    name=name,
                    type=entity_type,
                    properties=properties,
                    source_text=content[:500],
                    confidence=float(hint.get("confidence", 0.8) or 0.8),
                )
            )

        return ExtractionResult(entities=entities)

    def _merge_extractions(
        self,
        primary: ExtractionResult,
        secondary: ExtractionResult,
    ) -> ExtractionResult:
        """Merge regex hint entities into the main extraction result conservatively."""
        if not secondary.entities:
            return primary

        merged_entities: Dict[tuple[str, str], Entity] = {}
        for entity in list(primary.entities) + list(secondary.entities):
            entity_name = self._ingest_utils.normalize_text(entity.name)
            entity_type = self._ingest_utils.normalize_text(entity.type) or "concept"
            if not entity_name:
                continue
            key = (entity_name, entity_type)
            current = merged_entities.get(key)
            if current is None or entity.confidence >= current.confidence:
                merged_entities[key] = entity

        return ExtractionResult(
            entities=list(merged_entities.values()),
            relationships=list(primary.relationships),
            facts=list(primary.facts),
            summary=primary.summary,
        )

    async def ingest_memory(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
        source_system: str = "manual",
        create_change_log: bool = True,
    ) -> MemoryIngestResult:
        """Create or update one memory and its canonical graph evidence."""
        metadata = dict(metadata or {})
        source_system = metadata.get("source") or source_system
        external_id = metadata.get("external_id")
        workspace_id = metadata.get("workspace_id")
        if external_id and workspace_id is None:
            workspace_id = "default"

        conversation_id = metadata.get("conversation_id")
        if external_id is None and conversation_id:
            external_id = f"{source_system}:{workspace_id or 'default'}:{conversation_id}"

        source_path = metadata.get("source_path")
        record_type = metadata.get("record_type") or source_system or "memory"
        title = metadata.get("title")
        tags = list(metadata.get("tags") or [])
        timestamp = self._serialize_datetime(metadata.get("external_updated_at") or metadata.get("timestamp"))
        external_revision = metadata.get("external_revision")
        content_checksum = metadata.get("content_checksum") or self._content_checksum(content)
        client_mutation_id = metadata.get("client_mutation_id") or f"server:{uuid.uuid4().hex[:12]}"

        existing = None
        if external_id:
            existing = await self.graph_store.get_memory_registry_by_external_key(
                source_system,
                workspace_id,
                external_id,
            )
        elif memory_id:
            existing = await self.graph_store.get_memory_registry(memory_id)

        current_sync_state = (
            await self.graph_store.get_memory_sync_state(existing["memory_id"])
            if existing else None
        )
        current_doc = (
            await self.vector_store.get_memory(existing["memory_id"])
            if existing else None
        )

        is_deleted = bool(existing and existing.get("deleted_at"))
        content_changed = existing is None or existing.get("content_checksum") != content_checksum
        metadata_changed = (
            existing is None
            or self._metadata_changed(
                existing=existing,
                current_sync_state=current_sync_state,
                current_vector_metadata=(getattr(current_doc, "metadata", None) if current_doc else None),
                metadata=metadata,
                source_path=source_path,
                record_type=record_type,
                title=title,
                tags=tags,
                timestamp=timestamp,
                external_revision=external_revision,
            )
            or is_deleted
        )
        vector_missing = bool(existing and current_doc is None and not is_deleted)

        if existing and not content_changed and not metadata_changed and not vector_missing:
            return MemoryIngestResult(
                memory_id=existing["memory_id"],
                entities_count=0,
                relationships_count=0,
                server_version=existing["server_version"],
                result="noop",
            )

        memory_id = existing["memory_id"] if existing else (memory_id or f"mem_{uuid.uuid4().hex[:12]}")
        previous_version = existing["server_version"] if existing else 0
        next_version = previous_version + 1
        changed_at = self._now_iso()
        created_at = existing["created_at"] if existing else changed_at
        replace_evidence = content_changed or existing is None or is_deleted or vector_missing
        canonical_payload = CanonicalGraphPayload()
        should_extract = self._should_extract_graph_evidence(source_path, metadata)
        regex_extraction = self._regex_hints_to_extraction(metadata=metadata, content=content)

        vector_metadata = dict(metadata)
        vector_metadata.update(
            {
                "source": source_system,
                "workspace_id": workspace_id,
                "external_id": external_id,
                "source_path": source_path,
                "record_type": record_type,
                "title": title,
                "tags": tags,
                "content_checksum": content_checksum,
                "external_updated_at": timestamp,
                "external_revision": external_revision,
            }
        )

        if replace_evidence:
            embeddings = await self.llm.embed([self._ingest_utils.embedding_text(content)])
            if should_extract:
                extraction = await self.extractor.extract(content)
                extraction = self._merge_extractions(extraction, regex_extraction)
                canonical_payload = self._graph_evidence.canonicalize_extraction(
                    extraction=extraction,
                    content=content,
                    created_at=changed_at,
                )
            await self.vector_store.upsert_memory(
                memory_id=memory_id,
                content=content,
                embedding=embeddings[0],
                metadata=vector_metadata,
            )
        else:
            await self.vector_store.update_memory(memory_id=memory_id, metadata=vector_metadata)

        registry_row = MemoryRecordBuilders.build_registry_row(
            memory_id=memory_id,
            source_system=source_system,
            workspace_id=workspace_id,
            external_id=external_id,
            source_path=source_path,
            record_type=record_type,
            title=title,
            tags=tags,
            content_checksum=content_checksum,
            timestamp=timestamp,
            created_at=created_at,
            updated_at=changed_at,
            deleted_at=None,
            server_version=next_version,
        )
        sync_state_row = MemoryRecordBuilders.build_sync_state_row(
            memory_id=memory_id,
            sync_mode="internal",
            ownership_mode="server_managed",
            sync_status="synced",
            last_client_mutation_id=client_mutation_id,
            last_client_seen_at=changed_at,
            last_server_change_at=changed_at,
            base_server_version=previous_version,
            external_revision=external_revision,
            external_updated_at=timestamp,
            tombstone=0,
        )

        change_log_row = None
        if create_change_log:
            change_type = "created" if not existing else ("restored" if is_deleted else "updated")
            change_log_row = MemoryRecordBuilders.build_change_log_row(
                memory_id=memory_id,
                source_system=source_system,
                workspace_id=workspace_id,
                external_id=external_id,
                change_type=change_type,
                origin="server",
                client_mutation_id=client_mutation_id,
                server_version=next_version,
                occurred_at=changed_at,
                payload=MemoryRecordBuilders.build_payload(
                    workspace_id=workspace_id,
                    external_id=external_id,
                    source_path=source_path,
                    record_type=record_type,
                    title=title,
                    content=content,
                    tags=tags,
                    content_checksum=content_checksum,
                    external_updated_at=timestamp,
                    external_revision=external_revision,
                    metadata=vector_metadata,
                ),
            )

        await self.graph_store.upsert_memory_record(
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
            await self.graph_store.mark_community_dirty(reason=f"{source_system}:{record_type}:{memory_id}")

        return MemoryIngestResult(
            memory_id=memory_id,
            entities_count=len(canonical_payload.entities) if replace_evidence else 0,
            relationships_count=len(canonical_payload.relationships) if replace_evidence else 0,
            server_version=next_version,
            result="created" if not existing else ("restored" if is_deleted else "updated"),
        )

    async def delete_memory(
        self,
        memory_id: str,
        client_mutation_id: Optional[str] = None,
        create_change_log: bool = True,
    ) -> MemoryDeleteResult:
        """Delete one memory and tombstone registry/evidence when available."""
        existing = await self.graph_store.get_memory_registry(memory_id)
        if existing is None:
            deleted = await self.vector_store.delete_memory(memory_id)
            return MemoryDeleteResult(
                memory_id=memory_id,
                deleted=deleted,
                server_version=None,
                sync_status="deleted" if deleted else "not_found",
            )

        if existing.get("deleted_at"):
            return MemoryDeleteResult(
                memory_id=memory_id,
                deleted=False,
                server_version=existing["server_version"],
                sync_status="deleted",
            )

        current_sync_state = await self.graph_store.get_memory_sync_state(memory_id)
        current_doc = await self.vector_store.get_memory(memory_id)
        await self.vector_store.delete_memory(memory_id)

        changed_at = self._now_iso()
        next_version = existing["server_version"] + 1
        client_mutation_id = client_mutation_id or f"server:{uuid.uuid4().hex[:12]}"
        sync_state_row = MemoryRecordBuilders.build_sync_state_row(
            memory_id=memory_id,
            sync_mode=(current_sync_state or {}).get("sync_mode", "internal"),
            ownership_mode=(current_sync_state or {}).get("ownership_mode", "server_managed"),
            sync_status="deleted",
            last_client_mutation_id=client_mutation_id,
            last_client_seen_at=changed_at,
            last_server_change_at=changed_at,
            base_server_version=existing["server_version"],
            external_revision=(current_sync_state or {}).get("external_revision"),
            external_updated_at=(current_sync_state or {}).get("external_updated_at"),
            tombstone=1,
        )

        change_log_row = None
        if create_change_log:
            change_log_row = MemoryRecordBuilders.build_change_log_row(
                memory_id=memory_id,
                source_system=existing["source_system"],
                workspace_id=existing.get("workspace_id"),
                external_id=existing.get("external_id"),
                change_type="deleted",
                origin="server",
                client_mutation_id=client_mutation_id,
                server_version=next_version,
                occurred_at=changed_at,
                payload=MemoryRecordBuilders.build_payload_from_registry(
                    existing,
                    current_sync_state,
                    current_doc.content if current_doc else None,
                    current_vector_metadata=(getattr(current_doc, "metadata", None) if current_doc else None),
                ),
            )

        await self.graph_store.tombstone_memory_record(
            memory_id=memory_id,
            deleted_at=changed_at,
            updated_at=changed_at,
            server_version=next_version,
            sync_state_updates=sync_state_row,
            change_log_row=change_log_row,
        )
        await self.graph_store.mark_community_dirty(
            reason=f"{existing['source_system']}:{existing.get('record_type') or 'memory'}:{memory_id}:deleted"
        )

        return MemoryDeleteResult(
            memory_id=memory_id,
            deleted=True,
            server_version=next_version,
            sync_status="deleted",
        )


_memory_service: Optional[MemoryService] = None


def get_memory_service() -> MemoryService:
    """Get the shared memory service singleton."""
    global _memory_service
    if _memory_service is None:
        _memory_service = MemoryService()
    return _memory_service
