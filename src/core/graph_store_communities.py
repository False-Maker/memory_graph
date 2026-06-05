"""Community operations facade for GraphStore."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.core.graph_store_community_queries import GraphStoreCommunityQueryOps
from src.core.graph_store_community_state import GraphStoreCommunityStateOps

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphEntity


class GraphStoreCommunityOps:
    """Own community state, membership, and hierarchy behavior for GraphStore."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        lock: Any,
        row_to_dict: Callable[[Optional[sqlite3.Row]], Optional[Dict[str, Any]]],
        row_to_entity: Callable[[Optional[sqlite3.Row]], Optional[GraphEntity]],
        build_limit_offset_clause: Callable[[List[Any], Optional[int], int], str],
        get_child_community_ids_sync: Callable[[str], List[str]],
    ) -> None:
        self._state_ops = GraphStoreCommunityStateOps(
            get_connection=get_connection,
            lock=lock,
        )
        self._query_ops = GraphStoreCommunityQueryOps(
            get_connection=get_connection,
            row_to_dict=row_to_dict,
            row_to_entity=row_to_entity,
            build_limit_offset_clause=build_limit_offset_clause,
            get_child_community_ids_sync=get_child_community_ids_sync,
        )

    async def mark_community_dirty(
        self,
        reason: str,
        marked_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark community derivations as stale."""
        return await self._state_ops.mark_community_dirty(reason, marked_at=marked_at)

    async def mark_community_clean(
        self,
        rebuild_at: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark community derivations as up to date."""
        return await self._state_ops.mark_community_clean(rebuild_at=rebuild_at, job_id=job_id)

    async def get_community_state(self) -> Dict[str, Any]:
        """Return persisted community rebuild state."""
        return await self._state_ops.get_community_state()

    async def create_community(self, community: Any) -> str:
        """Create a community."""
        return await self._state_ops.create_community(community)

    async def get_leaf_entity_ids(self, community_id: str) -> List[str]:
        """Return all leaf entity IDs contained by a community."""
        return await self._query_ops.get_leaf_entity_ids(community_id)

    async def get_community(
        self,
        community_id: str,
        include_entity_ids: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get community by ID."""
        return await self._query_ops.get_community(
            community_id,
            include_entity_ids=include_entity_ids,
        )

    async def list_communities(
        self,
        level: Optional[int] = None,
        limit: Optional[int] = 100,
        offset: int = 0,
        require_summary: bool = False,
        include_entity_ids: bool = False,
        order_by: str = "rank_desc",
    ) -> List[Dict[str, Any]]:
        """List community records with optional filters."""
        return await self._query_ops.list_communities(
            level=level,
            limit=limit,
            offset=offset,
            require_summary=require_summary,
            include_entity_ids=include_entity_ids,
            order_by=order_by,
        )

    async def get_communities_by_level(self, level: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get communities by level."""
        return await self._query_ops.get_communities_by_level(level=level, limit=limit)

    async def get_entity_communities(self, entity_id: str) -> List[str]:
        """Return community IDs containing an entity, ordered by level."""
        return await self._query_ops.get_entity_communities(entity_id)

    async def get_community_entities(
        self,
        community_id: str,
        limit: Optional[int] = 50,
    ) -> List[GraphEntity]:
        """Return leaf entities contained by a community."""
        return await self._query_ops.get_community_entities(community_id, limit=limit)

    async def get_community_relationships(
        self,
        community_id: str,
        limit: Optional[int] = 50,
    ) -> List[Dict[str, Any]]:
        """Return relationships whose endpoints both belong to a community."""
        return await self._query_ops.get_community_relationships(community_id, limit=limit)

    async def update_community_summary(self, community_id: str, summary: str) -> None:
        """Update community summary."""
        await self._state_ops.update_community_summary(community_id, summary)

    async def replace_community_memberships(
        self,
        community_id: str,
        entity_ids: List[str],
        created_at: Optional[str] = None,
    ) -> None:
        """Replace entity memberships for a community."""
        await self._state_ops.replace_community_memberships(
            community_id,
            entity_ids,
            created_at=created_at,
        )

    async def refresh_community_entity_count(self, community_id: str) -> int:
        """Recompute and persist the leaf-entity count for a community."""
        entity_count = len(await self._query_ops.get_leaf_entity_ids(community_id))
        await self._state_ops.set_community_entity_count(community_id, entity_count)
        return entity_count

    async def count_community_memberships(self) -> int:
        """Count direct entity-to-community memberships."""
        return await self._state_ops.count_community_memberships()

    async def set_community_parent(
        self,
        child_id: str,
        parent_id: Optional[str],
    ) -> bool:
        """Set or clear the parent of a community."""
        return await self._state_ops.set_community_parent(child_id, parent_id)

    async def get_community_neighbors(self, community_id: str) -> List[str]:
        """Find neighboring communities through cross-community relationships."""
        return await self._query_ops.get_community_neighbors(community_id)

    async def get_community_ancestors(self, community_id: str) -> List[Dict[str, Any]]:
        """Return ancestor communities, closest first."""
        return await self._query_ops.get_community_ancestors(community_id)

    async def get_community_descendants(
        self,
        community_id: str,
    ) -> List[Dict[str, Any]]:
        """Return descendant communities, immediate children first."""
        return await self._query_ops.get_community_descendants(community_id)

    async def get_community_path(self, community_id: str) -> List[Dict[str, Any]]:
        """Return the path from the root community to the target community."""
        return await self._query_ops.get_community_path(community_id)
