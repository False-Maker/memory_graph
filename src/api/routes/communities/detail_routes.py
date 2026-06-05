"""Read-only detail routes for community facets."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from src.api.routes.communities.deps import create_hierarchy_builder, get_graph_store
from src.api.routes.communities_helpers import find_tree_community

router = APIRouter(prefix="/api/v1/communities", tags=["communities"])
_QA_FAIL_COMMUNITY_FACETS_ENV = "MEMORY_GRAPH_QA_FAIL_COMMUNITY_FACETS"


def _normalize_json(value: Any) -> Any:
    """Convert dataclass/datetime-heavy payloads into JSON-safe values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return _normalize_json(asdict(value))
    if isinstance(value, dict):
        return {str(key): _normalize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    return value


def _should_force_facet_failure(community_id: str, facet_name: str) -> bool:
    raw_config = os.environ.get(_QA_FAIL_COMMUNITY_FACETS_ENV, "").strip()
    if not raw_config:
        return False

    for rule in raw_config.split(";"):
        if ":" not in rule:
            continue
        rule_community_id, raw_facets = rule.split(":", 1)
        if rule_community_id.strip() != community_id:
            continue
        facets = {item.strip() for item in raw_facets.split(",") if item.strip()}
        if facet_name in facets:
            return True
    return False


async def _ensure_community_exists(community_id: str) -> None:
    tree = await create_hierarchy_builder().get_hierarchy_tree()
    if not find_tree_community(tree, community_id):
        raise HTTPException(status_code=404, detail=f"Community {community_id} not found")


@router.get("/{community_id}/entities")
async def get_community_entities(
    community_id: str,
    limit: int = Query(default=50, ge=1, le=500),
):
    """Return entities contained by a community."""
    try:
        await _ensure_community_exists(community_id)
        if _should_force_facet_failure(community_id, "entities"):
            raise RuntimeError(f"QA forced failure for community entities: {community_id}")
        entities = await get_graph_store().get_community_entities(community_id, limit=limit)
        normalized_entities = _normalize_json(entities)
        return {
            "community_id": community_id,
            "entities": normalized_entities,
            "total": len(normalized_entities),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get community entities: {exc}") from exc


@router.get("/{community_id}/relationships")
async def get_community_relationships(
    community_id: str,
    limit: int = Query(default=50, ge=1, le=500),
):
    """Return relationships whose endpoints belong to a community."""
    try:
        await _ensure_community_exists(community_id)
        if _should_force_facet_failure(community_id, "relationships"):
            raise RuntimeError(f"QA forced failure for community relationships: {community_id}")
        relationships = await get_graph_store().get_community_relationships(community_id, limit=limit)
        normalized_relationships = _normalize_json(relationships)
        return {
            "community_id": community_id,
            "relationships": normalized_relationships,
            "total": len(normalized_relationships),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get community relationships: {exc}") from exc


@router.get("/{community_id}/ancestors")
async def get_community_ancestors(community_id: str):
    """Return ancestor communities, closest first."""
    try:
        await _ensure_community_exists(community_id)
        if _should_force_facet_failure(community_id, "ancestors"):
            raise RuntimeError(f"QA forced failure for community ancestors: {community_id}")
        ancestors = await create_hierarchy_builder().get_ancestors(community_id)
        normalized_ancestors = _normalize_json(ancestors)
        return {
            "community_id": community_id,
            "ancestors": normalized_ancestors,
            "total": len(normalized_ancestors),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get community ancestors: {exc}") from exc


@router.get("/{community_id}/descendants")
async def get_community_descendants(community_id: str):
    """Return descendant communities."""
    try:
        await _ensure_community_exists(community_id)
        if _should_force_facet_failure(community_id, "descendants"):
            raise RuntimeError(f"QA forced failure for community descendants: {community_id}")
        descendants = await create_hierarchy_builder().get_descendants(community_id)
        normalized_descendants = _normalize_json(descendants)
        return {
            "community_id": community_id,
            "descendants": normalized_descendants,
            "total": len(normalized_descendants),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get community descendants: {exc}") from exc
