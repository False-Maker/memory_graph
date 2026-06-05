"""Shared SQLite helpers for GraphStore."""

from __future__ import annotations

import sqlite3
from typing import Any, List, Optional


def require_connection(conn: Optional[sqlite3.Connection]) -> sqlite3.Connection:
    """Return the active GraphStore connection or raise a runtime error."""
    if conn is None:
        raise RuntimeError("GraphStore connection is not initialized")
    return conn


def table_exists(conn: Optional[sqlite3.Connection], table_name: str) -> bool:
    """Check whether a SQLite table exists."""
    cursor = require_connection(conn).cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def build_limit_offset_clause(
    params: List[Any],
    limit: Optional[int],
    offset: int,
) -> str:
    """Build a SQLite LIMIT/OFFSET clause."""
    clause = ""
    if limit is not None:
        clause = " LIMIT ?"
        params.append(limit)
        if offset:
            clause += " OFFSET ?"
            params.append(offset)
    elif offset:
        clause = " LIMIT -1 OFFSET ?"
        params.append(offset)
    return clause


def get_child_community_ids_sync(
    conn: Optional[sqlite3.Connection],
    community_id: str,
) -> List[str]:
    """Return direct child community IDs for a community."""
    cursor = require_connection(conn).cursor()
    cursor.execute(
        """
        SELECT id
        FROM communities
        WHERE parent_id = ?
        ORDER BY level DESC, rank DESC, id
        """,
        (community_id,),
    )
    return [row["id"] for row in cursor.fetchall()]
