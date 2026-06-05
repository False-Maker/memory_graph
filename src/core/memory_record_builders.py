"""Shared payload/row builders for persisted memory records."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.core.graph_ingest_helpers import IngestTextUtils
from src.core.memory_contract import metadata_contract_view


class MemoryRecordBuilders:
    """Build shared payloads and SQLite rows for memory persistence flows."""

    @staticmethod
    def build_payload(
        *,
        workspace_id: Optional[str],
        external_id: Optional[str],
        source_path: Optional[str],
        record_type: Optional[str],
        title: Optional[str],
        content: Optional[str],
        tags: List[str],
        content_checksum: Optional[str],
        external_updated_at: Optional[str],
        external_revision: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a change-log payload from normalized fields."""
        payload = metadata_contract_view(metadata or {})
        payload.update(
            {
                "workspace_id": workspace_id,
                "external_id": external_id,
                "source_path": source_path,
                "record_type": record_type,
                "title": title,
                "content": content,
                "tags": list(tags),
                "content_checksum": content_checksum,
                "external_updated_at": external_updated_at,
                "external_revision": external_revision,
            }
        )
        return {
            "workspace_id": workspace_id,
            "external_id": external_id,
            "source_path": source_path,
            "record_type": record_type,
            "title": title,
            "content": content,
            "tags": list(tags),
            "content_checksum": content_checksum,
            "external_updated_at": external_updated_at,
            "external_revision": external_revision,
            **{
                key: value
                for key, value in payload.items()
                if key
                not in {
                    "workspace_id",
                    "external_id",
                    "source_path",
                    "record_type",
                    "title",
                    "content",
                    "tags",
                    "content_checksum",
                    "external_updated_at",
                    "external_revision",
                }
            },
        }

    @staticmethod
    def build_payload_from_registry(
        registry_row: Dict[str, Any],
        sync_state_row: Optional[Dict[str, Any]],
        content: Optional[str],
        current_vector_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Build a change-log payload from persisted registry rows."""
        metadata = metadata_contract_view(current_vector_metadata or {})
        metadata.update(
            {
                "source": metadata.get("source") or registry_row.get("source_system"),
                "workspace_id": metadata.get("workspace_id") or registry_row.get("workspace_id"),
                "external_id": metadata.get("external_id") or registry_row.get("external_id"),
                "source_path": metadata.get("source_path") or registry_row.get("source_path"),
                "record_type": metadata.get("record_type") or registry_row.get("record_type"),
                "title": metadata.get("title") or registry_row.get("title"),
                "tags": metadata.get("tags") or json.loads(registry_row.get("tags_json") or "[]"),
                "content_checksum": metadata.get("content_checksum") or registry_row.get("content_checksum"),
                "timestamp": metadata.get("timestamp") or registry_row.get("timestamp"),
                "external_updated_at": metadata.get("external_updated_at") or (sync_state_row or {}).get("external_updated_at"),
                "external_revision": metadata.get("external_revision") or (sync_state_row or {}).get("external_revision"),
            }
        )
        return MemoryRecordBuilders.build_payload(
            workspace_id=metadata.get("workspace_id"),
            external_id=metadata.get("external_id"),
            source_path=metadata.get("source_path"),
            record_type=metadata.get("record_type"),
            title=metadata.get("title"),
            content=content,
            tags=list(metadata.get("tags") or []),
            content_checksum=metadata.get("content_checksum"),
            external_updated_at=metadata.get("external_updated_at"),
            external_revision=metadata.get("external_revision"),
            metadata=metadata,
        )

    @staticmethod
    def build_registry_row(
        *,
        memory_id: str,
        source_system: str,
        workspace_id: Optional[str],
        external_id: Optional[str],
        source_path: Optional[str],
        record_type: Optional[str],
        title: Optional[str],
        tags: List[str],
        content_checksum: str,
        timestamp: Optional[str],
        created_at: str,
        updated_at: str,
        deleted_at: Optional[str],
        server_version: int,
    ) -> Dict[str, Any]:
        """Build one memory_registry row."""
        return {
            "memory_id": memory_id,
            "source_system": source_system,
            "workspace_id": workspace_id,
            "external_id": external_id,
            "source_path": source_path,
            "record_type": record_type,
            "title": title,
            "tags_json": IngestTextUtils.serialize_json(tags),
            "content_checksum": content_checksum,
            "timestamp": timestamp,
            "created_at": created_at,
            "updated_at": updated_at,
            "deleted_at": deleted_at,
            "server_version": server_version,
        }

    @staticmethod
    def build_sync_state_row(
        *,
        memory_id: str,
        sync_mode: str,
        ownership_mode: str,
        sync_status: str,
        last_client_mutation_id: Optional[str],
        last_client_seen_at: str,
        last_server_change_at: str,
        base_server_version: Optional[int],
        external_revision: Optional[str],
        external_updated_at: Optional[str],
        tombstone: int,
    ) -> Dict[str, Any]:
        """Build one memory_sync_state row."""
        return {
            "memory_id": memory_id,
            "sync_mode": sync_mode,
            "ownership_mode": ownership_mode,
            "sync_status": sync_status,
            "last_client_mutation_id": last_client_mutation_id,
            "last_client_seen_at": last_client_seen_at,
            "last_server_change_at": last_server_change_at,
            "base_server_version": base_server_version,
            "external_revision": external_revision,
            "external_updated_at": external_updated_at,
            "tombstone": tombstone,
        }

    @staticmethod
    def build_change_log_row(
        *,
        memory_id: str,
        source_system: str,
        workspace_id: Optional[str],
        external_id: Optional[str],
        change_type: str,
        origin: str,
        client_mutation_id: Optional[str],
        server_version: int,
        occurred_at: str,
        payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build one sync_change_log row."""
        return {
            "memory_id": memory_id,
            "source_system": source_system,
            "workspace_id": workspace_id,
            "external_id": external_id,
            "change_type": change_type,
            "origin": origin,
            "client_mutation_id": client_mutation_id,
            "server_version": server_version,
            "occurred_at": occurred_at,
            "payload_json": IngestTextUtils.serialize_json(payload) if payload is not None else None,
        }

    @staticmethod
    def metadata_changed(
        existing: Dict[str, Any],
        current_sync_state: Optional[Dict[str, Any]],
        *,
        current_vector_metadata: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]],
        source_path: Optional[str],
        record_type: Optional[str],
        title: Optional[str],
        tags: List[str],
        timestamp: Optional[str],
        external_revision: Optional[str],
    ) -> bool:
        """Return whether persisted metadata differs from current inputs."""
        persisted_metadata = metadata_contract_view(current_vector_metadata or {})
        persisted_metadata.update(
            {
                "source": persisted_metadata.get("source") or existing.get("source_system"),
                "workspace_id": persisted_metadata.get("workspace_id") or existing.get("workspace_id"),
                "external_id": persisted_metadata.get("external_id") or existing.get("external_id"),
                "source_path": persisted_metadata.get("source_path") or existing.get("source_path"),
                "record_type": persisted_metadata.get("record_type") or existing.get("record_type"),
                "title": persisted_metadata.get("title") or existing.get("title"),
                "tags": persisted_metadata.get("tags") or json.loads(existing.get("tags_json") or "[]"),
                "timestamp": persisted_metadata.get("timestamp") or existing.get("timestamp"),
                "content_checksum": persisted_metadata.get("content_checksum") or existing.get("content_checksum"),
                "external_revision": persisted_metadata.get("external_revision") or (current_sync_state or {}).get("external_revision"),
                "external_updated_at": persisted_metadata.get("external_updated_at") or (current_sync_state or {}).get("external_updated_at"),
            }
        )
        incoming_metadata = metadata_contract_view(metadata or {})
        incoming_metadata.update(
            {
                "workspace_id": incoming_metadata.get("workspace_id") or existing.get("workspace_id"),
                "external_id": incoming_metadata.get("external_id") or existing.get("external_id"),
                "source_path": source_path,
                "record_type": record_type,
                "title": title,
                "tags": list(tags),
                "timestamp": timestamp,
                "content_checksum": incoming_metadata.get("content_checksum") or existing.get("content_checksum"),
                "external_revision": external_revision,
                "external_updated_at": incoming_metadata.get("external_updated_at") or timestamp,
            }
        )
        return persisted_metadata != incoming_metadata
