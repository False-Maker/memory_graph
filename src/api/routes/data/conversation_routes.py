"""Conversation import routes for data management."""

import json
import time
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from src.api.routes.data.deps import get_detector, get_memory_service
from src.api.routes.data.import_run_store import record_import_run
from src.api.security import read_upload_file_limited
from src.api.routes.data_helpers import build_conversation_import_response
from src.api.schemas.memory import ConversationImportRequest, ConversationImportResponse
from src.core.parsers.base import ParseError

router = APIRouter(prefix="/api/v1/data", tags=["data"])


def _record_import_run_safe(payload: dict[str, Any]) -> None:
    try:
        record_import_run(payload)
    except Exception:
        # History tracking must never fail import API behavior.
        return


@router.post("/import/conversations", response_model=ConversationImportResponse)
async def import_conversations(
    file: UploadFile = File(..., description="Conversation export file (JSON, JSONL, or ZIP for ChatGPT)"),
    output_format: str = Form("markdown", description="Output format: markdown or plain_text"),
):
    """
    Import conversations from export file.

    Supports:
    - ChatGPT export (ZIP or JSON)
    - Claude export (JSON)
    - DeepSeek export (JSON or JSONL)
    - Generic JSON/JSONL format
    """
    started_at = time.time()

    try:
        content = await read_upload_file_limited(file)
        filename = file.filename
        detector = get_detector()
        try:
            conversations, platform = detector.parse_file(content, filename)
        except ParseError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse conversation: {str(exc)}",
            ) from exc

        if not conversations:
            raise HTTPException(status_code=400, detail="No valid conversations found in file")

        response = await build_conversation_import_response(
            conversations=conversations,
            platform=platform,
            output_format=output_format,
            service=get_memory_service(),
            started_at=started_at,
        )
        status = "succeeded" if response.failed_count == 0 else "partial"
        _record_import_run_safe(
            {
                "status": status,
                "run_type": "conversation_import",
                "source": "data/import/conversations",
                "filename": filename,
                "imported": response.imported_memories,
                "failed": response.failed_count,
                "detail": f"platform={platform}",
            }
        )
        return response
    except HTTPException:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "conversation_import",
                "source": "data/import/conversations",
                "filename": file.filename,
                "imported": 0,
                "failed": 1,
            }
        )
        raise
    except Exception as exc:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "conversation_import",
                "source": "data/import/conversations",
                "filename": file.filename,
                "imported": 0,
                "failed": 1,
                "error": str(exc),
            }
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/import/conversations/json", response_model=ConversationImportResponse)
async def import_conversations_json(request: ConversationImportRequest):
    """
    Import conversations from JSON content.

    Supports:
    - ChatGPT format
    - Claude format
    - DeepSeek format
    - Generic JSON/JSONL format
    """
    started_at = time.time()

    try:
        detector = get_detector()
        try:
            data = json.loads(request.content)
            conversations, platform = detector.detect_and_parse(data)
        except json.JSONDecodeError:
            conversations, platform = detector.detect_and_parse(request.content)

        if not conversations:
            raise HTTPException(status_code=400, detail="No valid conversations found")

        output_format = request.output_format if request.output_format else "markdown"
        response = await build_conversation_import_response(
            conversations=conversations,
            platform=platform,
            output_format=output_format,
            service=get_memory_service(),
            started_at=started_at,
        )
        status = "succeeded" if response.failed_count == 0 else "partial"
        _record_import_run_safe(
            {
                "status": status,
                "run_type": "conversation_import",
                "source": "data/import/conversations/json",
                "filename": None,
                "imported": response.imported_memories,
                "failed": response.failed_count,
                "detail": f"platform={platform}",
            }
        )
        return response
    except HTTPException:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "conversation_import",
                "source": "data/import/conversations/json",
                "filename": None,
                "imported": 0,
                "failed": 1,
            }
        )
        raise
    except Exception as exc:
        _record_import_run_safe(
            {
                "status": "failed",
                "run_type": "conversation_import",
                "source": "data/import/conversations/json",
                "filename": None,
                "imported": 0,
                "failed": 1,
                "error": str(exc),
            }
        )
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/import/formats")
async def get_supported_formats():
    """Get list of supported conversation formats."""
    return {
        "success": True,
        "formats": [
            {
                "name": "ChatGPT",
                "platform": "chatgpt",
                "description": "OpenAI ChatGPT export (ZIP or JSON)",
                "extensions": [".zip", ".json"],
            },
            {
                "name": "Claude",
                "platform": "claude",
                "description": "Anthropic Claude export (JSON)",
                "extensions": [".json"],
            },
            {
                "name": "DeepSeek",
                "platform": "deepseek",
                "description": "DeepSeek chat export (JSON or JSONL)",
                "extensions": [".json", ".jsonl"],
            },
            {
                "name": "Claude Code",
                "platform": "claude_code",
                "description": "Claude Code session export (JSONL)",
                "extensions": [".jsonl"],
            },
            {
                "name": "Slack",
                "platform": "slack",
                "description": "Slack conversation export (JSON)",
                "extensions": [".json"],
            },
            {
                "name": "GitHub Codex",
                "platform": "codex",
                "description": "GitHub Codex conversation export (JSON)",
                "extensions": [".json"],
            },
            {
                "name": "Generic JSON",
                "platform": "unknown",
                "description": "Generic JSON format with messages array",
                "extensions": [".json", ".jsonl"],
            },
        ],
    }
