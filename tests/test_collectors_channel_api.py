"""Cursor, browser, and websocket tests for /api/collectors endpoints."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class _FakeWebSocket:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.sent_messages = []
        self.closed = False

    async def receive_text(self):
        return self.client_id

    async def send_json(self, payload):
        self.sent_messages.append(payload)

    async def close(self):
        self.closed = True


class TestCollectorsChannelEndpoint:
    """Test cursor, browser, and websocket collectors endpoints."""

    @pytest.mark.asyncio
    async def test_get_websocket_stats(self, client):
        mock_ws = MagicMock()
        mock_ws.get_stats.return_value = {"connections": 2, "messages": 10}
        mock_unified = MagicMock(websocket=mock_ws)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/websocket/stats")

        assert response.status_code == 200
        assert response.json() == {"connections": 2, "messages": 10}

    @pytest.mark.asyncio
    async def test_get_websocket_stats_returns_404_when_missing(self, client):
        mock_unified = MagicMock(websocket=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/websocket/stats")

        assert response.status_code == 404
        assert response.json() == {"detail": "WebSocket collector not initialized"}

    @pytest.mark.asyncio
    async def test_get_cursor_conversations(self, client):
        mock_cursor = MagicMock()
        mock_cursor.get_conversations_list = AsyncMock(return_value=[{"id": "conv-1"}, {"id": "conv-2"}])
        mock_unified = MagicMock(cursor=mock_cursor)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/cursor/conversations")

        assert response.status_code == 200
        assert response.json() == {
            "conversations": [{"id": "conv-1"}, {"id": "conv-2"}],
            "total": 2,
        }

    @pytest.mark.asyncio
    async def test_get_cursor_conversations_returns_404_when_missing(self, client):
        mock_unified = MagicMock(cursor=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.get("/api/collectors/cursor/conversations")

        assert response.status_code == 404
        assert response.json() == {"detail": "Cursor collector not initialized"}

    @pytest.mark.asyncio
    async def test_import_cursor_conversation(self, client):
        mock_cursor = MagicMock()
        mock_cursor.import_conversation = AsyncMock(return_value=SimpleNamespace(source_id="conv-1"))
        mock_unified = MagicMock(cursor=mock_cursor)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/cursor/import/conv-1")

        assert response.status_code == 200
        assert response.json() == {"status": "imported", "conversation_id": "conv-1"}

    @pytest.mark.asyncio
    async def test_import_cursor_conversation_returns_404_when_missing(self, client):
        mock_unified = MagicMock(cursor=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/cursor/import/conv-1")

        assert response.status_code == 404
        assert response.json() == {"detail": "Cursor collector not initialized"}

    @pytest.mark.asyncio
    async def test_import_cursor_conversation_returns_404_when_not_found(self, client):
        mock_cursor = MagicMock()
        mock_cursor.import_conversation = AsyncMock(return_value=None)
        mock_unified = MagicMock(cursor=mock_cursor)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post("/api/collectors/cursor/import/conv-404")

        assert response.status_code == 404
        assert response.json() == {"detail": "Conversation not found: conv-404"}

    @pytest.mark.asyncio
    async def test_capture_browser_message(self, client):
        mock_browser = MagicMock()
        mock_browser.capture_message = AsyncMock(
            return_value={"status": "success", "conversation_id": "browser_1"}
        )
        mock_unified = MagicMock(browser=mock_browser)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post(
                "/api/collectors/browser/capture",
                json={
                    "source": "chatgpt",
                    "platform": "web",
                    "messages": [{"role": "user", "content": "hello"}],
                    "metadata": {"tab": "A"},
                },
            )

        assert response.status_code == 200
        assert response.json() == {"status": "success", "conversation_id": "browser_1"}

    @pytest.mark.asyncio
    async def test_capture_browser_message_returns_404_when_missing(self, client):
        mock_unified = MagicMock(browser=None)

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            response = await client.post(
                "/api/collectors/browser/capture",
                json={
                    "source": "chatgpt",
                    "platform": "web",
                    "messages": [{"role": "user", "content": "hello"}],
                },
            )

        assert response.status_code == 404
        assert response.json() == {"detail": "Browser collector not initialized"}

    @pytest.mark.asyncio
    async def test_websocket_collectors_returns_error_when_websocket_collector_missing(self):
        from src.api.routes.collectors import websocket_collectors

        mock_unified = MagicMock(websocket=None)
        websocket = _FakeWebSocket("client-1")

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            await websocket_collectors(websocket)

        assert websocket.sent_messages == [{
            "type": "error",
            "message": "WebSocket collector not initialized",
        }]
        assert websocket.closed is True

    @pytest.mark.asyncio
    async def test_websocket_collectors_surfaces_runtime_error(self):
        from src.api.routes.collectors import websocket_collectors

        mock_ws_collector = MagicMock()
        mock_ws_collector.handle_websocket = AsyncMock(side_effect=RuntimeError("boom"))
        mock_unified = MagicMock(websocket=mock_ws_collector)
        websocket = _FakeWebSocket("client-2")

        with patch("src.api.routes.collectors.get_unified_collector", return_value=mock_unified):
            await websocket_collectors(websocket)

        assert websocket.sent_messages == [{
            "type": "error",
            "message": "boom",
        }]
