"""WebSocket-related collectors routes."""

import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from src.api.routes.collectors.deps import require_runtime_component

router = APIRouter()
logger = logging.getLogger(__name__)


@router.websocket("/ws/collectors")
async def websocket_collectors(websocket: WebSocket):
    """WebSocket 实时采集接口"""
    client_id = None

    try:
        client_id = await websocket.receive_text()

        try:
            ws_collector = require_runtime_component(
                "websocket",
                "WebSocket collector not initialized",
            )
        except HTTPException as exc:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": exc.detail,
                }
            )
            await websocket.close()
            return

        await ws_collector.handle_websocket(websocket, client_id)

    except WebSocketDisconnect:
        logger.info("Client %s disconnected", client_id)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        try:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )
        except Exception:
            pass


@router.get("/websocket/stats")
async def get_websocket_stats():
    """获取 WebSocket 统计信息"""
    ws_collector = require_runtime_component("websocket", "WebSocket collector not initialized")
    return ws_collector.get_stats()
