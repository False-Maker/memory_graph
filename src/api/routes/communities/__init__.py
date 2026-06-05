"""Communities API route package."""

import uuid

from fastapi import APIRouter

from src.core.community_detection import CommunityDetector
from src.core.community_summarizer import CommunitySummarizer
from src.core.graph_store import get_graph_store
from src.core.hierarchy import HierarchyBuilder

router = APIRouter()

from src.api.routes.communities.detection_routes import (  # noqa: E402
    detect_communities,
    get_community_status,
    router as detection_router,
)
from src.api.routes.communities.detail_routes import (  # noqa: E402
    get_community_ancestors,
    get_community_descendants,
    get_community_entities,
    get_community_relationships,
    router as detail_router,
)
from src.api.routes.communities.hierarchy_routes import (  # noqa: E402
    get_community,
    get_community_hierarchy,
    get_full_hierarchy,
    list_communities,
    router as hierarchy_router,
)
from src.api.routes.communities.summary_routes import (  # noqa: E402
    regenerate_summary,
    router as summary_router,
)

router.include_router(detection_router)
router.include_router(detail_router)
router.include_router(hierarchy_router)
router.include_router(summary_router)

__all__ = [
    "CommunityDetector",
    "CommunitySummarizer",
    "HierarchyBuilder",
    "detect_communities",
    "get_community",
    "get_community_ancestors",
    "get_community_descendants",
    "get_community_entities",
    "get_community_hierarchy",
    "get_community_relationships",
    "get_community_status",
    "get_full_hierarchy",
    "get_graph_store",
    "list_communities",
    "regenerate_summary",
    "router",
    "uuid",
]
