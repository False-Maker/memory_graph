"""Row serialization/conversion helpers for GraphStore."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

import networkx as nx

from src.core.graph_store_models import GraphEntity, GraphRelationship
from src.core.graph_store_sqlite import require_connection


def row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Convert a SQLite row into a plain dict."""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def row_to_entity(row: Optional[sqlite3.Row]) -> Optional[GraphEntity]:
    """Convert a SQLite row into a GraphEntity."""
    if row is None:
        return None

    return GraphEntity(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        properties=json.loads(row["properties"]) if row["properties"] else {},
        source_text=row["source_text"] or "",
        confidence=row["confidence"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def row_to_relationship(row: Optional[sqlite3.Row]) -> Optional[GraphRelationship]:
    """Convert a SQLite row into a GraphRelationship."""
    if row is None:
        return None

    return GraphRelationship(
        id=row["id"],
        source_id=row["source_id"],
        target_id=row["target_id"],
        type=row["type"],
        properties=json.loads(row["properties"]) if row["properties"] else {},
        confidence=row["confidence"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def serialize_json(value: Optional[Any]) -> str:
    """Serialize JSON values consistently for SQLite storage."""
    return json.dumps(value if value is not None else {})


def upsert_entity_row(cursor: sqlite3.Cursor, entity: GraphEntity) -> None:
    """Insert or replace an entity row."""
    cursor.execute(
        """
        INSERT OR REPLACE INTO entities
        (id, name, type, properties, source_text, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity.id,
            entity.name,
            entity.type,
            serialize_json(entity.properties),
            entity.source_text,
            entity.confidence,
            entity.created_at.isoformat(),
        ),
    )


def upsert_relationship_row(cursor: sqlite3.Cursor, rel: GraphRelationship) -> None:
    """Insert or replace a relationship row."""
    cursor.execute(
        """
        INSERT OR REPLACE INTO relationships
        (id, source_id, target_id, type, properties, confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            rel.id,
            rel.source_id,
            rel.target_id,
            rel.type,
            serialize_json(rel.properties),
            rel.confidence,
            rel.created_at.isoformat(),
        ),
    )


def prune_orphan_graph_objects(cursor: sqlite3.Cursor) -> None:
    """Remove graph rows that are no longer backed by memory evidence."""
    cursor.execute(
        """
        DELETE FROM relationships
        WHERE id LIKE 'rel_%'
        AND id NOT IN (
            SELECT relationship_id FROM memory_relationship_evidence
        )
        """
    )
    cursor.execute(
        """
        DELETE FROM entities
        WHERE id LIKE 'ent_%'
        AND id NOT IN (
            SELECT entity_id FROM memory_entity_mentions
        )
        AND id NOT IN (
            SELECT source_id FROM relationships
            UNION
            SELECT target_id FROM relationships
        )
        """
    )


def load_graph_from_connection(conn: Optional[sqlite3.Connection]) -> nx.MultiDiGraph:
    """Load all persisted entities and relationships into a NetworkX graph."""
    graph = nx.MultiDiGraph()
    cursor = require_connection(conn).cursor()

    cursor.execute("SELECT * FROM entities")
    for row in cursor.fetchall():
        graph.add_node(
            row["id"],
            name=row["name"],
            type=row["type"],
            properties=json.loads(row["properties"]) if row["properties"] else {},
            source_text=row["source_text"] or "",
            confidence=row["confidence"],
            created_at=row["created_at"],
        )

    cursor.execute("SELECT * FROM relationships")
    for row in cursor.fetchall():
        graph.add_edge(
            row["source_id"],
            row["target_id"],
            key=row["id"],
            id=row["id"],
            type=row["type"],
            properties=json.loads(row["properties"]) if row["properties"] else {},
            confidence=row["confidence"],
            created_at=row["created_at"],
        )

    return graph
