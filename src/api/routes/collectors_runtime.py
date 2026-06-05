"""Runtime handler helpers for collectors routes."""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from fastapi import HTTPException, status


logger = logging.getLogger(__name__)


async def handle_start_collectors(
    *,
    unified: Any,
    settings: Any,
    request: Dict[str, Any],
    parse_collector_types: Callable[[Optional[List[str]]], Optional[List[Any]]],
) -> Dict[str, Any]:
    """Start collectors using the current settings snapshot."""
    config = {}
    if hasattr(settings, "collectors"):
        if hasattr(settings.collectors, "model_dump"):
            config = settings.collectors.model_dump()
        elif hasattr(settings.collectors, "dict"):
            config = settings.collectors.dict()
    unified.config = {**getattr(unified, "config", {}), "collectors": config}
    enabled_types = request.get("enabled_types") or request.get("collector_types")
    types = parse_collector_types(enabled_types)

    try:
        results = await unified.start(enabled_types=types)
        return {
            "status": "started",
            "results": results,
        }
    except Exception as exc:
        logger.error("Error starting collectors: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_stop_collectors(
    *,
    unified: Any,
    request: Dict[str, Any],
    parse_collector_types: Callable[[Optional[List[str]]], Optional[List[Any]]],
) -> Dict[str, Any]:
    """Stop all or selected collectors."""
    collector_types = request.get("collector_types")
    types = parse_collector_types(collector_types)

    try:
        if types:
            results = {}
            for collector_type in types:
                collector = unified.get_collector(collector_type)
                if collector is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Collector not registered: {collector_type.value}",
                    )
                results[collector_type.value] = await collector.stop()
            return {
                "status": "stopped",
                "results": results,
            }

        results = await unified.stop()
        return {
            "status": "stopped",
            "results": results,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error stopping collectors: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_single_collector_action(
    *,
    collector: Any,
    collector_type: str,
    action: str,
) -> Dict[str, Any]:
    """Run a single collector start/stop action and format the response."""
    try:
        success = await getattr(collector, action)()
        return {
            "status": ("started" if action == "start" else "stopped") if success else "failed",
            "collector_type": collector_type,
        }
    except Exception as exc:
        logger.error("Error %s collector %s: %s", action, collector_type, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


def handle_get_watched_paths(file_watcher: Any) -> Dict[str, List[str]]:
    """Return watched paths payload."""
    return {
        "paths": file_watcher.get_watched_paths(),
    }


def handle_watch_path_mutation(*, path: str, success: bool, status_label: str) -> Dict[str, Any]:
    """Format file watcher path mutation responses."""
    return {
        "status": status_label if success else "failed",
        "path": path,
    }


async def handle_import_file(*, file_watcher: Any, file_path: str) -> Dict[str, Any]:
    """Import a single file via the file watcher."""
    try:
        conversation = await file_watcher.import_file(file_path)
        if conversation:
            return {
                "status": "imported",
                "conversation_id": conversation.source_id,
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to import file: {file_path}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error importing file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_get_cursor_conversations(cursor: Any) -> Dict[str, Any]:
    """Return cursor conversation listing payload."""
    try:
        conversations = await cursor.get_conversations_list()
        return {
            "conversations": conversations,
            "total": len(conversations),
        }
    except Exception as exc:
        logger.error("Error getting Cursor conversations: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_import_cursor_conversation(
    *,
    cursor: Any,
    conversation_id: str,
) -> Dict[str, Any]:
    """Import a specific cursor conversation."""
    try:
        conversation = await cursor.import_conversation(conversation_id)
        if conversation:
            return {
                "status": "imported",
                "conversation_id": conversation.source_id,
            }
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation not found: {conversation_id}",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Error importing Cursor conversation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_capture_browser_message(*, browser: Any, message: Any) -> Any:
    """Capture a browser-sourced conversation payload."""
    try:
        return await browser.capture_message(message)
    except Exception as exc:
        logger.error("Error capturing browser message: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_import_message(*, unified: Any, source: str, data: Dict[str, Any]) -> Any:
    """Import a manually supplied message payload."""
    try:
        return await unified.import_message(source, data)
    except Exception as exc:
        logger.error("Error importing message: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


async def handle_import_directory(
    *,
    request: Any,
    scan_directory: Callable[[Any], Any],
    get_unified_collector: Callable[[], Any],
    import_scan_results: Callable[[Any, Any], Any],
    file_watcher_factory: Callable[[Dict[str, Any]], Any],
) -> Any:
    """Scan a directory and import its detected conversations."""
    scan_response = await scan_directory(request)
    unified = get_unified_collector()
    file_watcher = unified.file_watcher

    if file_watcher is None:
        file_watcher = file_watcher_factory(
            {
                "supported_extensions": request.extensions or [".txt", ".md", ".json", ".jsonl"],
            }
        )

    return await import_scan_results(
        scan_response,
        file_watcher.import_file,
        retries=getattr(request, "import_retries", 1),
    )
