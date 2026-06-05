"""Collectors API route package."""

from fastapi import APIRouter, HTTPException, status

from src.core.collectors import BrowserMessage, get_unified_collector
from src.core.collectors.base import CollectorType, is_public_collector_type
from src.core.config import get_settings
from src.api.routes.collectors_scan import (
    DirectoryScanRequest,
    ScanResult,
    import_scan_results,
    perform_directory_scan,
)

router = APIRouter(prefix="/api/collectors", tags=["collectors"])


def _parse_collector_type(raw_type: str) -> CollectorType:
    """Parse a collector type string into CollectorType."""
    try:
        collector_type = CollectorType(raw_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid collector type: {raw_type}",
        ) from exc

    if not is_public_collector_type(collector_type):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collector not available in current product surface: {raw_type}",
        )

    return collector_type


def _parse_collector_types(raw_types: list[str] | None) -> list[CollectorType] | None:
    """Parse collector type strings into CollectorType enums."""
    if not raw_types:
        return None

    return [_parse_collector_type(value) for value in raw_types]


def _require_registered_collector(raw_type: str):
    """Return a registered collector or raise a route-shaped error."""
    collector_type = _parse_collector_type(raw_type)
    collector = get_unified_collector().get_collector(collector_type)
    if collector is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Collector not registered: {raw_type}",
        )
    return collector_type, collector


def _require_runtime_component(component_name: str, missing_detail: str):
    """Return a collector runtime component from the unified collector."""
    component = getattr(get_unified_collector(), component_name, None)
    if component is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=missing_detail,
        )
    return component


from src.api.routes.collectors.status_routes import (  # noqa: E402
    get_collector_status,
    get_collectors_status,
    router as status_router,
)
from src.api.routes.collectors.control_routes import (  # noqa: E402
    start_collector,
    start_collectors,
    stop_collector,
    stop_collectors,
    router as control_router,
)
from src.api.routes.collectors.file_watcher_routes import (  # noqa: E402
    add_watch_path,
    get_watched_paths,
    import_file,
    remove_watch_path,
    router as file_watcher_router,
)
from src.api.routes.collectors.cursor_routes import (  # noqa: E402
    get_cursor_conversations,
    import_cursor_conversation,
    router as cursor_router,
)
from src.api.routes.collectors.browser_routes import (  # noqa: E402
    capture_browser_message,
    router as browser_router,
)
from src.api.routes.collectors.websocket_routes import (  # noqa: E402
    get_websocket_stats,
    websocket_collectors,
    router as websocket_router,
)
from src.api.routes.collectors.import_routes import (  # noqa: E402
    import_directory,
    import_message,
    scan_directory,
    router as import_router,
)

router.include_router(status_router)
router.include_router(control_router)
router.include_router(file_watcher_router)
router.include_router(cursor_router)
router.include_router(browser_router)
router.include_router(websocket_router)
router.include_router(import_router)

__all__ = [
    "BrowserMessage",
    "DirectoryScanRequest",
    "ScanResult",
    "_parse_collector_type",
    "_parse_collector_types",
    "_require_registered_collector",
    "_require_runtime_component",
    "add_watch_path",
    "capture_browser_message",
    "get_collector_status",
    "get_collectors_status",
    "get_cursor_conversations",
    "get_settings",
    "get_unified_collector",
    "get_watched_paths",
    "get_websocket_stats",
    "import_directory",
    "import_file",
    "import_message",
    "import_scan_results",
    "import_cursor_conversation",
    "perform_directory_scan",
    "remove_watch_path",
    "router",
    "scan_directory",
    "start_collector",
    "start_collectors",
    "stop_collector",
    "stop_collectors",
    "websocket_collectors",
]
