"""Hierarchy and lookup routes for communities."""

import os

from fastapi import APIRouter, HTTPException, Query

from src.api.routes.communities.deps import create_hierarchy_builder
from src.api.routes.communities_helpers import (
    build_community_response,
    build_descendant_subtree,
    build_hierarchy_node,
    find_tree_community,
    iter_tree_communities,
)
from src.api.schemas.community import (
    CommunityListResponse,
    CommunityResponse,
    HierarchyNode,
    HierarchyResponse,
)

router = APIRouter(prefix="/api/v1/communities", tags=["communities"])
_QA_FAIL_COMMUNITY_COLLECTIONS_ENV = "MEMORY_GRAPH_QA_FAIL_COMMUNITY_COLLECTIONS"


def _should_force_collection_failure(target: str) -> bool:
    raw = os.environ.get(_QA_FAIL_COMMUNITY_COLLECTIONS_ENV, "").strip()
    if not raw:
        return False
    enabled = {item.strip() for item in raw.split(",") if item.strip()}
    return target in enabled


@router.get("", response_model=CommunityListResponse)
async def list_communities(
    level: int | None = Query(default=None, ge=0, description="Filter by hierarchy level"),
    limit: int = Query(default=100, ge=1, le=500, description="Max communities to return"),
):
    """
    List all communities with optional filtering.

    Parameters:
    - level: Filter by hierarchy level (None = all levels)
    - limit: Maximum number of communities to return
    """
    try:
        if _should_force_collection_failure("list"):
            raise RuntimeError("QA forced failure for communities list")
        hierarchy_builder = create_hierarchy_builder()
        if level is not None:
            communities = await hierarchy_builder.get_level_communities(level)
        else:
            tree = await hierarchy_builder.get_hierarchy_tree()
            communities = list(iter_tree_communities(tree))

        community_responses = [build_community_response(c) for c in communities[:limit]]
        return CommunityListResponse(
            communities=community_responses,
            total=len(community_responses),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list communities: {str(exc)}",
        ) from exc


@router.get("/hierarchy", response_model=HierarchyResponse)
async def get_full_hierarchy():
    """
    Get the complete community hierarchy tree.

    Returns all communities structured as a hierarchy with roots at level 0
    and recursive children.
    """
    try:
        if _should_force_collection_failure("hierarchy"):
            raise RuntimeError("QA forced failure for communities hierarchy")
        hierarchy = await create_hierarchy_builder().get_hierarchy_tree()
        roots = [build_hierarchy_node(root) for root in hierarchy.get("roots", [])]
        return HierarchyResponse(
            roots=roots,
            levels=hierarchy.get("max_level", 0) + 1,
            total_communities=hierarchy.get("total_communities", len(roots)),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get hierarchy: {str(exc)}",
        ) from exc


@router.get("/{community_id}", response_model=CommunityResponse)
async def get_community(community_id: str):
    """
    Get detailed information about a specific community.

    Parameters:
    - community_id: Unique community identifier
    """
    try:
        tree = await create_hierarchy_builder().get_hierarchy_tree()
        community = find_tree_community(tree, community_id)
        if not community:
            raise HTTPException(
                status_code=404,
                detail=f"Community {community_id} not found",
            )
        return build_community_response(community)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get community: {str(exc)}",
        ) from exc


@router.get("/{community_id}/hierarchy", response_model=HierarchyNode)
async def get_community_hierarchy(community_id: str):
    """
    Get the hierarchy subtree rooted at a specific community.

    Returns the community and all its descendants in the hierarchy tree.

    Parameters:
    - community_id: Root community ID for subtree
    """
    try:
        hierarchy_builder = create_hierarchy_builder()
        descendants = await hierarchy_builder.get_descendants(community_id)
        if not descendants:
            raise HTTPException(
                status_code=404,
                detail=f"Community {community_id} not found or has no descendants",
            )

        tree = await hierarchy_builder.get_hierarchy_tree()
        root_community = find_tree_community(tree, community_id)
        if not root_community:
            raise HTTPException(
                status_code=404,
                detail=f"Community {community_id} not found",
            )

        return HierarchyNode(
            id=root_community["id"],
            title=root_community["title"],
            level=root_community["level"],
            entity_count=root_community.get("entity_count", 0),
            children=build_descendant_subtree(descendants, root_id=community_id),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get hierarchy subtree: {str(exc)}",
        ) from exc
