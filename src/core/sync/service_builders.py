"""Builder helpers for the generic sync service."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.graph_ingest_helpers import IngestTextUtils
from src.core.memory_contract import metadata_contract_view
from src.core.memory_record_builders import MemoryRecordBuilders


class SyncServiceBuilders:
    """Build sync payloads, rows, and normalized values."""

    def __init__(
        self,
        *,
        source_system: str,
        sync_mode: str,
        ownership_mode: str,
        embedding_text_max_chars: int,
    ) -> None:
        self._source_system = source_system
        self._sync_mode = sync_mode
        self._ownership_mode = ownership_mode
        self._text_utils = IngestTextUtils(embedding_text_max_chars)

    def stable_hash(self, prefix: str, *parts: str) -> str:
        """Build a stable prefixed SHA256 hash."""
        return self._text_utils.stable_hash(prefix, *parts)

    def normalize_text(self, value: Optional[str]) -> str:
        """Normalize text for canonical comparisons."""
        return self._text_utils.normalize_text(value)

    def embedding_text(self, content: Optional[str]) -> str:
        """Trim oversized content before sending it to the embedding provider."""
        return self._text_utils.embedding_text(content)

    @staticmethod
    def serialize_json(value: Any) -> str:
        """Serialize JSON content consistently."""
        return IngestTextUtils.serialize_json(value)

    @staticmethod
    def serialize_datetime(value: Optional[datetime]) -> Optional[str]:
        """Serialize an optional datetime to ISO-8601."""
        return IngestTextUtils.serialize_datetime(value)

    def should_extract_graph_evidence(self, source_path: Optional[str]) -> bool:
        """Skip graph extraction for generated summary artifacts."""
        return self._text_utils.should_extract_graph_evidence(source_path)

    def build_vector_metadata(
        self,
        workspace_id: str,
        record: Any,
    ) -> Dict[str, Any]:
        """Build vector-store metadata from one sync record."""
        vector_metadata = metadata_contract_view(record.model_dump() if hasattr(record, "model_dump") else vars(record))
        vector_metadata.update(
            {
                "source": self._source_system,
                "workspace_id": workspace_id,
                "external_id": record.external_id,
                "source_path": record.source_path,
                "record_type": record.record_type,
                "title": record.title,
                "tags": list(record.tags),
                "content_checksum": record.content_checksum,
                "external_updated_at": self.serialize_datetime(record.external_updated_at),
                "external_revision": record.external_revision,
            }
        )
        return {
            "source": self._source_system,
            "workspace_id": workspace_id,
            "external_id": record.external_id,
            "source_path": record.source_path,
            "record_type": record.record_type,
            "title": record.title,
            "tags": list(record.tags),
            "content_checksum": record.content_checksum,
            "external_updated_at": self.serialize_datetime(record.external_updated_at),
            "external_revision": record.external_revision,
            **{
                key: value
                for key, value in vector_metadata.items()
                if key
                not in {
                    "source",
                    "workspace_id",
                    "external_id",
                    "source_path",
                    "record_type",
                    "title",
                    "tags",
                    "content_checksum",
                    "external_updated_at",
                    "external_revision",
                }
            },
        }

    def build_payload(
        self,
        workspace_id: str,
        record: Any,
        content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build a change-log payload from one sync record."""
        return MemoryRecordBuilders.build_payload(
            workspace_id=workspace_id,
            external_id=record.external_id,
            source_path=record.source_path,
            record_type=record.record_type,
            title=record.title,
            content=content if content is not None else record.content,
            tags=list(record.tags),
            content_checksum=record.content_checksum,
            external_updated_at=self.serialize_datetime(record.external_updated_at),
            external_revision=record.external_revision,
            metadata=self.build_vector_metadata(workspace_id, record),
        )

    def build_payload_from_registry(
        self,
        registry_row: Dict[str, Any],
        sync_state_row: Optional[Dict[str, Any]],
        content: Optional[str],
        current_vector_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a change-log payload from persisted registry rows."""
        return MemoryRecordBuilders.build_payload_from_registry(
            registry_row,
            sync_state_row,
            content,
            current_vector_metadata=current_vector_metadata,
        )

    def build_registry_row(
        self,
        *,
        memory_id: str,
        workspace_id: str,
        record: Any,
        server_version: int,
        created_at: str,
        updated_at: str,
        deleted_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build one memory_registry row."""
        return MemoryRecordBuilders.build_registry_row(
            memory_id=memory_id,
            source_system=self._source_system,
            workspace_id=workspace_id,
            external_id=record.external_id,
            source_path=record.source_path,
            record_type=record.record_type,
            title=record.title,
            tags=list(record.tags),
            content_checksum=record.content_checksum,
            timestamp=self.serialize_datetime(record.external_updated_at),
            created_at=created_at,
            updated_at=updated_at,
            deleted_at=deleted_at,
            server_version=server_version,
        )

    def build_sync_state_row(
        self,
        *,
        memory_id: str,
        record: Any,
        changed_at: str,
        sync_status: str = "synced",
        tombstone: int = 0,
    ) -> Dict[str, Any]:
        """Build a memory_sync_state row for normal upserts."""
        return MemoryRecordBuilders.build_sync_state_row(
            memory_id=memory_id,
            sync_mode=self._sync_mode,
            ownership_mode=self._ownership_mode,
            sync_status=sync_status,
            last_client_mutation_id=record.client_mutation_id,
            last_client_seen_at=changed_at,
            last_server_change_at=changed_at,
            base_server_version=record.base_server_version,
            external_revision=record.external_revision,
            external_updated_at=self.serialize_datetime(record.external_updated_at),
            tombstone=tombstone,
        )

    def build_conflict_sync_state_row(
        self,
        *,
        memory_id: str,
        current_sync_state: Optional[Dict[str, Any]],
        record: Any,
        changed_at: str,
    ) -> Dict[str, Any]:
        """Build a memory_sync_state row for conflicts."""
        current_sync_state = current_sync_state or {}
        return MemoryRecordBuilders.build_sync_state_row(
            memory_id=memory_id,
            sync_mode=current_sync_state.get("sync_mode", self._sync_mode),
            ownership_mode=current_sync_state.get("ownership_mode", self._ownership_mode),
            sync_status="conflict",
            last_client_mutation_id=record.client_mutation_id,
            last_client_seen_at=changed_at,
            last_server_change_at=current_sync_state.get("last_server_change_at", changed_at),
            base_server_version=record.base_server_version,
            external_revision=record.external_revision,
            external_updated_at=self.serialize_datetime(record.external_updated_at),
            tombstone=current_sync_state.get("tombstone", 0),
        )

    def build_tombstone_sync_state_row(
        self,
        *,
        memory_id: str,
        current_sync_state: Optional[Dict[str, Any]],
        changed_at: str,
        client_mutation_id: str,
        base_server_version: int,
        external_revision: Optional[str],
        external_updated_at: Optional[str],
    ) -> Dict[str, Any]:
        """Build a memory_sync_state row for tombstoned memories."""
        current_sync_state = current_sync_state or {}
        return MemoryRecordBuilders.build_sync_state_row(
            memory_id=memory_id,
            sync_mode=current_sync_state.get("sync_mode", self._sync_mode),
            ownership_mode=current_sync_state.get("ownership_mode", self._ownership_mode),
            sync_status="deleted",
            last_client_mutation_id=client_mutation_id,
            last_client_seen_at=changed_at,
            last_server_change_at=changed_at,
            base_server_version=base_server_version,
            external_revision=external_revision,
            external_updated_at=external_updated_at,
            tombstone=1,
        )

    def build_change_log_row(
        self,
        *,
        memory_id: str,
        workspace_id: str,
        external_id: str,
        change_type: str,
        server_version: int,
        occurred_at: str,
        payload: Optional[Dict[str, Any]],
        client_mutation_id: Optional[str],
        origin: str = "client",
    ) -> Dict[str, Any]:
        """Build one sync_change_log row."""
        return MemoryRecordBuilders.build_change_log_row(
            memory_id=memory_id,
            source_system=self._source_system,
            workspace_id=workspace_id,
            external_id=external_id,
            change_type=change_type,
            origin=origin,
            client_mutation_id=client_mutation_id,
            server_version=server_version,
            occurred_at=occurred_at,
            payload=payload,
        )

    def metadata_changed(
        self,
        existing: Dict[str, Any],
        current_sync_state: Optional[Dict[str, Any]],
        current_vector_metadata: Optional[Dict[str, Any]],
        record: Any,
    ) -> bool:
        """Return whether metadata fields changed relative to persisted rows."""
        return MemoryRecordBuilders.metadata_changed(
            existing,
            current_sync_state,
            current_vector_metadata=current_vector_metadata,
            metadata=self.build_vector_metadata(existing.get("workspace_id") or "default", record),
            source_path=record.source_path,
            record_type=record.record_type,
            title=record.title,
            tags=list(record.tags),
            timestamp=self.serialize_datetime(record.external_updated_at),
            external_revision=record.external_revision,
        )
