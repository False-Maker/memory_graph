"""Community state and write-path operations for GraphStore."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.core.graph_store_sqlite import require_connection


class GraphStoreCommunityStateOps:
    """Persist community state, metadata, and memberships."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        lock: Any,
    ) -> None:
        self._get_connection = get_connection
        self._lock = lock

    def _require_connection(self) -> sqlite3.Connection:
        return require_connection(self._get_connection())

    async def mark_community_dirty(
        self,
        reason: str,
        marked_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark community derivations as stale."""
        conn = self._require_connection()
        marked_at = marked_at or datetime.now().isoformat()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE community_state
                SET dirty = 1, last_reason = ?, last_marked_at = ?
                WHERE id = 1
                """,
                (reason, marked_at),
            )
            conn.commit()

        return await self.get_community_state()

    async def mark_community_clean(
        self,
        rebuild_at: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark community derivations as up to date."""
        conn = self._require_connection()
        rebuild_at = rebuild_at or datetime.now().isoformat()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE community_state
                SET dirty = 0, last_rebuild_at = ?, last_rebuild_job_id = ?
                WHERE id = 1
                """,
                (rebuild_at, job_id),
            )
            conn.commit()

        return await self.get_community_state()

    async def get_community_state(self) -> Dict[str, Any]:
        """Return persisted community rebuild state."""
        cursor = self._require_connection().cursor()
        cursor.execute("SELECT * FROM community_state WHERE id = 1")
        row = cursor.fetchone()
        if not row:
            return {
                "dirty": False,
                "last_reason": None,
                "last_marked_at": None,
                "last_rebuild_at": None,
                "last_rebuild_job_id": None,
            }

        return {
            "dirty": bool(row["dirty"]),
            "last_reason": row["last_reason"],
            "last_marked_at": row["last_marked_at"],
            "last_rebuild_at": row["last_rebuild_at"],
            "last_rebuild_job_id": row["last_rebuild_job_id"],
        }

    async def create_community(self, community: Any) -> str:
        """Create or replace a community."""
        conn = self._require_connection()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO communities
                (id, level, parent_id, title, summary, rank, entity_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    community.id,
                    community.level,
                    community.parent_id,
                    community.title,
                    community.summary,
                    community.rank,
                    len(community.entity_ids) if hasattr(community, "entity_ids") else 0,
                    community.created_at.isoformat(),
                ),
            )
            conn.commit()

        return community.id

    async def update_community_summary(self, community_id: str, summary: str) -> None:
        """Update a community summary."""
        conn = self._require_connection()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE communities SET summary = ? WHERE id = ?",
                (summary, community_id),
            )
            conn.commit()

    async def replace_community_memberships(
        self,
        community_id: str,
        entity_ids: List[str],
        created_at: Optional[str] = None,
    ) -> None:
        """Replace direct entity memberships for a community."""
        conn = self._require_connection()
        created_at = created_at or datetime.now().isoformat()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM community_memberships WHERE community_id = ?",
                (community_id,),
            )
            for entity_id in entity_ids:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO community_memberships
                    (entity_id, community_id, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (entity_id, community_id, created_at),
                )
            cursor.execute(
                "UPDATE communities SET entity_count = ? WHERE id = ?",
                (len(entity_ids), community_id),
            )
            conn.commit()

    async def set_community_entity_count(self, community_id: str, entity_count: int) -> None:
        """Persist a computed entity count for a community."""
        conn = self._require_connection()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE communities SET entity_count = ? WHERE id = ?",
                (entity_count, community_id),
            )
            conn.commit()

    async def count_community_memberships(self) -> int:
        """Count direct entity-to-community memberships."""
        cursor = self._require_connection().cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM community_memberships")
        row = cursor.fetchone()
        return row["count"] if row else 0

    async def set_community_parent(
        self,
        child_id: str,
        parent_id: Optional[str],
    ) -> bool:
        """Set or clear the parent of a community."""
        conn = self._require_connection()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE communities SET parent_id = ? WHERE id = ?",
                (parent_id, child_id),
            )
            conn.commit()
            return cursor.rowcount > 0
