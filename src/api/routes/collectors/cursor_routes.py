"""Cursor-specific collectors routes."""

from fastapi import APIRouter

from src.api.routes.collectors.deps import require_runtime_component
from src.api.routes.collectors_runtime import (
    handle_get_cursor_conversations,
    handle_import_cursor_conversation,
)

router = APIRouter()


@router.get("/cursor/conversations")
async def get_cursor_conversations():
    """获取 Cursor 对话列表"""
    cursor = require_runtime_component("cursor", "Cursor collector not initialized")
    return await handle_get_cursor_conversations(cursor)


@router.post("/cursor/import/{conversation_id}")
async def import_cursor_conversation(conversation_id: str):
    """手动导入指定 Cursor 对话"""
    cursor = require_runtime_component("cursor", "Cursor collector not initialized")
    return await handle_import_cursor_conversation(
        cursor=cursor,
        conversation_id=conversation_id,
    )
