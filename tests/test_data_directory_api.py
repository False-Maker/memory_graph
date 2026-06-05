"""Focused tests for v1 /api/v1/data directory scan/import routes."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.api.security import enforce_api_auth
from src.api.routes.data.directory_routes import router


@pytest.fixture
async def directory_client():
    app = FastAPI()
    app.middleware("http")(enforce_api_auth)
    app.include_router(router)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer test-api-token"},
    ) as client:
        yield client


class TestDataDirectoryRoutes:
    @pytest.mark.asyncio
    async def test_scan_directory_returns_scan_result(self, directory_client):
        mock_scan_result = SimpleNamespace(
            total_files=2,
            conversation_files=[{"path": "/tmp/conv.json", "format": "chatgpt"}],
            skipped_files=[{"path": "/tmp/notes.txt", "reason": "not a recognized conversation format"}],
            errors=[],
        )

        with patch(
            "src.api.routes.data.directory_routes.perform_directory_scan",
            new=AsyncMock(return_value=mock_scan_result),
        ) as mock_scan:
            response = await directory_client.post(
                "/api/v1/data/scan-directory",
                json={"directory_path": "/tmp", "recursive": True, "extensions": [".json", ".txt"]},
            )

        assert response.status_code == 200
        assert response.json() == {
            "total_files": 2,
            "conversation_files": [{"path": "/tmp/conv.json", "format": "chatgpt"}],
            "skipped_files": [{"path": "/tmp/notes.txt", "reason": "not a recognized conversation format"}],
            "errors": [],
        }
        assert mock_scan.await_count == 1
        request_payload = mock_scan.await_args.args[0]
        assert request_payload.directory == "/tmp"
        assert request_payload.extensions == [".json", ".txt"]

    @pytest.mark.asyncio
    async def test_scan_directory_rejects_path_outside_allowed_roots(self, directory_client):
        response = await directory_client.post(
            "/api/v1/data/scan-directory",
            json={"directory_path": "/etc", "recursive": False},
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}

    @pytest.mark.asyncio
    async def test_import_directory_returns_reliability_fields(self, directory_client):
        mock_scan_result = SimpleNamespace(
            total_files=3,
            conversation_files=[{"path": "/tmp/a.json"}, {"path": "/tmp/b.json"}],
            skipped_files=[{"path": "/tmp/c.txt", "reason": "skip"}],
            errors=[],
        )
        import_result = {
            "status": "completed",
            "message": "Imported 1 conversations",
            "imported": 1,
            "attempted": 2,
            "failed": 1,
            "failed_files": [
                {
                    "path": "/tmp/b.json",
                    "reason": "import returned None",
                    "attempts": 2,
                    "retry_exhausted": True,
                }
            ],
            "skipped": 1,
            "duplicates_skipped": 0,
            "retryable_failed_files": [
                {
                    "path": "/tmp/b.json",
                    "reason": "import returned None",
                    "attempts": 2,
                    "retry_exhausted": True,
                }
            ],
            "retryable_count": 1,
            "total_scanned": 3,
        }

        with patch(
            "src.api.routes.data.directory_routes.perform_directory_scan",
            new=AsyncMock(return_value=mock_scan_result),
        ):
            with patch(
                "src.api.routes.data.directory_routes.import_scan_results",
                new=AsyncMock(return_value=import_result),
            ) as mock_import:
                with patch("src.api.routes.data.directory_routes.record_import_run") as mock_record:
                    response = await directory_client.post(
                        "/api/v1/data/import-directory",
                        json={"directory_path": "/tmp", "import_retries": 2},
                    )

        assert response.status_code == 200
        body = response.json()
        assert body["imported"] == 1
        assert body["attempted"] == 2
        assert body["duplicates_skipped"] == 0
        assert body["retryable_count"] == 1
        assert isinstance(body["retryable_failed_files"], list)
        assert mock_import.await_count == 1
        assert isinstance(mock_import.await_args.kwargs["import_file"], object)
        assert mock_import.await_args.kwargs["retries"] == 2
        mock_record.assert_called_once()
        recorded_payload = mock_record.call_args.args[0]
        assert recorded_payload["run_type"] == "directory_import"
        assert recorded_payload["directory_path"] == "/tmp"
        assert recorded_payload["source_path"] == "/tmp"
        assert recorded_payload["status"] == "completed"
        assert recorded_payload["message"] == "Imported 1 conversations"
        assert recorded_payload["imported"] == 1
        assert recorded_payload["attempted"] == 2
        assert recorded_payload["failed"] == 1
        assert recorded_payload["skipped"] == 1
        assert recorded_payload["retryable"] is True
        assert recorded_payload["retry_request"] == {
            "directory_path": "/tmp",
            "recursive": True,
            "extensions": [".txt", ".md", ".json", ".jsonl"],
            "include_patterns": None,
            "skip_patterns": None,
            "import_retries": 2,
        }

    @pytest.mark.asyncio
    async def test_import_directory_maps_file_not_found_to_400(self, directory_client):
        with patch(
            "src.api.routes.data.directory_routes.perform_directory_scan",
            new=AsyncMock(side_effect=FileNotFoundError("/not-found")),
        ):
            with patch("src.api.routes.data.directory_routes.record_import_run") as mock_record:
                response = await directory_client.post(
                    "/api/v1/data/import-directory",
                    json={"directory_path": "/not-found"},
                )

        assert response.status_code == 400
        assert response.json() == {"detail": "Directory not found: /not-found"}
        mock_record.assert_called_once()
        recorded_payload = mock_record.call_args.args[0]
        assert recorded_payload["run_type"] == "directory_import"
        assert recorded_payload["directory_path"] == "/not-found"
        assert recorded_payload["status"] == "failed"
        assert recorded_payload["failed"] == 1
        assert recorded_payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_import_directory_maps_unexpected_error_to_500_and_records_run(self, directory_client):
        with patch(
            "src.api.routes.data.directory_routes.perform_directory_scan",
            new=AsyncMock(return_value=SimpleNamespace(total_files=0, conversation_files=[], skipped_files=[], errors=[])),
        ):
            with patch(
                "src.api.routes.data.directory_routes.import_scan_results",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ):
                with patch("src.api.routes.data.directory_routes.record_import_run") as mock_record:
                    response = await directory_client.post(
                        "/api/v1/data/import-directory",
                        json={"directory_path": "/tmp"},
                    )

        assert response.status_code == 500
        assert response.json() == {"detail": "boom"}
        mock_record.assert_called_once()
        recorded_payload = mock_record.call_args.args[0]
        assert recorded_payload["run_type"] == "directory_import"
        assert recorded_payload["directory_path"] == "/tmp"
        assert recorded_payload["status"] == "failed"
        assert recorded_payload["failed"] == 1
        assert recorded_payload["error"] == "boom"
        assert recorded_payload["retryable"] is True

    @pytest.mark.asyncio
    async def test_import_scanned_file_uses_detector_and_memory_service(self, directory_client, tmp_path):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = [str(tmp_path)]
        file_path = tmp_path / "conv.json"
        file_path.write_text("{}", encoding="utf-8")
        mock_scan_result = SimpleNamespace(
            total_files=1,
            conversation_files=[{"path": str(file_path)}],
            skipped_files=[],
            errors=[],
        )
        fake_conversation = SimpleNamespace(
            platform=SimpleNamespace(value="claude"),
            title="Imported Chat",
            messages=[
                {"role": "user", "content": "Alice Johnson is coordinating the rollout with OpenAI."},
                {"role": "assistant", "content": "OpenAI confirmed Alice Johnson owns the migration."},
            ],
            metadata={"conversation_id": "conv-1"},
            created_at="2026-04-02T10:00:00",
            to_memory_content=lambda: "# Imported Chat\n\nHello",
        )
        mock_detector = MagicMock()
        mock_detector.parse_file.return_value = ([fake_conversation], "claude")
        mock_service = MagicMock()
        mock_service.ingest_memory = AsyncMock(return_value=SimpleNamespace(memory_id="mem-1"))

        with patch(
            "src.api.routes.data.directory_routes.perform_directory_scan",
            new=AsyncMock(return_value=mock_scan_result),
        ):
            with patch("src.api.routes.data.directory_routes.get_detector", return_value=mock_detector):
                with patch("src.api.routes.data.directory_routes.get_memory_service", return_value=mock_service):
                    response = await directory_client.post(
                        "/api/v1/data/import-directory",
                        json={"directory_path": str(tmp_path)},
                    )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["imported"] == 1
        mock_service.ingest_memory.assert_awaited_once()
        metadata = mock_service.ingest_memory.await_args.kwargs["metadata"]
        regex_entity_texts = {item["text"] for item in metadata["regex_entity_hints"]}
        assert "OpenAI" in regex_entity_texts
        assert "Alice Johnson" in regex_entity_texts

    @pytest.mark.asyncio
    async def test_scan_directory_detects_phase1_sample_exports(
        self,
        directory_client,
        tmp_path,
        phase1_import_fixture_dir,
    ):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = [str(tmp_path)]
        expected_formats = {
            "chatgpt_export.json": "chatgpt",
            "chatgpt_export_collection.json": "chatgpt",
            "claude_export.json": "claude",
            "claude_chat_variant.json": "claude",
            "claude_code_session.jsonl": "claude_code",
            "claude_code_session_variant.jsonl": "claude_code",
            "slack_export.json": "slack",
            "slack_thread_variant.json": "slack",
            "codex_export.json": "codex",
            "codex_export_variant.json": "codex",
        }
        for filename in expected_formats:
            source_path = Path(phase1_import_fixture_dir) / filename
            target_path = tmp_path / filename
            target_path.write_bytes(source_path.read_bytes())

        response = await directory_client.post(
            "/api/v1/data/scan-directory",
            json={"directory_path": str(tmp_path), "extensions": [".json", ".jsonl"]},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["total_files"] == len(expected_formats)
        conversation_files = {Path(item["path"]).name: item["format"] for item in body["conversation_files"]}
        assert conversation_files == expected_formats
