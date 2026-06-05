"""File watcher and import tests for /api/collectors endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCollectorsIoEndpoint:
    """Test file watcher and import collectors endpoints."""

    @pytest.mark.asyncio
    async def test_get_watched_paths(self, client):
        mock_file_watcher = MagicMock()
        mock_file_watcher.get_watched_paths.return_value = ["/tmp/a", "/tmp/b"]
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/file-watcher/paths")

        assert response.status_code == 200
        assert response.json() == {"paths": ["/tmp/a", "/tmp/b"]}

    @pytest.mark.asyncio
    async def test_get_watched_paths_returns_404_when_file_watcher_missing(self, client):
        mock_unified = MagicMock(file_watcher=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/file-watcher/paths")

        assert response.status_code == 404
        assert response.json() == {"detail": "File watcher not initialized"}

    @pytest.mark.asyncio
    async def test_add_watch_path_returns_404_when_file_watcher_missing(self, client):
        mock_unified = MagicMock(file_watcher=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/paths", params={"path": "/tmp/new"})

        assert response.status_code == 404
        assert response.json() == {"detail": "File watcher not initialized"}

    @pytest.mark.asyncio
    async def test_add_watch_path(self, client):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = ["/tmp"]
        mock_file_watcher = MagicMock()
        mock_file_watcher.add_watch_path.return_value = True
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/paths", params={"path": "/tmp/new"})

        assert response.status_code == 200
        assert response.json() == {"status": "added", "path": "/tmp/new"}
        mock_file_watcher.add_watch_path.assert_called_once_with("/tmp/new")

    @pytest.mark.asyncio
    async def test_add_watch_path_rejects_path_outside_allowed_roots(self, client):
        mock_file_watcher = MagicMock()
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/paths", params={"path": "/etc"})

        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}
        mock_file_watcher.add_watch_path.assert_not_called()

    @pytest.mark.asyncio
    async def test_remove_watch_path(self, client):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = ["/tmp"]
        mock_file_watcher = MagicMock()
        mock_file_watcher.remove_watch_path.return_value = True
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.request("DELETE", "/api/collectors/file-watcher/paths", params={"path": "/tmp/old"})

        assert response.status_code == 200
        assert response.json() == {"status": "removed", "path": "/tmp/old"}
        mock_file_watcher.remove_watch_path.assert_called_once_with("/tmp/old")

    @pytest.mark.asyncio
    async def test_remove_watch_path_returns_404_when_file_watcher_missing(self, client):
        mock_unified = MagicMock(file_watcher=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.request("DELETE", "/api/collectors/file-watcher/paths", params={"path": "/tmp/old"})

        assert response.status_code == 404
        assert response.json() == {"detail": "File watcher not initialized"}

    @pytest.mark.asyncio
    async def test_import_message(self, client):
        mock_unified = MagicMock()
        mock_unified.import_message = AsyncMock(return_value={"status": "ok", "imported": 1})

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post(
                "/api/collectors/import",
                params={"source": "manual"},
                json={"content": "hello"},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "imported": 1}

    @pytest.mark.asyncio
    async def test_import_message_surfaces_runtime_error(self, client):
        mock_unified = MagicMock()
        mock_unified.import_message = AsyncMock(side_effect=RuntimeError("import failed"))

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post(
                "/api/collectors/import",
                params={"source": "manual"},
                json={"content": "hello"},
            )

        assert response.status_code == 500
        assert response.json() == {"detail": "import failed"}

    @pytest.mark.asyncio
    async def test_import_file_uses_file_watcher(self, client):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = ["/tmp"]
        mock_file_watcher = MagicMock()
        mock_file_watcher.import_file = AsyncMock(return_value=SimpleNamespace(source_id="conv-file"))
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/import", params={"file_path": "/tmp/chat.md"})

        assert response.status_code == 200
        assert response.json() == {"status": "imported", "conversation_id": "conv-file"}
        mock_file_watcher.import_file.assert_awaited_once_with("/tmp/chat.md")

    @pytest.mark.asyncio
    async def test_import_file_rejects_path_outside_allowed_roots(self, client):
        mock_file_watcher = MagicMock()
        mock_file_watcher.import_file = AsyncMock()
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/import", params={"file_path": "/etc/passwd"})

        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}
        mock_file_watcher.import_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_import_file_returns_400_when_import_returns_none(self, client):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = ["/tmp"]
        mock_file_watcher = MagicMock()
        mock_file_watcher.import_file = AsyncMock(return_value=None)
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/import", params={"file_path": "/tmp/chat.md"})

        assert response.status_code == 400
        assert response.json() == {"detail": "Failed to import file: /tmp/chat.md"}

    @pytest.mark.asyncio
    async def test_import_file_returns_404_when_file_watcher_missing(self, client):
        mock_unified = MagicMock(file_watcher=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/file-watcher/import", params={"file_path": "/tmp/chat.md"})

        assert response.status_code == 404
        assert response.json() == {"detail": "File watcher not initialized"}

    @pytest.mark.asyncio
    async def test_scan_directory(self, client, tmp_path):
        from src.core.config import get_settings

        get_settings().app.allowed_file_roots = [str(tmp_path)]
        convo_file = tmp_path / "conversation.json"
        convo_file.write_text('{"messages":[{"role":"user","content":"hello"}]}', encoding="utf-8")
        other_file = tmp_path / "notes.txt"
        other_file.write_text("plain note", encoding="utf-8")

        mock_detector = MagicMock()
        mock_detector.detect_platform.side_effect = [
            SimpleNamespace(value="chatgpt"),
            SimpleNamespace(value="unknown"),
        ]

        with patch("src.api.routes.collectors_scan.get_detector", return_value=mock_detector):
            response = await client.post(
                "/api/collectors/scan-directory",
                json={
                    "directory": str(tmp_path),
                    "recursive": False,
                    "extensions": [".json", ".txt"],
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["total_files"] == 2
        assert len(body["conversation_files"]) == 1
        assert body["conversation_files"][0]["format"] == "chatgpt"
        assert any(item["reason"] == "not a recognized conversation format" for item in body["skipped_files"])

    @pytest.mark.asyncio
    async def test_scan_directory_rejects_missing_directory(self, client):
        response = await client.post(
            "/api/collectors/scan-directory",
            json={"directory": "/path/does/not/exist", "recursive": False},
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}

    @pytest.mark.asyncio
    async def test_scan_directory_rejects_path_outside_allowed_roots(self, client):
        response = await client.post(
            "/api/collectors/scan-directory",
            json={"directory": "/etc", "recursive": False},
        )

        assert response.status_code == 403
        assert response.json() == {"detail": "Path is outside configured allowed file roots"}

    @pytest.mark.asyncio
    async def test_import_directory(self, client):
        mock_scan_result = SimpleNamespace(
            total_files=3,
            conversation_files=[{"path": "/tmp/a.json"}, {"path": "/tmp/b.json"}],
            skipped_files=[{"path": "/tmp/c.txt", "reason": "skip"}],
        )
        mock_file_watcher = MagicMock()
        mock_file_watcher.import_file = AsyncMock(side_effect=[SimpleNamespace(), None, None])
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.scan_directory", new=AsyncMock(return_value=mock_scan_result)):
            with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
                response = await client.post(
                    "/api/collectors/import-directory",
                    json={"directory": "/tmp", "recursive": True},
                )

        assert response.status_code == 200
        assert response.json() == {
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

    @pytest.mark.asyncio
    async def test_import_directory_returns_no_files_when_scan_is_empty(self, client):
        mock_scan_result = SimpleNamespace(
            total_files=0,
            conversation_files=[],
            skipped_files=[],
        )

        with patch("src.api.routes.collectors.scan_directory", new=AsyncMock(return_value=mock_scan_result)):
            response = await client.post(
                "/api/collectors/import-directory",
                json={"directory": "/tmp", "recursive": True},
            )

        assert response.status_code == 200
        assert response.json() == {
            "status": "no_files",
            "message": "No conversation files found in the directory",
            "imported": 0,
            "skipped": 0,
            "attempted": 0,
            "duplicates_skipped": 0,
            "retryable_failed_files": [],
            "retryable_count": 0,
        }

    @pytest.mark.asyncio
    async def test_import_directory_deduplicates_paths_and_recovers_on_retry(self, client):
        mock_scan_result = SimpleNamespace(
            total_files=4,
            conversation_files=[
                {"path": "/tmp/a.json"},
                {"path": "/tmp/a.json"},
            ],
            skipped_files=[{"path": "/tmp/c.txt", "reason": "skip"}],
        )
        mock_file_watcher = MagicMock()
        mock_file_watcher.import_file = AsyncMock(side_effect=[None, SimpleNamespace()])
        mock_unified = MagicMock(file_watcher=mock_file_watcher)

        with patch("src.api.routes.collectors.scan_directory", new=AsyncMock(return_value=mock_scan_result)):
            with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
                response = await client.post(
                    "/api/collectors/import-directory",
                    json={"directory": "/tmp", "recursive": True, "import_retries": 1},
                )

        assert response.status_code == 200
        assert response.json() == {
            "status": "completed",
            "message": "Imported 1 conversations",
            "imported": 1,
            "attempted": 1,
            "failed": 0,
            "failed_files": [],
            "skipped": 2,
            "duplicates_skipped": 1,
            "retryable_failed_files": [],
            "retryable_count": 0,
            "total_scanned": 4,
        }
