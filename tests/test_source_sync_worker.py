"""Tests for the generic source sync worker."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.sync.source_models import SyncSourceConfig, SyncStateRecord
from src.core.sync.sync_state_store import SyncStateStore
from src.core.sync.sync_worker import SourceSyncWorker


class TestSourceSyncWorker:
    """Push/pull flows for the local sync client."""

    @pytest.mark.asyncio
    async def test_push_writes_marker_and_updates_state(self, temp_dir):
        """Successful push should persist state and backfill markers."""
        workspace = temp_dir
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        target = memory_dir / "2026-03-23.md"
        target.write_text(
            "# 2026-03-23\n\n"
            "## Decisions\n\n"
            "### Choose PostgreSQL\n"
            "Use PostgreSQL as the main database.\n",
            encoding="utf-8",
        )

        config = SyncSourceConfig(
            workspace_root=workspace,
            workspace_id="workspace-main",
            state_path=workspace / ".state" / "memory-graph-sync.json",
            conflicts_dir=workspace / ".conflicts",
        )
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        async def batch_upsert(records):
            return {
                "results": [
                    {
                        "external_id": records[0]["external_id"],
                        "memory_id": "mem_123",
                        "result": "created",
                        "server_version": 1,
                        "sync_status": "synced",
                    }
                ]
            }

        client.batch_upsert = AsyncMock(side_effect=batch_upsert)
        client.reconcile = AsyncMock(
            return_value={
                "scan_id": "scan_test",
                "missing_external_ids": [],
                "deleted_external_ids": [],
                "active_count": 1,
            }
        )

        worker = SourceSyncWorker(config=config, client=client)
        summary = await worker.push(batch_size=10)

        assert summary.created == 1
        assert summary.marker_updates == 1
        state_payload = json.loads(config.resolved_state_path().read_text(encoding="utf-8"))
        assert len(state_payload["records"]) == 1
        updated_file = target.read_text(encoding="utf-8")
        assert "<!-- mg:id=external:workspace-main:decision_" in updated_file

    @pytest.mark.asyncio
    async def test_pull_creates_inbox_record_and_conflict_file(self, temp_dir):
        """Pull should write remote-only records to inbox and conflicts to disk."""
        workspace = temp_dir
        (workspace / "memory").mkdir(parents=True, exist_ok=True)
        config = SyncSourceConfig(
            workspace_root=workspace,
            workspace_id="workspace-main",
            state_path=workspace / ".state" / "memory-graph-sync.json",
            conflicts_dir=workspace / ".conflicts",
        )
        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get_changes = AsyncMock(
            return_value={
                "next_cursor": 2,
                "changes": [
                    {
                        "seq": 1,
                        "change_type": "created",
                        "origin": "server",
                        "client_mutation_id": None,
                        "external_id": "external:workspace-main:decision_remote",
                        "memory_id": "mem_remote",
                        "server_version": 3,
                        "occurred_at": "2026-03-23T00:00:00+00:00",
                        "record": {
                            "external_id": "external:workspace-main:decision_remote",
                            "source_path": "memory/remote.md",
                            "record_type": "decision",
                            "title": "Remote Decision",
                            "content": "Remote content",
                            "tags": ["remote"],
                            "content_checksum": "sha256:remote",
                        },
                    },
                    {
                        "seq": 2,
                        "change_type": "conflict",
                        "origin": "server",
                        "client_mutation_id": "mut_conflict",
                        "external_id": "external:workspace-main:decision_conflict",
                        "memory_id": "mem_conflict",
                        "server_version": 4,
                        "occurred_at": "2026-03-23T00:00:00+00:00",
                        "record": {
                            "external_id": "external:workspace-main:decision_conflict",
                            "title": "Conflict Decision",
                            "content": "Remote conflicting content",
                        },
                    },
                ],
            }
        )

        worker = SourceSyncWorker(config=config, client=client)
        summary = await worker.pull(limit=50)

        assert summary.applied_creates == 1
        assert summary.written_conflicts == 1
        inbox_files = list(config.resolved_inbox_dir().glob("*.md"))
        assert len(inbox_files) == 1
        inbox_text = inbox_files[0].read_text(encoding="utf-8")
        assert "Remote Decision" in inbox_text
        conflict_files = list(config.resolved_conflicts_dir().glob("*.md"))
        assert len(conflict_files) == 1
        assert "Remote conflicting content" in conflict_files[0].read_text(encoding="utf-8")

    @pytest.mark.asyncio
    async def test_restore_pushes_only_deleted_state_records(self, temp_dir):
        """Restore should only upsert records that local state still marks deleted."""
        workspace = temp_dir
        memory_dir = workspace / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        target = memory_dir / "2026-03-23.md"
        target.write_text(
            "# 2026-03-23\n\n"
            "## Decisions\n\n"
            "### Restore Me\n"
            "<!-- mg:id=external:workspace-main:decision_restore -->\n\n"
            "Bring this record back.\n\n"
            "### Leave Me Alone\n"
            "<!-- mg:id=external:workspace-main:decision_synced -->\n\n"
            "Already synced.\n",
            encoding="utf-8",
        )

        config = SyncSourceConfig(
            workspace_root=workspace,
            workspace_id="workspace-main",
            state_path=workspace / ".state" / "memory-graph-sync.json",
            conflicts_dir=workspace / ".conflicts",
        )
        state_store = SyncStateStore(config)
        state = state_store.load()
        state.records["external:workspace-main:decision_restore"] = SyncStateRecord(
            external_id="external:workspace-main:decision_restore",
            source_path="memory/2026-03-23.md",
            last_checksum="sha256:old-restore",
            last_seen_server_version=7,
            last_client_mutation_id="mut_old_restore",
            memory_id="mem_restore",
            marker_present=True,
            sync_status="deleted",
        )
        state.records["external:workspace-main:decision_synced"] = SyncStateRecord(
            external_id="external:workspace-main:decision_synced",
            source_path="memory/2026-03-23.md",
            last_checksum="sha256:old-synced",
            last_seen_server_version=3,
            last_client_mutation_id="mut_old_synced",
            memory_id="mem_synced",
            marker_present=True,
            sync_status="synced",
        )
        state_store.save(state)

        client = MagicMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)

        async def batch_upsert(records):
            assert [record["external_id"] for record in records] == [
                "external:workspace-main:decision_restore"
            ]
            return {
                "results": [
                    {
                        "external_id": "external:workspace-main:decision_restore",
                        "memory_id": "mem_restore",
                        "result": "updated",
                        "server_version": 8,
                        "sync_status": "synced",
                    }
                ]
            }

        client.batch_upsert = AsyncMock(side_effect=batch_upsert)

        worker = SourceSyncWorker(config=config, client=client, state_store=state_store)
        plan = worker.plan_push(restore_only=True)
        summary = await worker.restore(batch_size=10)

        assert plan.pending_records == 1
        assert plan.restore_candidates == 1
        assert summary.pushed_records == 1
        assert summary.restore_candidates == 1
        assert summary.updated == 1
        saved_state = state_store.load()
        assert saved_state.records["external:workspace-main:decision_restore"].sync_status == "synced"
        assert saved_state.records["external:workspace-main:decision_synced"].sync_status == "synced"
