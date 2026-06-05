"""Focused tests for /api/v1/sync endpoints."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _expected_collection_diagnostics(**overrides):
    payload = {
        "applied_filters": {},
        "server_side_filtered": False,
        "truncated": False,
        "candidate_window": None,
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class TestSyncEndpoint:
    """Test /api/v1/sync endpoints."""

    @pytest.mark.asyncio
    async def test_list_sync_source_settings_returns_saved_sources(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            """
{
  "version": 1,
  "sources": [
    {
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "/tmp/workspace-notes",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }
  ]
}
            """.strip(),
            encoding="utf-8",
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            response = await client.get("/api/v1/sync/sources/settings")

        assert response.status_code == 200
        assert response.json() == {
            "sources": [
                {
                    "source_id": "src-1",
                    "label": "Project Notes",
                    "source_system": "notes",
                    "workspace_id": "workspace-notes",
                    "workspace_root": "/tmp/workspace-notes",
                    "source_paths": ["notes/**/*.md"],
                    "updated_at": "2026-04-01T10:00:00Z",
                }
            ]
        }

    @pytest.mark.asyncio
    async def test_create_sync_source_setting_persists_source(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            response = await client.post(
                "/api/v1/sync/sources/settings",
                json={
                    "label": "Project Notes",
                    "source_system": "notes",
                    "workspace_id": "workspace-notes",
                    "workspace_root": "/tmp/workspace-notes",
                    "source_paths": ["notes/**/*.md", "journal/*.md"],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["label"] == "Project Notes"
        assert body["source_system"] == "notes"
        assert body["workspace_id"] == "workspace-notes"
        assert body["workspace_root"] == "/tmp/workspace-notes"
        assert body["source_paths"] == ["notes/**/*.md", "journal/*.md"]
        assert body["source_id"]

        saved = settings_path.read_text(encoding="utf-8")
        assert "Project Notes" in saved
        assert "notes/**/*.md" in saved

    @pytest.mark.asyncio
    async def test_update_sync_source_setting_overwrites_existing_source(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            """
{
  "version": 1,
  "sources": [
    {
      "source_id": "src-1",
      "label": "Old",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "/tmp/old",
      "source_paths": ["old/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }
  ]
}
            """.strip(),
            encoding="utf-8",
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            response = await client.put(
                "/api/v1/sync/sources/settings/src-1",
                json={
                    "label": "Updated",
                    "source_system": "project-notes",
                    "workspace_id": "workspace-alpha",
                    "workspace_root": "/tmp/alpha",
                    "source_paths": ["alpha/**/*.md"],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["source_id"] == "src-1"
        assert body["label"] == "Updated"
        assert body["source_system"] == "project-notes"
        assert body["workspace_id"] == "workspace-alpha"
        assert body["source_paths"] == ["alpha/**/*.md"]
        saved = settings_path.read_text(encoding="utf-8")
        assert "Updated" in saved
        assert "Old" not in saved

    @pytest.mark.asyncio
    async def test_delete_sync_source_setting_removes_source(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            """
{
  "version": 1,
  "sources": [
    {
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "/tmp/workspace-notes",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }
  ]
}
            """.strip(),
            encoding="utf-8",
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            response = await client.request("DELETE", "/api/v1/sync/sources/settings/src-1")

        assert response.status_code == 200
        assert response.json() == {"success": True, "source_id": "src-1"}
        saved = settings_path.read_text(encoding="utf-8")
        assert '"sources": []' in saved

    @pytest.mark.asyncio
    async def test_push_sync_source_setting_runs_worker_push(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            f"""
{{
  "version": 1,
  "sources": [
    {{
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "{tmp_path}",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }}
  ]
}}
            """.strip(),
            encoding="utf-8",
        )

        mock_push_summary = MagicMock(
            scanned_records=12,
            pushed_records=9,
            restore_candidates=1,
            created=4,
            updated=3,
            noop=2,
            conflicts=1,
            rejected=0,
            marker_updates=5,
            deleted_remote_records=["ext-removed"],
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            with patch("src.api.routes.sync.SourceSyncWorker") as mock_worker_cls:
                worker = mock_worker_cls.return_value
                worker.parser.list_source_files.return_value = [
                    Path(tmp_path / "notes/a.md"),
                    Path(tmp_path / "notes/b.md"),
                ]
                worker.push = AsyncMock(return_value=mock_push_summary)
                with patch("src.api.routes.sync.record_import_run") as mock_record:
                    response = await client.post(
                        "/api/v1/sync/sources/settings/src-1/push",
                        json={"batch_size": 25, "delete_missing": False},
                    )

        assert response.status_code == 200
        body = response.json()
        assert body["source_id"] == "src-1"
        assert body["label"] == "Project Notes"
        assert body["source_system"] == "notes"
        assert body["workspace_id"] == "workspace-notes"
        assert body["workspace_root"] == str(tmp_path)
        assert body["source_paths"] == ["notes/**/*.md"]
        assert body["state_path"].endswith("/workspace-notes/state/memory-graph-sync.json")
        assert body["conflicts_dir"].endswith("/workspace-notes/conflicts/memory-graph")
        assert body["summary"] == {
            "matched_files": 2,
            "scanned_records": 12,
            "pushed_records": 9,
            "restore_candidates": 1,
            "created": 4,
            "updated": 3,
            "noop": 2,
            "conflicts": 1,
            "rejected": 0,
            "marker_updates": 5,
            "deleted_remote_records": ["ext-removed"],
            "needs_conflict_resolution": True,
            "needs_retry": False,
            "needs_attention": True,
        }
        worker.push.assert_awaited_once_with(batch_size=25, reconcile=True, delete_missing=False)
        mock_record.assert_called_once()
        recorded_payload = mock_record.call_args.args[0]
        assert recorded_payload["run_type"] == "source_push"
        assert recorded_payload["source_id"] == "src-1"
        assert recorded_payload["workspace_id"] == "workspace-notes"
        assert recorded_payload["label"] == "Project Notes"
        assert recorded_payload["status"] == "succeeded"
        assert recorded_payload["summary"]["matched_files"] == 2

    @pytest.mark.asyncio
    async def test_push_sync_source_setting_returns_404_for_missing_source(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text('{"version": 1, "sources": []}', encoding="utf-8")

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            response = await client.post("/api/v1/sync/sources/settings/missing-source/push")

        assert response.status_code == 404
        assert response.json() == {"detail": "Sync source not found: missing-source"}

    @pytest.mark.asyncio
    async def test_pull_sync_source_setting_runs_worker_pull(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            f"""
{{
  "version": 1,
  "sources": [
    {{
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "{tmp_path}",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }}
  ]
}}
            """.strip(),
            encoding="utf-8",
        )

        mock_pull_summary = MagicMock(
            processed_changes=7,
            applied_creates=2,
            applied_updates=3,
            applied_deletes=1,
            written_conflicts=1,
            skipped_echoes=4,
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            with patch("src.api.routes.sync.SourceSyncWorker") as mock_worker_cls:
                worker = mock_worker_cls.return_value
                worker.pull = AsyncMock(return_value=mock_pull_summary)

                response = await client.post(
                    "/api/v1/sync/sources/settings/src-1/pull",
                    json={"change_limit": 80},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["source_id"] == "src-1"
        assert body["label"] == "Project Notes"
        assert body["workspace_root"] == str(tmp_path)
        assert body["inbox_dir"] == str(Path(tmp_path) / "memory" / "inbox")
        assert body["summary"] == {
            "processed_changes": 7,
            "applied_creates": 2,
            "applied_updates": 3,
            "applied_deletes": 1,
            "written_conflicts": 1,
            "skipped_echoes": 4,
            "needs_conflict_resolution": True,
            "needs_attention": True,
        }
        worker.pull.assert_awaited_once_with(limit=80)

    @pytest.mark.asyncio
    async def test_sync_sync_source_setting_runs_worker_sync(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            f"""
{{
  "version": 1,
  "sources": [
    {{
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "{tmp_path}",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }}
  ]
}}
            """.strip(),
            encoding="utf-8",
        )

        mock_push_summary = MagicMock(
            scanned_records=9,
            pushed_records=6,
            restore_candidates=0,
            created=2,
            updated=2,
            noop=2,
            conflicts=0,
            rejected=0,
            marker_updates=1,
            deleted_remote_records=["ext-removed"],
        )
        mock_pull_summary = MagicMock(
            processed_changes=5,
            applied_creates=1,
            applied_updates=2,
            applied_deletes=1,
            written_conflicts=1,
            skipped_echoes=2,
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            with patch("src.api.routes.sync.SourceSyncWorker") as mock_worker_cls:
                worker = mock_worker_cls.return_value
                worker.parser.list_source_files.return_value = [
                    Path(tmp_path / "notes/a.md"),
                    Path(tmp_path / "notes/b.md"),
                    Path(tmp_path / "notes/c.md"),
                ]
                worker.sync = AsyncMock(return_value={"push": mock_push_summary, "pull": mock_pull_summary})

                response = await client.post(
                    "/api/v1/sync/sources/settings/src-1/sync",
                    json={"batch_size": 30, "change_limit": 60, "delete_missing": False},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["source_id"] == "src-1"
        assert body["inbox_dir"] == str(Path(tmp_path) / "memory" / "inbox")
        assert body["push"] == {
            "matched_files": 3,
            "scanned_records": 9,
            "pushed_records": 6,
            "restore_candidates": 0,
            "created": 2,
            "updated": 2,
            "noop": 2,
            "conflicts": 0,
            "rejected": 0,
            "marker_updates": 1,
            "deleted_remote_records": ["ext-removed"],
            "needs_conflict_resolution": False,
            "needs_retry": False,
            "needs_attention": False,
        }
        assert body["pull"] == {
            "processed_changes": 5,
            "applied_creates": 1,
            "applied_updates": 2,
            "applied_deletes": 1,
            "written_conflicts": 1,
            "skipped_echoes": 2,
            "needs_conflict_resolution": True,
            "needs_attention": True,
        }
        worker.sync.assert_awaited_once_with(batch_size=30, change_limit=60, delete_missing=False)

    @pytest.mark.asyncio
    async def test_restore_sync_source_setting_runs_worker_restore(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            f"""
{{
  "version": 1,
  "sources": [
    {{
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "{tmp_path}",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }}
  ]
}}
            """.strip(),
            encoding="utf-8",
        )

        mock_restore_summary = MagicMock(
            scanned_records=7,
            pushed_records=3,
            restore_candidates=3,
            created=1,
            updated=2,
            noop=0,
            conflicts=0,
            rejected=0,
            marker_updates=0,
            deleted_remote_records=[],
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            with patch("src.api.routes.sync.SourceSyncWorker") as mock_worker_cls:
                worker = mock_worker_cls.return_value
                worker.parser.list_source_files.return_value = [Path(tmp_path / "notes/a.md")]
                worker.restore = AsyncMock(return_value=mock_restore_summary)

                response = await client.post(
                    "/api/v1/sync/sources/settings/src-1/restore",
                    json={"batch_size": 40},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["source_id"] == "src-1"
        assert body["summary"] == {
            "matched_files": 1,
            "scanned_records": 7,
            "pushed_records": 3,
            "restore_candidates": 3,
            "created": 1,
            "updated": 2,
            "noop": 0,
            "conflicts": 0,
            "rejected": 0,
            "marker_updates": 0,
            "deleted_remote_records": [],
            "needs_conflict_resolution": False,
            "needs_retry": False,
            "needs_attention": False,
        }
        worker.restore.assert_awaited_once_with(batch_size=40)

    @pytest.mark.asyncio
    async def test_get_sync_source_setting_status_returns_local_and_remote_state(self, client, tmp_path):
        settings_path = tmp_path / "sync-sources.json"
        settings_path.write_text(
            f"""
{{
  "version": 1,
  "sources": [
    {{
      "source_id": "src-1",
      "label": "Project Notes",
      "source_system": "notes",
      "workspace_id": "workspace-notes",
      "workspace_root": "{tmp_path}",
      "source_paths": ["notes/**/*.md"],
      "updated_at": "2026-04-01T10:00:00+00:00"
    }}
  ]
}}
            """.strip(),
            encoding="utf-8",
        )

        local_state = SimpleNamespace(
            records={
                "ext-1": SimpleNamespace(sync_status="synced"),
                "ext-2": SimpleNamespace(sync_status="deleted"),
                "ext-3": SimpleNamespace(sync_status="conflict"),
            },
            last_pulled_seq=42,
            recent_mutation_ids=["m1", "m2", "m3"],
        )
        mock_service = MagicMock()
        mock_service.get_state = AsyncMock(
            return_value={
                "workspace_id": "workspace-notes",
                "active_records": 9,
                "tombstones": 2,
                "conflicts": 1,
                "last_change_seq": 88,
                "last_server_change_at": "2026-04-05T10:00:00+00:00",
            }
        )

        with patch("src.api.routes.sync._get_sync_source_settings_path", return_value=settings_path):
            with patch("src.api.routes.sync.SourceSyncWorker") as mock_worker_cls:
                worker = mock_worker_cls.return_value
                worker.parser.list_source_files.return_value = [
                    Path(tmp_path / "notes/a.md"),
                    Path(tmp_path / "notes/b.md"),
                ]
                worker.get_local_state.return_value = local_state
                with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
                    response = await client.get("/api/v1/sync/sources/settings/src-1/status")

        assert response.status_code == 200
        body = response.json()
        assert body["source_id"] == "src-1"
        assert body["matched_files"] == 2
        assert body["status"] == "degraded"
        assert body["needs_conflict_resolution"] is True
        assert body["needs_attention"] is True
        assert "冲突记录" in body["attention_reason"]
        assert body["local_state"] == {
            "tracked_records": 3,
            "deleted_records": 1,
            "conflict_records": 1,
            "synced_records": 1,
            "last_pulled_seq": 42,
            "recent_mutation_ids": 3,
        }
        assert body["remote_state"] == {
            "active_records": 9,
            "tombstones": 2,
            "conflicts": 1,
            "last_change_seq": 88,
            "last_server_change_at": "2026-04-05T10:00:00Z",
        }

    @pytest.mark.asyncio
    async def test_batch_upsert_source_memories(self, client):
        mock_service = MagicMock()
        mock_service.batch_upsert_source_memories = AsyncMock(
            return_value={
                "results": [
                    {
                        "external_id": "ext-1",
                        "memory_id": "mem-1",
                        "result": "created",
                        "server_version": 1,
                        "sync_status": "synced",
                        "detail": None,
                    }
                ]
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/sync/sources/memories:batch-upsert",
                json={
                    "source_system": "notes",
                    "workspace_id": "workspace-notes",
                    "client_id": "client-1",
                    "records": [
                        {
                            "external_id": "ext-1",
                            "source_path": "notes/daily.md",
                            "record_type": "note",
                            "title": "Daily",
                            "content": "Use SQLite",
                            "tags": ["db"],
                            "content_checksum": "sha256:abc",
                            "client_mutation_id": "mut-1",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {
                    "external_id": "ext-1",
                    "memory_id": "mem-1",
                    "result": "created",
                    "server_version": 1,
                    "sync_status": "synced",
                    "detail": None,
                }
            ],
            "summary": {
                "total_records": 1,
                "created": 1,
                "updated": 0,
                "noop": 0,
                "conflicts": 0,
                "rejected": 0,
                "duplicate_external_ids": [],
                "conflict_external_ids": [],
                "rejected_external_ids": [],
                "retryable_external_ids": [],
                "needs_conflict_resolution": False,
                "needs_retry": False,
                "needs_attention": False,
            },
        }
        mock_service.batch_upsert_source_memories.assert_awaited_once()
        assert mock_service.batch_upsert_source_memories.await_args.args[0] == "notes"

    @pytest.mark.asyncio
    async def test_batch_upsert_source_memories_generic_route(self, client):
        mock_service = MagicMock()
        mock_service.batch_upsert_source_memories = AsyncMock(
            return_value={
                "results": [
                    {
                        "external_id": "ext-1",
                        "memory_id": "mem-1",
                        "result": "created",
                        "server_version": 1,
                        "sync_status": "synced",
                        "detail": None,
                    }
                ]
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/sync/sources/memories:batch-upsert",
                json={
                    "source_system": "external",
                    "workspace_id": "workspace-main",
                    "client_id": "client-1",
                    "records": [
                        {
                            "external_id": "ext-1",
                            "source_path": "MEMORY.md",
                            "record_type": "decision",
                            "title": "Decision",
                            "content": "Use SQLite",
                            "tags": ["db"],
                            "content_checksum": "sha256:abc",
                            "client_mutation_id": "mut-1",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {
                    "external_id": "ext-1",
                    "memory_id": "mem-1",
                    "result": "created",
                    "server_version": 1,
                    "sync_status": "synced",
                    "detail": None,
                }
            ],
            "summary": {
                "total_records": 1,
                "created": 1,
                "updated": 0,
                "noop": 0,
                "conflicts": 0,
                "rejected": 0,
                "duplicate_external_ids": [],
                "conflict_external_ids": [],
                "rejected_external_ids": [],
                "retryable_external_ids": [],
                "needs_conflict_resolution": False,
                "needs_retry": False,
                "needs_attention": False,
            },
        }

    @pytest.mark.asyncio
    async def test_batch_upsert_source_memories_returns_recovery_oriented_summary(self, client):
        mock_service = MagicMock()
        mock_service.batch_upsert_source_memories = AsyncMock(
            return_value={
                "results": [
                    {
                        "external_id": "ext-created",
                        "memory_id": "mem-created",
                        "result": "created",
                        "server_version": 1,
                        "sync_status": "synced",
                        "detail": None,
                    },
                    {
                        "external_id": "ext-duplicate",
                        "memory_id": None,
                        "result": "noop",
                        "server_version": None,
                        "sync_status": "noop",
                        "detail": "duplicate record skipped in request batch",
                    },
                    {
                        "external_id": "ext-conflict",
                        "memory_id": "mem-conflict",
                        "result": "conflict",
                        "server_version": 3,
                        "sync_status": "conflict",
                        "detail": "base_server_version does not match",
                    },
                    {
                        "external_id": "ext-rejected",
                        "memory_id": None,
                        "result": "rejected",
                        "server_version": None,
                        "sync_status": "rejected",
                        "detail": "extract failed",
                    },
                ]
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/sync/sources/memories:batch-upsert",
                json={
                    "source_system": "external",
                    "workspace_id": "workspace-main",
                    "client_id": "client-1",
                    "records": [
                        {
                            "external_id": "ext-created",
                            "source_path": "MEMORY.md",
                            "record_type": "decision",
                            "title": "Decision",
                            "content": "Use SQLite",
                            "tags": ["db"],
                            "content_checksum": "sha256:abc",
                            "client_mutation_id": "mut-1",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json()["summary"] == {
            "total_records": 4,
            "created": 1,
            "updated": 0,
            "noop": 1,
            "conflicts": 1,
            "rejected": 1,
            "duplicate_external_ids": ["ext-duplicate"],
            "conflict_external_ids": ["ext-conflict"],
            "rejected_external_ids": ["ext-rejected"],
            "retryable_external_ids": ["ext-rejected"],
            "needs_conflict_resolution": True,
            "needs_retry": True,
            "needs_attention": True,
        }

    @pytest.mark.asyncio
    async def test_delete_source_memory_success(self, client):
        mock_service = MagicMock()
        mock_service.delete_source_memory = AsyncMock(
            return_value={
                "external_id": "ext-1",
                "memory_id": "mem-1",
                "result": "deleted",
                "server_version": 2,
                "sync_status": "deleted",
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.request(
                "DELETE",
                "/api/v1/sync/sources/external/memories/workspace-main/ext-1",
                json={
                    "base_server_version": 1,
                    "external_revision": "rev-1",
                    "client_mutation_id": "mut-2",
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "external_id": "ext-1",
            "memory_id": "mem-1",
            "result": "deleted",
            "server_version": 2,
            "sync_status": "deleted",
        }

    @pytest.mark.asyncio
    async def test_delete_source_memory_not_found(self, client):
        from src.core.sync.service import SyncNotFoundError

        mock_service = MagicMock()
        mock_service.delete_source_memory = AsyncMock(side_effect=SyncNotFoundError("missing"))

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.request(
                "DELETE",
                "/api/v1/sync/sources/external/memories/workspace-main/ext-1",
                json={
                    "base_server_version": 1,
                    "client_mutation_id": "mut-2",
                },
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "missing"}

    @pytest.mark.asyncio
    async def test_delete_source_memory_conflict(self, client):
        from src.core.sync.service import SyncConflictError

        mock_service = MagicMock()
        mock_service.delete_source_memory = AsyncMock(
            side_effect=SyncConflictError("stale version", current_version=7)
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.request(
                "DELETE",
                "/api/v1/sync/sources/external/memories/workspace-main/ext-1",
                json={
                    "base_server_version": 1,
                    "client_mutation_id": "mut-2",
                },
            )

        assert response.status_code == 409
        assert response.json() == {
            "detail": {
                "message": "stale version",
                "current_server_version": 7,
            }
        }

    @pytest.mark.asyncio
    async def test_list_source_changes(self, client):
        mock_service = MagicMock()
        mock_service.get_changes = AsyncMock(
            return_value={
                "next_cursor": 12,
                "changes": [
                    {
                        "seq": 11,
                        "change_type": "updated",
                        "origin": "server",
                        "client_mutation_id": "mut-3",
                        "external_id": "ext-1",
                        "memory_id": "mem-1",
                        "server_version": 3,
                        "occurred_at": "2026-03-31T09:00:00",
                        "record": {"title": "Updated"},
                    }
                ],
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.get(
                "/api/v1/sync/sources/external/changes?workspace_id=workspace-main&cursor=10&limit=5"
            )

        assert response.status_code == 200
        assert response.json() == {
            "next_cursor": 12,
            "changes": [
                {
                    "seq": 11,
                    "change_type": "updated",
                    "origin": "server",
                    "client_mutation_id": "mut-3",
                    "external_id": "ext-1",
                    "memory_id": "mem-1",
                    "server_version": 3,
                    "occurred_at": "2026-03-31T09:00:00",
                    "record": {"title": "Updated"},
                }
            ],
            "diagnostics": _expected_collection_diagnostics(
                applied_filters={"cursor": 10, "limit": 5},
                server_side_filtered=True,
            ),
        }

    @pytest.mark.asyncio
    async def test_reconcile_source_workspace(self, client):
        mock_service = MagicMock()
        mock_service.reconcile_source = AsyncMock(
            return_value={
                "scan_id": "scan-1",
                "missing_external_ids": ["ext-missing"],
                "deleted_external_ids": ["ext-deleted"],
                "active_count": 4,
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/sync/sources/external/reconcile",
                json={
                    "workspace_id": "workspace-main",
                    "scan_id": "scan-1",
                    "seen_external_ids": ["ext-1", "ext-2"],
                    "delete_missing": True,
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "scan_id": "scan-1",
            "missing_external_ids": ["ext-missing"],
            "deleted_external_ids": ["ext-deleted"],
            "active_count": 4,
        }

    @pytest.mark.asyncio
    async def test_get_sync_source_state(self, client):
        mock_service = MagicMock()
        mock_service.get_state = AsyncMock(
            return_value={
                "workspace_id": "workspace-main",
                "active_records": 8,
                "tombstones": 1,
                "conflicts": 0,
                "last_change_seq": 42,
                "last_server_change_at": "2026-03-31T09:30:00",
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.get("/api/v1/sync/sources/external/state?workspace_id=workspace-main")

        assert response.status_code == 200
        assert response.json() == {
            "workspace_id": "workspace-main",
            "active_records": 8,
            "tombstones": 1,
            "conflicts": 0,
            "last_change_seq": 42,
            "last_server_change_at": "2026-03-31T09:30:00",
        }

    @pytest.mark.asyncio
    async def test_compat_sync_push_maps_results_to_engram_contract(self, client):
        mock_service = MagicMock()
        mock_service.batch_upsert_source_memories = AsyncMock(
            return_value={
                "results": [
                    {
                        "external_id": "ext-1",
                        "memory_id": "mem-1",
                        "result": "created",
                        "server_version": 3,
                        "detail": None,
                    },
                    {
                        "external_id": "ext-2",
                        "memory_id": "mem-2",
                        "result": "updated",
                        "server_version": 4,
                        "detail": "metadata refreshed",
                    },
                ]
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/sync/push",
                json={
                    "sourceSystem": "external",
                    "workspaceId": "workspace-main",
                    "clientId": "engram-platform",
                    "records": [
                        {
                            "externalId": "ext-1",
                            "sourcePath": "memory/a.md",
                            "recordType": "note",
                            "content": "Memory A",
                            "contentChecksum": "sha256:a",
                            "clientMutationId": "mut-1",
                        }
                    ],
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "results": [
                {
                    "externalId": "ext-1",
                    "status": "created",
                    "memoryId": "mem-1",
                    "serverVersion": 3,
                    "detail": None,
                },
                {
                    "externalId": "ext-2",
                    "status": "updated",
                    "memoryId": "mem-2",
                    "serverVersion": 4,
                    "detail": "metadata refreshed",
                },
            ]
        }

    @pytest.mark.asyncio
    async def test_compat_sync_pull_maps_change_feed_to_engram_contract(self, client):
        mock_service = MagicMock()
        mock_service.get_changes = AsyncMock(
            return_value={
                "next_cursor": 12,
                "changes": [
                    {
                        "seq": 11,
                        "change_type": "updated",
                        "memory_id": "mem-1",
                        "external_id": "ext-1",
                        "server_version": 5,
                        "record": {"summary": "Launch summary"},
                    }
                ],
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.get("/api/v1/sync/pull?sourceSystem=external&workspaceId=workspace-main&cursor=10&limit=5")

        assert response.status_code == 200
        assert response.json() == {
            "nextCursor": 12,
            "changes": [
                {
                    "cursor": 11,
                    "changeType": "updated",
                    "memoryId": "mem-1",
                    "externalId": "ext-1",
                    "serverVersion": 5,
                    "record": {"summary": "Launch summary"},
                }
            ],
            "diagnostics": _expected_collection_diagnostics(
                applied_filters={"cursor": 10, "limit": 5},
                server_side_filtered=True,
            ),
        }

    @pytest.mark.asyncio
    async def test_compat_sync_state_maps_workspace_summary_to_engram_contract(self, client):
        mock_service = MagicMock()
        mock_service.get_state = AsyncMock(
            return_value={
                "workspace_id": "workspace-main",
                "active_records": 8,
                "tombstones": 1,
                "conflicts": 0,
                "last_change_seq": 42,
                "last_server_change_at": "2026-03-31T09:30:00",
            }
        )

        with patch("src.api.routes.sync.get_sync_service", return_value=mock_service):
            response = await client.get("/api/v1/sync/state?sourceSystem=external&workspaceId=workspace-main")

        assert response.status_code == 200
        assert response.json() == {
            "workspaceId": "workspace-main",
            "activeRecords": 8,
            "tombstones": 1,
            "conflicts": 0,
            "lastChangeCursor": 42,
            "metadata": {
                "sourceSystem": "external",
                "lastServerChangeAt": "2026-03-31T09:30:00",
            },
        }

    @pytest.mark.asyncio
    async def test_preview_sync_source_accepts_multiple_paths(self, client):
        config = MagicMock()
        config.source_system = "notes"
        config.workspace_id = "workspace-notes"
        config.workspace_root = Path("/tmp/workspace-notes")
        config.source_paths = ["notes/**/*.md", "/tmp/workspace-notes/journal.md"]

        parser = MagicMock()
        parser.list_source_files.return_value = [
            Path("/tmp/workspace-notes/notes/daily.md"),
            Path("/tmp/workspace-notes/journal.md"),
        ]
        parser.scan_workspace.return_value = MagicMock(records=[object(), object(), object()])

        with patch("src.api.routes.sync.build_sync_source_config", return_value=config):
            with patch("src.api.routes.sync.WorkspaceSourceParser", return_value=parser):
                response = await client.post(
                    "/api/v1/sync/sources/preview",
                    json={
                        "source_system": "notes",
                        "workspace_id": "workspace-notes",
                        "workspace_root": "/tmp/workspace-notes",
                        "source_paths": [
                            "notes/**/*.md",
                            "/tmp/workspace-notes/journal.md",
                        ],
                    },
                )

        assert response.status_code == 200
        assert response.json() == {
            "source_system": "notes",
            "workspace_id": "workspace-notes",
            "workspace_root": "/tmp/workspace-notes",
            "source_paths": ["notes/**/*.md", "/tmp/workspace-notes/journal.md"],
            "matched_files": ["notes/daily.md", "journal.md"],
            "record_count": 3,
        }


    @pytest.mark.asyncio
    async def test_get_sync_source_setting_status_reports_attention_flags(self, client):
        config = MagicMock()
        config.source_system = 'notes'
        config.workspace_id = 'workspace-main'
        config.workspace_root = Path('/tmp/workspace-main')
        config.source_paths = ['notes/**/*.md']
        config.resolved_state_path.return_value = Path('/tmp/workspace-main/state.json')
        config.resolved_conflicts_dir.return_value = Path('/tmp/workspace-main/conflicts')
        config.resolved_inbox_dir.return_value = Path('/tmp/workspace-main/inbox')

        worker = MagicMock()
        worker.parser.list_source_files.return_value = [Path('/tmp/workspace-main/notes/a.md')]
        worker.get_local_state.return_value = SimpleNamespace(
            records={
                'ext-1': SimpleNamespace(sync_status='conflict'),
                'ext-2': SimpleNamespace(sync_status='synced'),
            },
            last_pulled_seq=9,
            recent_mutation_ids=['mut-1'],
        )

        with patch('src.api.routes.sync._get_sync_source_setting_or_404', return_value={
            'source_id': 'src-1',
            'label': 'Workspace Notes',
            'source_system': 'notes',
            'workspace_id': 'workspace-main',
            'workspace_root': '/tmp/workspace-main',
            'source_paths': ['notes/**/*.md'],
        }):
            with patch('src.api.routes.sync._build_source_worker', return_value=(config, worker)):
                with patch('src.api.routes.sync.get_sync_service', return_value=MagicMock(get_state=AsyncMock(return_value={
                    'workspace_id': 'workspace-main',
                    'active_records': 8,
                    'tombstones': 1,
                    'conflicts': 0,
                    'last_change_seq': 42,
                    'last_server_change_at': '2026-03-31T09:30:00',
                }))):
                    response = await client.get('/api/v1/sync/sources/settings/src-1/status')

        assert response.status_code == 200
        body = response.json()
        assert body['status'] == 'degraded'
        assert body['needs_conflict_resolution'] is True
        assert body['needs_attention'] is True
        assert '冲突记录' in body['attention_reason']

    @pytest.mark.asyncio
    async def test_push_sync_source_setting_reports_attention_flags(self, client):
        config = MagicMock()
        config.source_system = 'notes'
        config.workspace_id = 'workspace-main'
        config.workspace_root = Path('/tmp/workspace-main')
        config.source_paths = ['notes/**/*.md']
        config.resolved_state_path.return_value = Path('/tmp/workspace-main/state.json')
        config.resolved_conflicts_dir.return_value = Path('/tmp/workspace-main/conflicts')

        worker = MagicMock()
        worker.parser.list_source_files.return_value = [Path('/tmp/workspace-main/notes/a.md')]
        worker.push = AsyncMock(return_value=SimpleNamespace(
            scanned_records=3,
            pushed_records=3,
            restore_candidates=0,
            created=1,
            updated=1,
            noop=0,
            conflicts=1,
            rejected=1,
            marker_updates=0,
            deleted_remote_records=[],
        ))

        with patch('src.api.routes.sync._get_sync_source_setting_or_404', return_value={
            'source_id': 'src-1',
            'label': 'Workspace Notes',
            'source_system': 'notes',
            'workspace_id': 'workspace-main',
            'workspace_root': '/tmp/workspace-main',
            'source_paths': ['notes/**/*.md'],
        }):
            with patch('src.api.routes.sync._build_source_worker', return_value=(config, worker)):
                response = await client.post('/api/v1/sync/sources/settings/src-1/push', json={})

        assert response.status_code == 200
        body = response.json()
        assert body['summary']['needs_conflict_resolution'] is True
        assert body['summary']['needs_retry'] is True
        assert body['summary']['needs_attention'] is True

    @pytest.mark.asyncio
    async def test_pull_sync_source_setting_reports_attention_flags(self, client):
        config = MagicMock()
        config.source_system = 'notes'
        config.workspace_id = 'workspace-main'
        config.workspace_root = Path('/tmp/workspace-main')
        config.source_paths = ['notes/**/*.md']
        config.resolved_state_path.return_value = Path('/tmp/workspace-main/state.json')
        config.resolved_conflicts_dir.return_value = Path('/tmp/workspace-main/conflicts')
        config.resolved_inbox_dir.return_value = Path('/tmp/workspace-main/inbox')

        worker = MagicMock()
        worker.pull = AsyncMock(return_value=SimpleNamespace(
            processed_changes=4,
            applied_creates=1,
            applied_updates=1,
            applied_deletes=0,
            written_conflicts=2,
            skipped_echoes=0,
        ))

        with patch('src.api.routes.sync._get_sync_source_setting_or_404', return_value={
            'source_id': 'src-1',
            'label': 'Workspace Notes',
            'source_system': 'notes',
            'workspace_id': 'workspace-main',
            'workspace_root': '/tmp/workspace-main',
            'source_paths': ['notes/**/*.md'],
        }):
            with patch('src.api.routes.sync._build_source_worker', return_value=(config, worker)):
                response = await client.post('/api/v1/sync/sources/settings/src-1/pull', json={})

        assert response.status_code == 200
        body = response.json()
        assert body['summary']['needs_conflict_resolution'] is True
        assert body['summary']['needs_attention'] is True
