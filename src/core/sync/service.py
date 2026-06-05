"""Sync service for external memory sources."""

import inspect
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.api.schemas.sync import (
    SyncBatchUpsertRequest,
    SyncBatchUpsertResponse,
    SyncDeleteRequest,
    SyncDeleteResponse,
    SyncReconcileRequest,
)
from src.core.entity_extractor import EntityExtractor
from src.core.graph_store import get_graph_store
from src.core.graph_ingest_helpers import CanonicalGraphEvidenceBuilder
from src.core.llm_manager import get_llm_manager
from src.core.sync.repository import SyncRepository
from src.core.sync.service_builders import SyncServiceBuilders
from src.core.sync.service_flow_ops import SyncServiceFlowOps
from src.core.vector_store import get_vector_store


class SyncConflictError(Exception):
    """Raised when a sync write sees a stale server version."""

    def __init__(self, detail: str, current_version: int):
        super().__init__(detail)
        self.detail = detail
        self.current_version = current_version


class SyncNotFoundError(Exception):
    """Raised when a sync record does not exist."""


class SyncService:
    """Coordinates sync API requests across vector and graph storage."""

    SYNC_MODE = "two_way"
    OWNERSHIP_MODE = "shared_with_external_anchor"
    EMBEDDING_TEXT_MAX_CHARS = 4000

    def __init__(self) -> None:
        self._flow_ops_by_source_system: Dict[str, SyncServiceFlowOps] = {}

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    async def _maybe_await(self, value: Any):
        """Await async call results while tolerating sync-compatible mocks."""
        if inspect.isawaitable(value):
            return await value
        return value

    def _normalize_source_system(self, source_system: str | None) -> str:
        normalized = (source_system or "").strip().lower()
        return normalized or "external"

    def _batch_dedupe_key(self, record: Any) -> tuple[str, str, str]:
        """Build a lightweight semantic key to skip duplicate records in one batch."""
        return (
            str(record.external_id),
            str(record.content_checksum),
            str(record.external_revision or ""),
        )

    def _get_flow_ops(self, source_system: str) -> SyncServiceFlowOps:
        """Return a source-specific flow facade."""
        normalized_source = self._normalize_source_system(source_system)
        existing = self._flow_ops_by_source_system.get(normalized_source)
        if existing is not None:
            return existing

        builders = SyncServiceBuilders(
            source_system=normalized_source,
            sync_mode=self.SYNC_MODE,
            ownership_mode=self.OWNERSHIP_MODE,
            embedding_text_max_chars=self.EMBEDDING_TEXT_MAX_CHARS,
        )
        graph_evidence = CanonicalGraphEvidenceBuilder(
            normalize_text=builders.normalize_text,
            stable_hash=builders.stable_hash,
        )
        flow_ops = SyncServiceFlowOps(
            source_system=normalized_source,
            builders=builders,
            graph_evidence=graph_evidence,
            now_iso=self._now_iso,
            maybe_await=self._maybe_await,
            get_graph_store=get_graph_store,
            get_vector_store=get_vector_store,
            get_llm_manager=get_llm_manager,
            extractor_cls=EntityExtractor,
        )
        self._flow_ops_by_source_system[normalized_source] = flow_ops
        return flow_ops

    async def batch_upsert_source_memories(
        self,
        source_system: str,
        request: SyncBatchUpsertRequest,
    ) -> SyncBatchUpsertResponse:
        repository = SyncRepository(get_graph_store())
        results: List[Dict[str, Any]] = []
        flow_ops = self._get_flow_ops(source_system)
        seen_record_keys: set[tuple[str, str, str]] = set()

        for record in request.records:
            record_key = self._batch_dedupe_key(record)
            if record_key in seen_record_keys:
                results.append(
                    {
                        "external_id": record.external_id,
                        "memory_id": None,
                        "result": "noop",
                        "server_version": None,
                        "sync_status": "noop",
                        "detail": "duplicate record skipped in request batch",
                    }
                )
                continue

            seen_record_keys.add(record_key)
            try:
                results.append(
                    await flow_ops.process_upsert_record(
                        repository=repository,
                        workspace_id=request.workspace_id,
                        record=record,
                    )
                )
            except Exception as exc:
                results.append(
                    {
                        "external_id": record.external_id,
                        "memory_id": None,
                        "result": "rejected",
                        "server_version": None,
                        "sync_status": "rejected",
                        "detail": str(exc),
                    }
                )

        return SyncBatchUpsertResponse(results=results)

    async def delete_source_memory(
        self,
        source_system: str,
        workspace_id: str,
        external_id: str,
        request: SyncDeleteRequest,
    ) -> SyncDeleteResponse:
        repository = SyncRepository(get_graph_store())
        vector_store = get_vector_store()

        existing = await repository.get_memory_by_external_key(
            self._normalize_source_system(source_system),
            workspace_id,
            external_id,
        )
        if existing is None:
            raise SyncNotFoundError(f"Sync record not found: {external_id}")

        current_sync_state = await repository.get_memory_sync_state(existing["memory_id"])
        if existing.get("deleted_at"):
            return SyncDeleteResponse(
                external_id=external_id,
                memory_id=existing["memory_id"],
                result="noop",
                server_version=existing["server_version"],
                sync_status="deleted",
            )

        if request.base_server_version != existing["server_version"]:
            raise SyncConflictError(
                "base_server_version does not match current server version",
                existing["server_version"],
            )

        next_version = await self._get_flow_ops(source_system).tombstone_existing_record(
            repository=repository,
            vector_store=vector_store,
            existing=existing,
            current_sync_state=current_sync_state,
            workspace_id=workspace_id,
            external_id=external_id,
            client_mutation_id=request.client_mutation_id,
            base_server_version=request.base_server_version,
            external_revision=request.external_revision,
        )

        return SyncDeleteResponse(
            external_id=external_id,
            memory_id=existing["memory_id"],
            result="deleted",
            server_version=next_version,
            sync_status="deleted",
        )

    async def get_changes(
        self,
        source_system: str,
        workspace_id: str,
        cursor: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        repository = SyncRepository(get_graph_store())
        rows = await repository.list_changes(
            source_system=self._normalize_source_system(source_system),
            workspace_id=workspace_id,
            cursor_seq=cursor,
            limit=limit,
        )

        changes = []
        next_cursor = cursor
        for row in rows:
            next_cursor = row["seq"]
            changes.append(
                {
                    "seq": row["seq"],
                    "change_type": row["change_type"],
                    "origin": row["origin"],
                    "client_mutation_id": row.get("client_mutation_id"),
                    "external_id": row.get("external_id"),
                    "memory_id": row["memory_id"],
                    "server_version": row["server_version"],
                    "occurred_at": row["occurred_at"],
                    "record": json.loads(row["payload_json"]) if row.get("payload_json") else None,
                }
            )

        return {
            "next_cursor": next_cursor,
            "changes": changes,
        }

    async def reconcile_source(
        self,
        source_system: str,
        request: SyncReconcileRequest,
    ) -> Dict[str, Any]:
        repository = SyncRepository(get_graph_store())
        vector_store = get_vector_store()
        active_records = await repository.list_active_workspace_records(
            self._normalize_source_system(source_system),
            request.workspace_id,
        )
        active_by_external_id = {
            row["external_id"]: row
            for row in active_records
            if row.get("external_id")
        }
        seen_external_ids = set(request.seen_external_ids)
        missing_external_ids = sorted(
            external_id
            for external_id in active_by_external_id
            if external_id not in seen_external_ids
        )
        deleted_external_ids: List[str] = []

        if request.delete_missing:
            for external_id in missing_external_ids:
                existing = active_by_external_id[external_id]
                current_sync_state = await repository.get_memory_sync_state(existing["memory_id"])
                await self._get_flow_ops(source_system).tombstone_existing_record(
                    repository=repository,
                    vector_store=vector_store,
                    existing=existing,
                    current_sync_state=current_sync_state,
                    workspace_id=request.workspace_id,
                    external_id=external_id,
                    client_mutation_id=f"{request.scan_id}:{external_id}",
                    base_server_version=existing["server_version"],
                    external_revision=(current_sync_state or {}).get("external_revision"),
                )
                deleted_external_ids.append(external_id)

        state = await repository.get_state_summary(
            self._normalize_source_system(source_system),
            request.workspace_id,
        )
        return {
            "scan_id": request.scan_id,
            "missing_external_ids": missing_external_ids,
            "deleted_external_ids": deleted_external_ids,
            "active_count": state["active_count"],
        }

    async def get_state(self, source_system: str, workspace_id: str) -> Dict[str, Any]:
        repository = SyncRepository(get_graph_store())
        state = await repository.get_state_summary(
            self._normalize_source_system(source_system),
            workspace_id,
        )
        return {
            "workspace_id": workspace_id,
            "active_records": state["active_count"],
            "tombstones": state["tombstone_count"],
            "conflicts": state["conflict_count"],
            "last_change_seq": state["last_change_seq"],
            "last_server_change_at": state["last_server_change_at"],
        }


_sync_service: Optional[SyncService] = None


def get_sync_service() -> SyncService:
    """Get the sync service singleton."""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service
