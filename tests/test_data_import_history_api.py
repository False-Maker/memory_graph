"""Targeted tests for data import run history API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.data.import_run_store import list_recent_import_runs, record_import_run


@pytest.fixture
def import_runs_store_path(monkeypatch, tmp_path):
    path = tmp_path / "import-runs.json"
    monkeypatch.setenv("IMPORT_RUNS_STORE_PATH", str(path))
    return path


class TestDataImportHistoryApi:
    @pytest.mark.asyncio
    async def test_import_runs_endpoint_returns_empty_list(self, client, import_runs_store_path):
        response = await client.get("/api/v1/data/import-runs?limit=10")

        assert response.status_code == 200
        assert response.json() == {"success": True, "runs": []}

    @pytest.mark.asyncio
    async def test_file_import_records_success_run(self, client, import_runs_store_path):
        with patch(
            "src.api.routes.data.batch_create_memories",
            new=AsyncMock(return_value={"success": True, "memory_ids": ["mem-1"], "count": 1}),
        ):
            response = await client.post(
                "/api/v1/data/import",
                files={
                    "file": (
                        "memories.json",
                        json.dumps({"content": "Imported memory", "metadata": {"source": "manual"}}),
                        "application/json",
                    )
                },
            )

        assert response.status_code == 200
        runs_response = await client.get("/api/v1/data/import-runs?limit=10")
        assert runs_response.status_code == 200
        runs = runs_response.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "succeeded"
        assert runs[0]["run_type"] == "file_import"
        assert runs[0]["source"] == "data/import"
        assert runs[0]["filename"] == "memories.json"
        assert runs[0]["imported"] == 1

    @pytest.mark.asyncio
    async def test_conversation_json_import_failure_records_failed_run(self, client, import_runs_store_path):
        mock_detector = MagicMock()
        mock_detector.detect_and_parse.return_value = ([], "unknown")

        with patch("src.api.routes.data.get_detector", return_value=mock_detector):
            response = await client.post(
                "/api/v1/data/import/conversations/json",
                json={"content": "[]", "output_format": "markdown"},
            )

        assert response.status_code == 400

        runs_response = await client.get("/api/v1/data/import-runs?limit=10")
        runs = runs_response.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["status"] == "failed"
        assert runs[0]["run_type"] == "conversation_import"
        assert runs[0]["source"] == "data/import/conversations/json"
        assert runs[0]["failed"] == 1

    @pytest.mark.asyncio
    async def test_import_runs_limit_applies(self, client, import_runs_store_path):
        with patch(
            "src.api.routes.data.batch_create_memories",
            new=AsyncMock(return_value={"success": True, "memory_ids": ["mem-1"], "count": 1}),
        ):
            await client.post(
                "/api/v1/data/import",
                files={"file": ("one.json", json.dumps({"content": "one"}), "application/json")},
            )
            await client.post(
                "/api/v1/data/import",
                files={"file": ("two.json", json.dumps({"content": "two"}), "application/json")},
            )

        runs_response = await client.get("/api/v1/data/import-runs?limit=1")
        runs = runs_response.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["filename"] == "two.json"

    @pytest.mark.asyncio
    async def test_record_import_run_preserves_richer_payload_fields(self, client, import_runs_store_path):
        record_import_run(
            {
                "status": "completed",
                "run_type": "directory_import",
                "source": "data/import-directory",
                "filename": "/tmp/workspace",
                "imported": 5,
                "attempted": 7,
                "failed": 1,
                "skipped": 1,
                "message": "batch directory import finished",
                "started_at": "2026-04-02T10:00:00+00:00",
                "finished_at": "2026-04-02T10:01:00+00:00",
                "detail": "extensions=.md,.json",
                "directory_path": "/tmp/workspace",
                "source_path": "/tmp/workspace",
                "retryable": True,
                "retry_request": {
                    "directory_path": "/tmp/workspace",
                    "recursive": True,
                    "extensions": [".md", ".json"],
                    "include_patterns": None,
                    "skip_patterns": None,
                    "import_retries": 2,
                },
            }
        )

        runs_response = await client.get("/api/v1/data/import-runs?limit=10")
        assert runs_response.status_code == 200
        runs = runs_response.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["run_type"] == "directory_import"
        assert runs[0]["directory_path"] == "/tmp/workspace"
        assert runs[0]["source_path"] == "/tmp/workspace"
        assert runs[0]["retryable"] is True
        assert "retry_request" not in runs[0]
        assert runs[0]["attempted"] == 7
        assert runs[0]["skipped"] == 1
        assert runs[0]["message"] == "batch directory import finished"
        assert runs[0]["started_at"] == "2026-04-02T10:00:00+00:00"
        assert runs[0]["finished_at"] == "2026-04-02T10:01:00+00:00"

    @pytest.mark.asyncio
    async def test_record_import_run_preserves_source_operation_summary_fields(self, client, import_runs_store_path):
        record_import_run(
            {
                "status": "succeeded",
                "run_type": "source_sync",
                "source": "sync/sources/settings/src-1/sync",
                "source_id": "src-1",
                "workspace_id": "workspace-notes",
                "label": "Project Notes",
                "message": "source sync completed: Project Notes",
                "summary": {
                    "push": {"created": 1, "updated": 2, "conflicts": 0},
                    "pull": {"processed_changes": 4, "written_conflicts": 1},
                },
            }
        )

        runs_response = await client.get("/api/v1/data/import-runs?limit=10")
        assert runs_response.status_code == 200
        runs = runs_response.json()["runs"]
        assert len(runs) == 1
        assert runs[0]["run_type"] == "source_sync"
        assert runs[0]["source_id"] == "src-1"
        assert runs[0]["workspace_id"] == "workspace-notes"
        assert runs[0]["label"] == "Project Notes"
        assert runs[0]["summary"] == {
            "push": {"created": 1, "updated": 2, "conflicts": 0},
            "pull": {"processed_changes": 4, "written_conflicts": 1},
        }

    @pytest.mark.asyncio
    async def test_retry_import_run_replays_directory_request(self, client, import_runs_store_path):
        record_import_run(
            {
                "id": "run-1",
                "status": "failed",
                "run_type": "directory_import",
                "source": "data/import-directory",
                "directory_path": "/tmp/workspace",
                "filename": "/tmp/workspace",
                "retryable": True,
                "retry_request": {
                    "directory_path": "/tmp/workspace",
                    "recursive": True,
                    "extensions": [".md"],
                    "include_patterns": None,
                    "skip_patterns": None,
                    "import_retries": 2,
                },
            }
        )

        with patch(
            "src.api.routes.data.history_routes.run_directory_import",
            new=AsyncMock(
                return_value={
                    "status": "completed",
                    "message": "Imported 3 conversations",
                    "imported": 3,
                    "attempted": 3,
                    "failed": 0,
                    "skipped": 0,
                }
            ),
        ) as mock_retry:
            response = await client.post("/api/v1/data/import-runs/run-1/retry")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["source_run_id"] == "run-1"
        assert body["result"]["status"] == "completed"
        mock_retry.assert_awaited_once()
        request_payload = mock_retry.await_args.args[0]
        assert request_payload.directory_path == "/tmp/workspace"
        assert request_payload.extensions == [".md"]
        assert mock_retry.await_args.kwargs["retry_of"] == "run-1"

    @pytest.mark.asyncio
    async def test_retry_import_run_rejects_unsupported_run_type(self, client, import_runs_store_path):
        record_import_run(
            {
                "id": "run-file",
                "status": "failed",
                "run_type": "file_import",
                "source": "data/import",
                "filename": "payload.json",
            }
        )

        response = await client.post("/api/v1/data/import-runs/run-file/retry")

        assert response.status_code == 400
        assert response.json() == {"detail": "Retry is not supported for run type: file_import"}

    @pytest.mark.asyncio
    async def test_retry_import_run_returns_404_for_missing_run(self, client, import_runs_store_path):
        response = await client.post("/api/v1/data/import-runs/missing-run/retry")

        assert response.status_code == 404
        assert response.json() == {"detail": "Import run not found: missing-run"}

    @pytest.mark.asyncio
    async def test_list_recent_import_runs_normalizes_legacy_records(self, client, import_runs_store_path):
        import_runs_store_path.write_text(
            json.dumps(
                [
                    {
                        "id": "legacy-1",
                        "created_at": "2026-04-01T08:00:00+00:00",
                        "status": "succeeded",
                        "run_type": "file_import",
                        "source": "data/import",
                        "filename": "legacy.json",
                        "imported": "3",
                        "failed": "0",
                    },
                    {
                        "run_id": "legacy-run-2",
                        "type": "conversation_import",
                        "status": "failed",
                        "source": "data/import/conversations/json",
                        "failed": 1,
                        "error": "legacy parse error",
                    },
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        runs = list_recent_import_runs(limit=10)
        assert len(runs) == 2

        first = runs[0]
        assert first["id"] == "legacy-1"
        assert first["attempted"] == 0
        assert first["skipped"] == 0
        assert first["message"] is None
        assert first["started_at"] == "2026-04-01T08:00:00+00:00"
        assert first["finished_at"] is None

        second = runs[1]
        assert second["id"] == "legacy-run-2"
        assert second["run_type"] == "conversation_import"
        assert second["created_at"]
        assert second["attempted"] == 0
        assert second["skipped"] == 0
