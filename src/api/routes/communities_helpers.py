"""Helper functions for communities routes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional

from src.api.schemas.community import CommunityResponse, HierarchyNode


def iter_tree_communities(tree: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Yield flattened community records from a hierarchy tree payload."""
    for level_data in tree.get("levels", {}).values():
        yield from level_data


def find_tree_community(
    tree: dict[str, Any],
    community_id: str,
) -> Optional[dict[str, Any]]:
    """Find a community record by ID inside a hierarchy tree payload."""
    for community in iter_tree_communities(tree):
        if community["id"] == community_id:
            return community
    return None


def build_community_response(community: dict[str, Any]) -> CommunityResponse:
    """Convert a stored community mapping into an API response model."""
    return CommunityResponse(
        id=community["id"],
        level=community["level"],
        parent_id=community.get("parent_id"),
        title=community["title"],
        summary=community.get("summary", ""),
        entity_count=community.get("entity_count", 0),
        rank=community.get("rank", 0.5),
        created_at=community.get("created_at", datetime.now()),
    )


def build_hierarchy_node(node_dict: dict[str, Any]) -> HierarchyNode:
    """Recursively convert a hierarchy mapping into a HierarchyNode."""
    return HierarchyNode(
        id=node_dict["id"],
        title=node_dict["title"],
        level=node_dict["level"],
        entity_count=node_dict.get("entity_count", 0),
        children=[build_hierarchy_node(child) for child in node_dict.get("children", [])],
    )


def build_descendant_subtree(
    descendants: list[dict[str, Any]],
    *,
    root_id: str,
) -> list[HierarchyNode]:
    """Build children subtree nodes from a flat descendants list."""

    def build_children(parent_id: str) -> list[HierarchyNode]:
        return [
            HierarchyNode(
                id=node["id"],
                title=node["title"],
                level=node["level"],
                entity_count=node.get("entity_count", 0),
                children=build_children(node["id"]),
            )
            for node in descendants
            if node.get("parent_id") == parent_id
        ]

    return build_children(root_id)
