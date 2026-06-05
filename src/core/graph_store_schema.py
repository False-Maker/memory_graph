"""SQLite schema/bootstrap helpers for GraphStore."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        properties TEXT,
        source_text TEXT,
        confidence REAL DEFAULT 1.0,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS relationships (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        target_id TEXT NOT NULL,
        type TEXT NOT NULL,
        properties TEXT,
        confidence REAL DEFAULT 1.0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
        FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS communities (
        id TEXT PRIMARY KEY,
        level INTEGER NOT NULL,
        parent_id TEXT,
        title TEXT,
        summary TEXT,
        rank REAL DEFAULT 0.0,
        entity_count INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES communities(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_memberships (
        entity_id TEXT NOT NULL,
        community_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (entity_id, community_id),
        FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
        FOREIGN KEY (community_id) REFERENCES communities(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_registry (
        memory_id TEXT PRIMARY KEY,
        source_system TEXT NOT NULL,
        workspace_id TEXT,
        external_id TEXT,
        source_path TEXT,
        record_type TEXT,
        title TEXT,
        tags_json TEXT,
        content_checksum TEXT NOT NULL,
        timestamp TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        deleted_at TEXT,
        server_version INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_sync_state (
        memory_id TEXT PRIMARY KEY,
        sync_mode TEXT NOT NULL,
        ownership_mode TEXT NOT NULL,
        sync_status TEXT NOT NULL,
        last_client_mutation_id TEXT,
        last_client_seen_at TEXT,
        last_server_change_at TEXT,
        base_server_version INTEGER,
        external_revision TEXT,
        external_updated_at TEXT,
        tombstone INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY (memory_id) REFERENCES memory_registry(memory_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_entity_mentions (
        memory_id TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        mention_text TEXT,
        confidence REAL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (memory_id, entity_id),
        FOREIGN KEY (memory_id) REFERENCES memory_registry(memory_id) ON DELETE CASCADE,
        FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS memory_relationship_evidence (
        memory_id TEXT NOT NULL,
        relationship_id TEXT NOT NULL,
        source_entity_id TEXT NOT NULL,
        target_entity_id TEXT NOT NULL,
        relationship_type TEXT NOT NULL,
        confidence REAL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (memory_id, relationship_id),
        FOREIGN KEY (memory_id) REFERENCES memory_registry(memory_id) ON DELETE CASCADE,
        FOREIGN KEY (relationship_id) REFERENCES relationships(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_change_log (
        seq INTEGER PRIMARY KEY AUTOINCREMENT,
        memory_id TEXT NOT NULL,
        source_system TEXT NOT NULL,
        workspace_id TEXT,
        external_id TEXT,
        change_type TEXT NOT NULL,
        origin TEXT NOT NULL,
        client_mutation_id TEXT,
        server_version INTEGER NOT NULL,
        occurred_at TEXT NOT NULL,
        payload_json TEXT,
        FOREIGN KEY (memory_id) REFERENCES memory_registry(memory_id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS community_state (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        dirty INTEGER NOT NULL DEFAULT 0,
        last_reason TEXT,
        last_marked_at TEXT,
        last_rebuild_at TEXT,
        last_rebuild_job_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS temporal_triples (
        id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        relation_type TEXT NOT NULL,
        target_entity_id TEXT,
        valid_from TEXT,
        valid_to TEXT,
        confidence REAL DEFAULT 1.0,
        source TEXT,
        created_at TEXT NOT NULL,
        metadata TEXT,
        FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
        FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE SET NULL
    )
    """,
)

_COMMUNITY_STATE_SEED = """
INSERT OR IGNORE INTO community_state
(id, dirty, last_reason, last_marked_at, last_rebuild_at, last_rebuild_job_id)
VALUES (1, 0, NULL, NULL, NULL, NULL)
"""

_INDEX_STATEMENTS = (
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_registry_external
    ON memory_registry(source_system, workspace_id, external_id)
    """,
    "CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type)",
    "CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)",
    "CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_id)",
    "CREATE INDEX IF NOT EXISTS idx_communities_level ON communities(level)",
    """
    CREATE INDEX IF NOT EXISTS idx_community_memberships_community
    ON community_memberships(community_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_community_memberships_entity
    ON community_memberships(entity_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_registry_workspace
    ON memory_registry(source_system, workspace_id, deleted_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_memory_sync_status
    ON memory_sync_state(sync_status, tombstone)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sync_change_log_cursor
    ON sync_change_log(source_system, workspace_id, seq)
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_temporal_triples_entity_window
    ON temporal_triples(entity_id, valid_from, valid_to)
    """,
)


def get_vector_persist_directory(settings: Any) -> str:
    """Get the vector persistence directory from dict or settings object."""
    vector_config = settings.database.vector

    if isinstance(vector_config, dict):
        faiss_config = vector_config.get("faiss")
        if isinstance(faiss_config, dict):
            return faiss_config.get(
                "persist_directory",
                vector_config.get("persist_directory", "./data"),
            )
        return vector_config.get("persist_directory", "./data")

    faiss_config = getattr(vector_config, "faiss", None)
    if faiss_config is not None:
        persist_directory = getattr(faiss_config, "persist_directory", None)
        if persist_directory:
            return persist_directory

    persist_directory = getattr(vector_config, "persist_directory", None)
    if persist_directory:
        return persist_directory

    return "./data"


def get_graph_db_path(settings: Any) -> Path:
    """Resolve and create the graph SQLite path."""
    data_dir = Path(get_vector_persist_directory(settings))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "graph.db"


def bootstrap_graph_store_schema(conn: sqlite3.Connection) -> None:
    """Create all GraphStore tables and indexes."""
    cursor = conn.cursor()
    for statement in _SCHEMA_STATEMENTS:
        cursor.execute(statement)

    cursor.execute(_COMMUNITY_STATE_SEED)

    for statement in _INDEX_STATEMENTS:
        cursor.execute(statement)

    conn.commit()


def connect_graph_store(db_path: Path) -> sqlite3.Connection:
    """Open and bootstrap the SQLite database used by GraphStore."""
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    bootstrap_graph_store_schema(conn)
    return conn
