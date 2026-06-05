"""Data management API route package."""

from fastapi import APIRouter

from src.core.graph_store import get_graph_store
from src.core.llm_manager import get_llm_manager
from src.core.memory_service import get_memory_service
from src.core.parsers.detector import get_detector
from src.core.vector_store import get_vector_store

router = APIRouter()

from src.api.routes.data.management_routes import (  # noqa: E402
    batch_create_memories,
    clear_all_data,
    export_data,
    import_data,
    rebuild_vector_index,
    router as management_router,
)
from src.api.routes.data.conversation_routes import (  # noqa: E402
    get_supported_formats,
    import_conversations,
    import_conversations_json,
    router as conversation_router,
)
from src.api.routes.data.history_routes import (  # noqa: E402
    get_recent_import_runs,
    router as history_router,
)

try:  # noqa: E402
    from src.api.routes.data.directory_routes import router as directory_router
except Exception:  # pragma: no cover - defensive import for optional route module
    directory_router = None

router.include_router(management_router)
router.include_router(conversation_router)
router.include_router(history_router)
if directory_router is not None:
    router.include_router(directory_router)

__all__ = [
    "batch_create_memories",
    "clear_all_data",
    "export_data",
    "get_detector",
    "get_graph_store",
    "get_llm_manager",
    "get_memory_service",
    "get_recent_import_runs",
    "get_supported_formats",
    "get_vector_store",
    "import_conversations",
    "import_conversations_json",
    "import_data",
    "rebuild_vector_index",
    "router",
]
