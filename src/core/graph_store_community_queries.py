"""Community query and hierarchy operations for GraphStore."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.core.graph_store_sqlite import require_connection

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphEntity


class GraphStoreCommunityQueryOps:
    """Read community state, memberships, and hierarchy relationships."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        row_to_dict: Callable[[Optional[sqlite3.Row]], Optional[Dict[str, Any]]],
        row_to_entity: Callable[[Optional[sqlite3.Row]], Optional[GraphEntity]],
        build_limit_offset_clause: Callable[[List[Any], Optional[int], int], str],
        get_child_community_ids_sync: Callable[[str], List[str]],
    ) -> None:
        self._get_connection = get_connection
        self._row_to_dict = row_to_dict
        self._row_to_entity = row_to_entity
        self._build_limit_offset_clause = build_limit_offset_clause
        self._get_child_community_ids_sync = get_child_community_ids_sync

    def _require_connection(self) -> sqlite3.Connection:
        return require_connection(self._get_connection())

    @staticmethod
    def _community_projection(community: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": community["id"],
            "level": community["level"],
            "title": community.get("title", ""),
            "rank": community.get("rank", 0.0),
        }

    async def get_leaf_entity_ids(self, community_id: str) -> List[str]:
        """Return all leaf entity IDs contained by a community."""
        conn = self._require_connection()
        pending = [community_id]
        visited: set[str] = set()
        entity_ids: List[str] = []

        while pending:
            current_id = pending.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            child_ids = self._get_child_community_ids_sync(current_id)
            if child_ids:
                pending.extend(child_ids)
                continue

            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT entity_id
                FROM community_memberships
                WHERE community_id = ?
                ORDER BY entity_id
                """,
                (current_id,),
            )
            entity_ids.extend(row["entity_id"] for row in cursor.fetchall())

        seen_entities: set[str] = set()
        ordered_unique_ids: List[str] = []
        for entity_id in entity_ids:
            if entity_id in seen_entities:
                continue
            seen_entities.add(entity_id)
            ordered_unique_ids.append(entity_id)

        return ordered_unique_ids

    async def get_community(
        self,
        community_id: str,
        include_entity_ids: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Get community by ID."""
        cursor = self._require_connection().cursor()
        cursor.execute("SELECT * FROM communities WHERE id = ?", (community_id,))
        row = cursor.fetchone()
        community = self._row_to_dict(row)
        if community is None:
            return None

        leaf_entity_ids = await self.get_leaf_entity_ids(community_id)
        community["entity_count"] = len(leaf_entity_ids)
        if include_entity_ids:
            community["entity_ids"] = leaf_entity_ids

        return community

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
        cursor = self._require_connection().cursor()
        clauses: List[str] = []
        params: List[Any] = []

        if level is not None:
            clauses.append("level = ?")
            params.append(level)

        if require_summary:
            clauses.append("summary IS NOT NULL")
            clauses.append("TRIM(summary) <> ''")

        query = "SELECT * FROM communities"
        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        if order_by == "level_rank":
            query += " ORDER BY level, rank DESC, id"
        else:
            query += " ORDER BY rank DESC, id"

        query += self._build_limit_offset_clause(params, limit, offset)
        cursor.execute(query, params)

        communities = [self._row_to_dict(row) for row in cursor.fetchall()]
        for community in communities:
            if community is None:
                continue
            leaf_entity_ids = await self.get_leaf_entity_ids(community["id"])
            community["entity_count"] = len(leaf_entity_ids)
            if include_entity_ids:
                community["entity_ids"] = leaf_entity_ids

        return [community for community in communities if community is not None]

    async def get_communities_by_level(
        self,
        level: int,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get communities by level."""
        return await self.list_communities(level=level, limit=limit)

    async def get_entity_communities(self, entity_id: str) -> List[str]:
        """Return community IDs containing an entity, ordered by level."""
        cursor = self._require_connection().cursor()
        cursor.execute(
            """
            SELECT c.id AS community_id
            FROM community_memberships m
            JOIN communities c ON c.id = m.community_id
            WHERE m.entity_id = ?
            ORDER BY c.level ASC, c.rank DESC, c.id
            """,
            (entity_id,),
        )
        return [row["community_id"] for row in cursor.fetchall()]

    async def get_community_entities(
        self,
        community_id: str,
        limit: Optional[int] = 50,
    ) -> List[GraphEntity]:
        """Return leaf entities contained by a community."""
        entity_ids = await self.get_leaf_entity_ids(community_id)
        if not entity_ids:
            return []

        placeholders = ",".join("?" for _ in entity_ids)
        params: List[Any] = list(entity_ids)
        query = f"""
            SELECT *
            FROM entities
            WHERE id IN ({placeholders})
            ORDER BY created_at DESC
        """
        query += self._build_limit_offset_clause(params, limit, 0)

        cursor = self._require_connection().cursor()
        cursor.execute(query, params)
        return [
            entity
            for row in cursor.fetchall()
            if (entity := self._row_to_entity(row)) is not None
        ]

    async def get_community_relationships(
        self,
        community_id: str,
        limit: Optional[int] = 50,
    ) -> List[Dict[str, Any]]:
        """Return relationships whose endpoints both belong to a community."""
        entity_ids = await self.get_leaf_entity_ids(community_id)
        if not entity_ids:
            return []

        placeholders = ",".join("?" for _ in entity_ids)
        params: List[Any] = [*entity_ids, *entity_ids]
        query = f"""
            SELECT
                r.id AS id,
                r.source_id AS source_id,
                s.name AS source,
                r.target_id AS target_id,
                t.name AS target,
                r.type AS type,
                r.created_at AS created_at
            FROM relationships r
            JOIN entities s ON s.id = r.source_id
            JOIN entities t ON t.id = r.target_id
            WHERE r.source_id IN ({placeholders})
              AND r.target_id IN ({placeholders})
            ORDER BY r.created_at DESC
        """
        query += self._build_limit_offset_clause(params, limit, 0)

        cursor = self._require_connection().cursor()
        cursor.execute(query, params)
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    async def get_community_neighbors(self, community_id: str) -> List[str]:
        """Find neighboring communities through cross-community relationships."""
        entity_ids = await self.get_leaf_entity_ids(community_id)
        if not entity_ids:
            return []

        placeholders = ",".join("?" for _ in entity_ids)
        cursor = self._require_connection().cursor()
        cursor.execute(
            f"""
            SELECT DISTINCT m2.community_id AS neighbor_id
            FROM relationships r
            JOIN community_memberships m1 ON m1.entity_id = r.source_id
            JOIN community_memberships m2 ON m2.entity_id = r.target_id
            WHERE m1.entity_id IN ({placeholders})
              AND m2.community_id <> m1.community_id
            ORDER BY neighbor_id
            """,
            entity_ids,
        )
        return [row["neighbor_id"] for row in cursor.fetchall()]

    async def get_community_ancestors(self, community_id: str) -> List[Dict[str, Any]]:
        """Return ancestor communities, closest first."""
        ancestors: List[Dict[str, Any]] = []
        current = await self.get_community(community_id)

        while current and current.get("parent_id"):
            parent = await self.get_community(current["parent_id"])
            if not parent:
                break
            ancestors.append(self._community_projection(parent))
            current = parent

        return ancestors

    async def get_community_descendants(
        self,
        community_id: str,
    ) -> List[Dict[str, Any]]:
        """Return descendant communities, immediate children first."""
        descendants: List[Dict[str, Any]] = []
        pending = self._get_child_community_ids_sync(community_id)

        while pending:
            current_id = pending.pop(0)
            current = await self.get_community(current_id)
            if not current:
                continue

            descendants.append(self._community_projection(current))
            pending.extend(self._get_child_community_ids_sync(current_id))

        descendants.sort(key=lambda item: item["level"], reverse=True)
        return descendants

    async def get_community_path(self, community_id: str) -> List[Dict[str, Any]]:
        """Return the path from the root community to the target community."""
        community = await self.get_community(community_id)
        if not community:
            return []

        path_nodes = [self._community_projection(community)]
        current_parent = community.get("parent_id")

        while current_parent:
            parent = await self.get_community(current_parent)
            if not parent:
                break
            path_nodes.append(self._community_projection(parent))
            current_parent = parent.get("parent_id")

        path_nodes.reverse()
        return path_nodes
