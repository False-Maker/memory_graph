"""Read/query operations for GraphStore sync metadata."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable, Dict, List, Optional

from src.core.graph_store_sqlite import require_connection


class GraphStoreSyncQueryOps:
    """Read memory registry, sync state, and change-log metadata."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        row_to_dict: Callable[[Optional[sqlite3.Row]], Optional[Dict[str, Any]]],
    ) -> None:
        self._get_connection = get_connection
        self._row_to_dict = row_to_dict

    def _require_connection(self) -> sqlite3.Connection:
        return require_connection(self._get_connection())

    async def get_memory_registry(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get a registry row by memory ID."""
        cursor = self._require_connection().cursor()
        cursor.execute("SELECT * FROM memory_registry WHERE memory_id = ?", (memory_id,))
        return self._row_to_dict(cursor.fetchone())

    async def get_memory_registry_by_external_key(
        self,
        source_system: str,
        workspace_id: Optional[str],
        external_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a registry row by external sync key."""
        cursor = self._require_connection().cursor()
        cursor.execute(
            """
            SELECT * FROM memory_registry
            WHERE source_system = ?
            AND ((workspace_id = ?) OR (workspace_id IS NULL AND ? IS NULL))
            AND external_id = ?
            """,
            (source_system, workspace_id, workspace_id, external_id),
        )
        return self._row_to_dict(cursor.fetchone())

    async def get_memory_sync_state(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Get sync state for a memory."""
        cursor = self._require_connection().cursor()
        cursor.execute("SELECT * FROM memory_sync_state WHERE memory_id = ?", (memory_id,))
        return self._row_to_dict(cursor.fetchone())

    async def get_memory_context(self, memory_id: str) -> Dict[str, Any]:
        """Get related entities and communities for one memory."""
        cursor = self._require_connection().cursor()

        cursor.execute(
            """
            SELECT
                e.id AS id,
                e.name AS name,
                e.type AS type,
                m.mention_text AS mention_text,
                COALESCE(m.confidence, e.confidence, 1.0) AS confidence,
                e.created_at AS created_at
            FROM memory_entity_mentions m
            JOIN entities e ON e.id = m.entity_id
            WHERE m.memory_id = ?
            ORDER BY e.created_at DESC, e.name ASC
            """,
            (memory_id,),
        )
        entities = [self._row_to_dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT DISTINCT
                c.id AS id,
                c.title AS title,
                c.level AS level,
                c.parent_id AS parent_id,
                c.summary AS summary,
                c.entity_count AS entity_count,
                c.rank AS rank,
                c.created_at AS created_at
            FROM memory_entity_mentions m
            JOIN community_memberships cm ON cm.entity_id = m.entity_id
            JOIN communities c ON c.id = cm.community_id
            WHERE m.memory_id = ?
            ORDER BY c.level ASC, c.rank DESC, c.id ASC
            """,
            (memory_id,),
        )
        communities = [self._row_to_dict(row) for row in cursor.fetchall()]

        return {
            "entities": entities,
            "communities": communities,
        }

    async def get_entity_memory_ids(
        self,
        entity_id: str,
        limit: Optional[int] = 20,
    ) -> List[str]:
        """Return non-deleted memory IDs that mention an entity, newest first."""
        cursor = self._require_connection().cursor()
        params: List[Any] = [entity_id]
        query = """
            SELECT m.memory_id AS memory_id
            FROM memory_entity_mentions m
            JOIN memory_registry mr ON mr.memory_id = m.memory_id
            WHERE m.entity_id = ?
              AND mr.deleted_at IS NULL
            ORDER BY
                COALESCE(m.created_at, mr.updated_at, mr.created_at) DESC,
                mr.updated_at DESC,
                m.memory_id ASC
        """
        if limit is not None:
            query += "\nLIMIT ?"
            params.append(limit)
        cursor.execute(query, params)
        return [row["memory_id"] for row in cursor.fetchall()]

    async def list_sync_changes(
        self,
        source_system: str,
        workspace_id: Optional[str],
        cursor_seq: int,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """List sync changes ordered by cursor."""
        cursor = self._require_connection().cursor()
        cursor.execute(
            """
            SELECT * FROM sync_change_log
            WHERE source_system = ?
            AND ((workspace_id = ?) OR (workspace_id IS NULL AND ? IS NULL))
            AND seq > ?
            ORDER BY seq ASC
            LIMIT ?
            """,
            (source_system, workspace_id, workspace_id, cursor_seq, limit),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    async def list_active_workspace_records(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> List[Dict[str, Any]]:
        """List active registry rows for a workspace."""
        cursor = self._require_connection().cursor()
        cursor.execute(
            """
            SELECT * FROM memory_registry
            WHERE source_system = ?
            AND ((workspace_id = ?) OR (workspace_id IS NULL AND ? IS NULL))
            AND deleted_at IS NULL
            ORDER BY updated_at DESC
            """,
            (source_system, workspace_id, workspace_id),
        )
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    async def get_sync_state_summary(
        self,
        source_system: str,
        workspace_id: Optional[str],
    ) -> Dict[str, Any]:
        """Get aggregate sync state for a workspace."""
        cursor = self._require_connection().cursor()

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_registry
            WHERE source_system = ?
            AND ((workspace_id = ?) OR (workspace_id IS NULL AND ? IS NULL))
            AND deleted_at IS NULL
            """,
            (source_system, workspace_id, workspace_id),
        )
        active_count = cursor.fetchone()["count"]

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_registry
            WHERE source_system = ?
            AND ((workspace_id = ?) OR (workspace_id IS NULL AND ? IS NULL))
            AND deleted_at IS NOT NULL
            """,
            (source_system, workspace_id, workspace_id),
        )
        tombstone_count = cursor.fetchone()["count"]

        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM memory_sync_state ss
            JOIN memory_registry mr ON mr.memory_id = ss.memory_id
            WHERE mr.source_system = ?
            AND ((mr.workspace_id = ?) OR (mr.workspace_id IS NULL AND ? IS NULL))
            AND ss.sync_status = 'conflict'
            """,
            (source_system, workspace_id, workspace_id),
        )
        conflict_count = cursor.fetchone()["count"]

        cursor.execute(
            """
            SELECT MAX(seq) AS last_seq, MAX(occurred_at) AS last_change
            FROM sync_change_log
            WHERE source_system = ?
            AND ((workspace_id = ?) OR (workspace_id IS NULL AND ? IS NULL))
            """,
            (source_system, workspace_id, workspace_id),
        )
        row = cursor.fetchone()

        return {
            "active_count": active_count,
            "tombstone_count": tombstone_count,
            "conflict_count": conflict_count,
            "last_change_seq": row["last_seq"] or 0,
            "last_server_change_at": row["last_change"],
        }
