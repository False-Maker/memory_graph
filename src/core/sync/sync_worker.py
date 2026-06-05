"""Push/pull worker for external source <-> Memory Graph sync."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

from src.core.sync.sync_api_client import SyncApiClient
from src.core.sync.sync_conflicts import SyncConflictStore
from src.core.sync.source_models import (
    SyncSourceConfig,
    SyncState,
    SyncStateRecord,
    WorkspaceSnapshot,
)
from src.core.sync.source_parser import WorkspaceSourceParser
from src.core.sync.sync_state_store import SyncStateStore


@dataclass
class PushSummary:
    """Summary of one push run."""

    scanned_records: int = 0
    pushed_records: int = 0
    restore_candidates: int = 0
    created: int = 0
    updated: int = 0
    noop: int = 0
    conflicts: int = 0
    rejected: int = 0
    marker_updates: int = 0
    deleted_remote_records: List[str] = field(default_factory=list)


@dataclass
class PullSummary:
    """Summary of one pull run."""

    processed_changes: int = 0
    applied_creates: int = 0
    applied_updates: int = 0
    applied_deletes: int = 0
    written_conflicts: int = 0
    skipped_echoes: int = 0


@dataclass
class PushPlan:
    """Preview of one push/restore run."""

    scanned_records: int = 0
    pending_records: int = 0
    restore_candidates: int = 0
    marker_candidates: int = 0


class SourceSyncWorker:
    """Coordinate local scanning and remote sync calls."""

    def __init__(
        self,
        config: SyncSourceConfig,
        client: Optional[SyncApiClient] = None,
        parser: Optional[WorkspaceSourceParser] = None,
        state_store: Optional[SyncStateStore] = None,
        conflict_store: Optional[SyncConflictStore] = None,
    ):
        self.config = config
        self.client = client or SyncApiClient(config)
        self.parser = parser or WorkspaceSourceParser(config)
        self.state_store = state_store or SyncStateStore(config)
        self.conflict_store = conflict_store or SyncConflictStore(config)

    def scan(self) -> WorkspaceSnapshot:
        """Scan the local workspace."""
        return self.parser.scan_workspace()

    def _new_mutation_id(self) -> str:
        return f"mut_{uuid.uuid4().hex[:12]}"

    def _should_enqueue_record(
        self,
        record,
        existing: Optional[SyncStateRecord],
        restore_only: bool = False,
    ) -> bool:
        """Decide whether one local record should be sent upstream."""
        if restore_only:
            return existing is not None and existing.sync_status == "deleted"

        if existing is None:
            return True

        return not (
            existing.last_checksum == record.content_checksum
            and existing.source_path == record.source_path
            and existing.sync_status != "deleted"
        )

    def plan_push(self, restore_only: bool = False) -> PushPlan:
        """Build a dry-run plan for push/bootstrap/restore commands."""
        state = self.state_store.load()
        snapshot = self.scan()
        plan = PushPlan(scanned_records=len(snapshot.records))

        for record in snapshot.records:
            existing = state.records.get(record.external_id)
            if not self._should_enqueue_record(record, existing, restore_only=restore_only):
                continue
            plan.pending_records += 1
            if existing is not None and existing.sync_status == "deleted":
                plan.restore_candidates += 1
            if not record.marker_present:
                plan.marker_candidates += 1

        return plan

    def _state_record_from_remote(
        self,
        external_id: str,
        source_path: str,
        checksum: str,
        server_version: Optional[int],
        client_mutation_id: Optional[str],
        memory_id: Optional[str],
        marker_present: bool,
        sync_status: str = "synced",
    ) -> SyncStateRecord:
        return SyncStateRecord(
            external_id=external_id,
            source_path=source_path,
            last_checksum=checksum,
            last_seen_server_version=server_version,
            last_client_mutation_id=client_mutation_id,
            memory_id=memory_id,
            marker_present=marker_present,
            sync_status=sync_status,
        )

    async def push(
        self,
        batch_size: int = 50,
        reconcile: bool = True,
        delete_missing: bool = True,
        restore_only: bool = False,
    ) -> PushSummary:
        """Push local changes to the remote server."""
        if restore_only and reconcile:
            raise ValueError("restore_only pushes cannot run reconcile")

        state = self.state_store.load()
        snapshot = self.scan()
        summary = PushSummary(scanned_records=len(snapshot.records))

        pending_upserts: List[Dict[str, object]] = []
        pending_records: Dict[str, object] = {}

        for record in snapshot.records:
            existing = state.records.get(record.external_id)
            if not self._should_enqueue_record(record, existing, restore_only=restore_only):
                continue
            if existing is not None and existing.sync_status == "deleted":
                summary.restore_candidates += 1

            mutation_id = self._new_mutation_id()
            pending_upserts.append(
                {
                    "external_id": record.external_id,
                    "source_path": record.source_path,
                    "record_type": record.record_type,
                    "title": record.title,
                    "content": record.content,
                    "tags": list(record.tags),
                    "content_checksum": record.content_checksum,
                    "external_updated_at": record.external_updated_at.isoformat(),
                    "external_revision": record.external_revision,
                    "base_server_version": existing.last_seen_server_version if existing else None,
                    "client_mutation_id": mutation_id,
                }
            )
            pending_records[record.external_id] = (record, mutation_id)

        marker_candidates = []

        if pending_upserts:
            async with self.client:
                for batch_start in range(0, len(pending_upserts), batch_size):
                    batch = pending_upserts[batch_start : batch_start + batch_size]
                    response = await self.client.batch_upsert(batch)
                    for result in response.get("results", []):
                        external_id = result["external_id"]
                        record, mutation_id = pending_records[external_id]
                        self.state_store.remember_mutation_id(state, mutation_id)
                        outcome = result["result"]
                        summary.pushed_records += 1

                        if outcome == "created":
                            summary.created += 1
                        elif outcome == "updated":
                            summary.updated += 1
                        elif outcome == "noop":
                            summary.noop += 1
                        elif outcome == "conflict":
                            summary.conflicts += 1
                        else:
                            summary.rejected += 1

                        if outcome in {"created", "updated", "noop"}:
                            self.state_store.update_record(
                                state,
                                self._state_record_from_remote(
                                    external_id=record.external_id,
                                    source_path=record.source_path,
                                    checksum=record.content_checksum,
                                    server_version=result.get("server_version"),
                                    client_mutation_id=mutation_id,
                                    memory_id=result.get("memory_id"),
                                    marker_present=record.marker_present,
                                    sync_status=result.get("sync_status") or "synced",
                                ),
                            )
                            if not record.marker_present:
                                marker_candidates.append(record)

                    self.state_store.save(state)

        if marker_candidates:
            summary.marker_updates = self.parser.write_markers(marker_candidates)
            if summary.marker_updates:
                refreshed = self.scan()
                for record in refreshed.records:
                    current = state.records.get(record.external_id)
                    if current is not None:
                        current.marker_present = record.marker_present
                self.state_store.save(state)

        if reconcile:
            scan_id = f"scan_{uuid.uuid4().hex[:12]}"
            async with self.client:
                reconcile_payload = await self.client.reconcile(
                    seen_external_ids=[record.external_id for record in self.scan().records],
                    scan_id=scan_id,
                    delete_missing=delete_missing,
                )
            deleted_external_ids = list(reconcile_payload.get("deleted_external_ids", []))
            summary.deleted_remote_records = deleted_external_ids
            for external_id in deleted_external_ids:
                self.state_store.remove_record(state, external_id)
            self.state_store.save(state)

        self.state_store.save(state)
        return summary

    async def pull(self, limit: int = 100) -> PullSummary:
        """Pull remote changes and write them back locally."""
        state = self.state_store.load()
        summary = PullSummary()

        async with self.client:
            payload = await self.client.get_changes(
                cursor=state.last_pulled_seq,
                limit=limit,
            )

        snapshot = self.scan()
        for change in payload.get("changes", []):
            summary.processed_changes += 1
            change_type = change["change_type"]
            external_id = change.get("external_id")
            mutation_id = change.get("client_mutation_id")
            record_payload = change.get("record") or {}

            if change.get("origin") == "client" and self.state_store.has_mutation_id(state, mutation_id):
                summary.skipped_echoes += 1
                continue

            if external_id is None:
                continue

            if change_type == "conflict":
                local_record = snapshot.by_external_id.get(external_id)
                self.conflict_store.write_conflict(
                    external_id=external_id,
                    source_path=local_record.source_path if local_record else None,
                    local_content=local_record.content if local_record else None,
                    remote_record=record_payload,
                    server_version=change.get("server_version"),
                )
                summary.written_conflicts += 1
                continue

            local_record = snapshot.by_external_id.get(external_id)

            if change_type in {"created", "updated", "restored"}:
                source_path = str(record_payload.get("source_path") or "")
                checksum = str(record_payload.get("content_checksum") or "")
                title = str(record_payload.get("title") or external_id)
                content = str(record_payload.get("content") or "")

                if local_record is not None:
                    self.parser.replace_record(
                        record=local_record,
                        title=title,
                        content=content,
                        external_id=external_id,
                    )
                    summary.applied_updates += 1
                else:
                    self.parser.append_inbox_record(record_payload)
                    summary.applied_creates += 1

                snapshot = self.scan()
                refreshed = snapshot.by_external_id.get(external_id)
                self.state_store.update_record(
                    state,
                    self._state_record_from_remote(
                        external_id=external_id,
                        source_path=refreshed.source_path if refreshed else source_path,
                        checksum=refreshed.content_checksum if refreshed else checksum,
                        server_version=change.get("server_version"),
                        client_mutation_id=mutation_id,
                        memory_id=change.get("memory_id"),
                        marker_present=refreshed.marker_present if refreshed else True,
                        sync_status="synced",
                    ),
                )
                continue

            if change_type == "deleted":
                if local_record is not None:
                    self.parser.delete_record(local_record)
                    summary.applied_deletes += 1
                    snapshot = self.scan()
                current = state.records.get(external_id)
                if current is not None:
                    current.sync_status = "deleted"
                else:
                    self.state_store.update_record(
                        state,
                        SyncStateRecord(
                            external_id=external_id,
                            source_path=str(record_payload.get("source_path") or ""),
                            last_checksum=str(record_payload.get("content_checksum") or ""),
                            last_seen_server_version=change.get("server_version"),
                            last_client_mutation_id=mutation_id,
                            memory_id=change.get("memory_id"),
                            marker_present=False,
                            sync_status="deleted",
                        ),
                    )

        state.last_pulled_seq = payload.get("next_cursor", state.last_pulled_seq)
        self.state_store.save(state)
        return summary

    async def sync(
        self,
        batch_size: int = 50,
        change_limit: int = 100,
        delete_missing: bool = True,
    ) -> Dict[str, object]:
        """Run one push followed by one pull."""
        push_summary = await self.push(
            batch_size=batch_size,
            reconcile=True,
            delete_missing=delete_missing,
        )
        pull_summary = await self.pull(limit=change_limit)
        return {
            "push": push_summary,
            "pull": pull_summary,
        }

    def get_local_state(self) -> SyncState:
        """Return the current persisted local state."""
        return self.state_store.load()

    async def bootstrap(self, batch_size: int = 50) -> PushSummary:
        """Initial full push for a workspace."""
        return await self.push(
            batch_size=batch_size,
            reconcile=False,
            delete_missing=False,
        )

    async def restore(self, batch_size: int = 50) -> PushSummary:
        """Restore records that are still marked deleted in local state."""
        return await self.push(
            batch_size=batch_size,
            reconcile=False,
            delete_missing=False,
            restore_only=True,
        )


def run_sync(
    worker: SourceSyncWorker,
    batch_size: int = 50,
    change_limit: int = 100,
    delete_missing: bool = True,
) -> Dict[str, object]:
    """Convenience sync runner for sync scripts."""
    return asyncio.run(
        worker.sync(
            batch_size=batch_size,
            change_limit=change_limit,
            delete_missing=delete_missing,
        )
    )
