"""Control and status tests for /api/collectors endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCollectorsControlEndpoint:
    """Test control/status collectors endpoints."""

    @pytest.mark.asyncio
    async def test_get_collectors_status(self, client):
        mock_unified = MagicMock()
        mock_unified.get_status.return_value = {"cursor": {"running": True}}

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/status")

        assert response.status_code == 200
        assert response.json() == {"cursor": {"running": True}}

    @pytest.mark.asyncio
    async def test_get_collectors_status_filters_experimental_collectors_from_public_payload(self, client):
        mock_unified = MagicMock()
        mock_unified.get_status.return_value = {
            "running": True,
            "collectors": [
                {"type": "windsurf", "running": True, "support_tier": "official"},
                {"type": "cline", "running": True, "support_tier": "experimental"},
            ],
        }

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/status")

        assert response.status_code == 200
        assert response.json() == {
            "running": True,
            "collectors": [
                {"type": "windsurf", "running": True, "support_tier": "official"},
            ],
        }

    @pytest.mark.asyncio
    async def test_get_collector_status_rejects_invalid_type(self, client):
        response = await client.get("/api/collectors/collectors/not-real")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid collector type: not-real"}

    @pytest.mark.asyncio
    async def test_get_collector_status_rejects_experimental_type(self, client):
        response = await client.get("/api/collectors/collectors/cline")

        assert response.status_code == 404
        assert response.json() == {"detail": "Collector not available in current product surface: cline"}

    @pytest.mark.asyncio
    async def test_get_collector_status(self, client):
        mock_unified = MagicMock()
        mock_unified.get_collector_status.return_value = {"type": "cursor", "running": True}

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/collectors/cursor")

        assert response.status_code == 200
        assert response.json() == {"type": "cursor", "running": True}

    @pytest.mark.asyncio
    async def test_get_collector_status_returns_404_when_missing(self, client):
        mock_unified = MagicMock()
        mock_unified.get_collector_status.return_value = None

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/collectors/cursor")

        assert response.status_code == 404
        assert response.json() == {"detail": "Collector not found: cursor"}

    @pytest.mark.asyncio
    async def test_start_collectors(self, client):
        mock_unified = MagicMock()
        mock_unified.start = AsyncMock(return_value={"cursor": True, "file_watcher": True})
        mock_settings = SimpleNamespace(collectors=SimpleNamespace(dict=lambda: {}))

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            with patch("src.api.routes.collectors.get_settings", return_value=mock_settings):
                response = await client.post(
                    "/api/collectors/start",
                    json={"enabled_types": ["cursor", "file_watcher"]},
                )

        assert response.status_code == 200
        assert response.json() == {
            "status": "started",
            "results": {"cursor": True, "file_watcher": True},
        }
        mock_unified.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_start_collectors_rejects_invalid_type(self, client):
        mock_unified = MagicMock()
        mock_settings = SimpleNamespace(collectors=SimpleNamespace(dict=lambda: {}))

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            with patch("src.api.routes.collectors.get_settings", return_value=mock_settings):
                response = await client.post(
                    "/api/collectors/start",
                    json={"enabled_types": ["not-real"]},
                )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid collector type: not-real"}

    @pytest.mark.asyncio
    async def test_start_collectors_rejects_experimental_type(self, client):
        mock_unified = MagicMock()
        mock_settings = SimpleNamespace(collectors=SimpleNamespace(dict=lambda: {}))

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            with patch("src.api.routes.collectors.get_settings", return_value=mock_settings):
                response = await client.post(
                    "/api/collectors/start",
                    json={"enabled_types": ["cline"]},
                )

        assert response.status_code == 404
        assert response.json() == {"detail": "Collector not available in current product surface: cline"}

    @pytest.mark.asyncio
    async def test_stop_collectors(self, client):
        mock_unified = MagicMock()
        mock_unified.stop = AsyncMock(return_value={"cursor": True})

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/stop", json={})

        assert response.status_code == 200
        assert response.json() == {"status": "stopped", "results": {"cursor": True}}
        mock_unified.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_collectors_rejects_invalid_type(self, client):
        mock_unified = MagicMock()

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/stop", json={"collector_types": ["not-real"]})

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid collector type: not-real"}

    @pytest.mark.asyncio
    async def test_stop_collectors_rejects_experimental_type(self, client):
        mock_unified = MagicMock()

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/stop", json={"collector_types": ["cline"]})

        assert response.status_code == 404
        assert response.json() == {"detail": "Collector not available in current product surface: cline"}

    @pytest.mark.asyncio
    async def test_stop_collectors_can_stop_specific_collectors(self, client):
        mock_cursor = MagicMock()
        mock_cursor.stop = AsyncMock(return_value=True)
        mock_ws = MagicMock()
        mock_ws.stop = AsyncMock(return_value=True)
        mock_unified = MagicMock()
        mock_unified.get_collector.side_effect = lambda ctype: {
            "cursor": mock_cursor,
            "websocket": mock_ws,
        }.get(ctype.value)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post(
                "/api/collectors/stop",
                json={"collector_types": ["cursor"]},
            )

        assert response.status_code == 200
        assert response.json() == {"status": "stopped", "results": {"cursor": True}}
        mock_cursor.stop.assert_awaited_once()
        mock_ws.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_single_collector(self, client):
        mock_collector = MagicMock()
        mock_collector.start = AsyncMock(return_value=True)
        mock_unified = MagicMock()
        mock_unified.get_collector.return_value = mock_collector

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/collectors/cursor/start")

        assert response.status_code == 200
        assert response.json() == {"status": "started", "collector_type": "cursor"}

    @pytest.mark.asyncio
    async def test_stop_single_collector(self, client):
        mock_collector = MagicMock()
        mock_collector.stop = AsyncMock(return_value=True)
        mock_unified = MagicMock()
        mock_unified.get_collector.return_value = mock_collector

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/collectors/cursor/stop")

        assert response.status_code == 200
        assert response.json() == {"status": "stopped", "collector_type": "cursor"}

    @pytest.mark.asyncio
    async def test_start_single_collector_returns_404_when_missing(self, client):
        mock_unified = MagicMock()
        mock_unified.get_collector.return_value = None

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/collectors/cursor/start")

        assert response.status_code == 404
        assert response.json() == {"detail": "Collector not registered: cursor"}

    @pytest.mark.asyncio
    async def test_start_single_collector_rejects_invalid_type(self, client):
        response = await client.post("/api/collectors/collectors/not-real/start")

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid collector type: not-real"}

    @pytest.mark.asyncio
    async def test_start_single_collector_rejects_experimental_type(self, client):
        response = await client.post("/api/collectors/collectors/cline/start")

        assert response.status_code == 404
        assert response.json() == {"detail": "Collector not available in current product surface: cline"}
