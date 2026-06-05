"""Administrative/runtime operations for GraphStore."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

import networkx as nx

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphStats


class GraphStoreAdminOps:
    """Own statistics and runtime/admin operations for GraphStore."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        set_connection: Callable[[Optional[sqlite3.Connection]], None],
        get_graph: Callable[[], Optional[nx.MultiDiGraph]],
        lock: Any,
        table_exists: Callable[[str], bool],
        make_stats: Callable[[], GraphStats],
    ) -> None:
        self._get_connection = get_connection
        self._set_connection = set_connection
        self._get_graph = get_graph
        self._lock = lock
        self._table_exists = table_exists
        self._make_stats = make_stats

    def _require_connection(self) -> sqlite3.Connection:
        conn = self._get_connection()
        if conn is None:
            raise RuntimeError("GraphStore connection is not initialized")
        return conn

    def _require_graph(self) -> nx.MultiDiGraph:
        graph = self._get_graph()
        if graph is None:
            raise RuntimeError("GraphStore graph is not initialized")
        return graph

    async def detect_communities(self, level: int = 0):
        """Detect communities using Louvain algorithm."""
        graph = self._require_graph()
        conn = self._require_connection()
        if graph.number_of_nodes() == 0:
            return []

        undirected_graph = graph.to_undirected()

        try:
            from networkx.algorithms import community

            communities = community.louvain_communities(undirected_graph, seed=42)
            results = []
            for idx, detected_community in enumerate(communities):
                community_id = f"community_{level}_{idx}"
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO communities
                    (id, level, parent_id, title, summary, rank, entity_count, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        community_id,
                        level,
                        None,
                        f"Community {idx}",
                        "",
                        0.0,
                        len(detected_community),
                        datetime.now().isoformat(),
                    ),
                )
                conn.commit()

                results.append(
                    {
                        "id": community_id,
                        "level": level,
                        "entity_ids": list(detected_community),
                        "entity_count": len(detected_community),
                    }
                )

            return results

        except Exception as exc:
            print(f"Community detection error: {exc}")
            return []

    async def get_stats(self) -> GraphStats:
        """Get graph statistics."""
        cursor = self._require_connection().cursor()
        stats = self._make_stats()

        cursor.execute("SELECT COUNT(*) as count FROM entities")
        stats.total_entities = cursor.fetchone()["count"]

        cursor.execute("SELECT type, COUNT(*) as count FROM entities GROUP BY type")
        stats.entity_types = {row["type"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("SELECT COUNT(*) as count FROM relationships")
        stats.total_relationships = cursor.fetchone()["count"]

        if self._table_exists("memory_registry"):
            cursor.execute("SELECT COUNT(*) as count FROM memory_registry WHERE deleted_at IS NULL")
            stats.total_memories = cursor.fetchone()["count"]
        else:
            cursor.execute(
                "SELECT COUNT(DISTINCT source_text) as count FROM entities WHERE source_text IS NOT NULL AND source_text != ''"
            )
            stats.total_memories = cursor.fetchone()["count"]

        return stats

    async def clear_all(self) -> bool:
        """Clear all graph, sync, and community data."""
        conn = self._require_connection()
        graph = self._require_graph()
        with self._lock:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM sync_change_log")
            cursor.execute(
                "UPDATE community_state SET dirty = 0, last_reason = NULL, last_marked_at = NULL, last_rebuild_at = NULL, last_rebuild_job_id = NULL WHERE id = 1"
            )
            cursor.execute("DELETE FROM memory_relationship_evidence")
            cursor.execute("DELETE FROM memory_entity_mentions")
            cursor.execute("DELETE FROM memory_sync_state")
            cursor.execute("DELETE FROM memory_registry")
            cursor.execute("DELETE FROM relationships")
            cursor.execute("DELETE FROM entities")
            cursor.execute("DELETE FROM communities")
            conn.commit()
            graph.clear()

        return True

    async def close(self) -> None:
        """Close the SQLite connection."""
        conn = self._get_connection()
        if conn is not None:
            conn.close()
            self._set_connection(None)

    async def test_connection(self) -> bool:
        """Test SQLite connectivity."""
        try:
            cursor = self._require_connection().cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception:
            return False
