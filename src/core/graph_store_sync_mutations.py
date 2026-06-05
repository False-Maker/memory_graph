"""Write/mutation operations for GraphStore sync metadata."""

from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from src.core.graph_store_sqlite import require_connection

if TYPE_CHECKING:
    from src.core.graph_store_models import GraphEntity, GraphRelationship


class GraphStoreSyncMutationOps:
    """Persist registry/sync rows and maintain graph evidence consistency."""

    def __init__(
        self,
        *,
        get_connection: Callable[[], Optional[sqlite3.Connection]],
        lock: Any,
        upsert_entity_row: Callable[[sqlite3.Cursor, GraphEntity], None],
        upsert_relationship_row: Callable[[sqlite3.Cursor, GraphRelationship], None],
        prune_orphan_graph_objects: Callable[[sqlite3.Cursor], None],
        load_graph: Callable[[], None],
    ) -> None:
        self._get_connection = get_connection
        self._lock = lock
        self._upsert_entity_row = upsert_entity_row
        self._upsert_relationship_row = upsert_relationship_row
        self._prune_orphan_graph_objects = prune_orphan_graph_objects
        self._load_graph = load_graph

    def _require_connection(self) -> sqlite3.Connection:
        return require_connection(self._get_connection())

    @staticmethod
    def _upsert_registry_row(cursor: sqlite3.Cursor, registry_row: Dict[str, Any]) -> None:
        cursor.execute(
            """
            INSERT OR REPLACE INTO memory_registry
            (
                memory_id, source_system, workspace_id, external_id, source_path,
                record_type, title, tags_json, content_checksum, timestamp,
                created_at, updated_at, deleted_at, server_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                registry_row["memory_id"],
                registry_row["source_system"],
                registry_row.get("workspace_id"),
                registry_row.get("external_id"),
                registry_row.get("source_path"),
                registry_row.get("record_type"),
                registry_row.get("title"),
                registry_row.get("tags_json", "[]"),
                registry_row["content_checksum"],
                registry_row.get("timestamp"),
                registry_row["created_at"],
                registry_row["updated_at"],
                registry_row.get("deleted_at"),
                registry_row["server_version"],
            ),
        )

    @staticmethod
    def _upsert_sync_state_row(cursor: sqlite3.Cursor, sync_state_row: Dict[str, Any]) -> None:
        cursor.execute(
            """
            INSERT OR REPLACE INTO memory_sync_state
            (
                memory_id, sync_mode, ownership_mode, sync_status,
                last_client_mutation_id, last_client_seen_at, last_server_change_at,
                base_server_version, external_revision, external_updated_at, tombstone
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                sync_state_row["memory_id"],
                sync_state_row["sync_mode"],
                sync_state_row["ownership_mode"],
                sync_state_row["sync_status"],
                sync_state_row.get("last_client_mutation_id"),
                sync_state_row.get("last_client_seen_at"),
                sync_state_row.get("last_server_change_at"),
                sync_state_row.get("base_server_version"),
                sync_state_row.get("external_revision"),
                sync_state_row.get("external_updated_at"),
                sync_state_row.get("tombstone", 0),
            ),
        )

    @staticmethod
    def _insert_change_log(cursor: sqlite3.Cursor, change_log_row: Dict[str, Any]) -> None:
        cursor.execute(
            """
            INSERT INTO sync_change_log
            (
                memory_id, source_system, workspace_id, external_id, change_type,
                origin, client_mutation_id, server_version, occurred_at, payload_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                change_log_row["memory_id"],
                change_log_row["source_system"],
                change_log_row.get("workspace_id"),
                change_log_row.get("external_id"),
                change_log_row["change_type"],
                change_log_row["origin"],
                change_log_row.get("client_mutation_id"),
                change_log_row["server_version"],
                change_log_row["occurred_at"],
                change_log_row.get("payload_json"),
            ),
        )

    def _replace_graph_evidence(
        self,
        cursor: sqlite3.Cursor,
        memory_id: str,
        *,
        entities: Optional[List[GraphEntity]],
        mentions: Optional[List[Dict[str, Any]]],
        relationships: Optional[List[GraphRelationship]],
        relationship_evidence: Optional[List[Dict[str, Any]]],
    ) -> None:
        cursor.execute(
            "DELETE FROM memory_relationship_evidence WHERE memory_id = ?",
            (memory_id,),
        )
        cursor.execute(
            "DELETE FROM memory_entity_mentions WHERE memory_id = ?",
            (memory_id,),
        )

        for entity in entities or []:
            self._upsert_entity_row(cursor, entity)

        for rel in relationships or []:
            self._upsert_relationship_row(cursor, rel)

        for mention in mentions or []:
            cursor.execute(
                """
                INSERT OR REPLACE INTO memory_entity_mentions
                (memory_id, entity_id, mention_text, confidence, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    mention["entity_id"],
                    mention.get("mention_text"),
                    mention.get("confidence"),
                    mention["created_at"],
                ),
            )

        for evidence in relationship_evidence or []:
            cursor.execute(
                """
                INSERT OR REPLACE INTO memory_relationship_evidence
                (
                    memory_id, relationship_id, source_entity_id,
                    target_entity_id, relationship_type, confidence, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    evidence["relationship_id"],
                    evidence["source_entity_id"],
                    evidence["target_entity_id"],
                    evidence["relationship_type"],
                    evidence.get("confidence"),
                    evidence["created_at"],
                ),
            )

        self._prune_orphan_graph_objects(cursor)

    async def upsert_memory_record(
        self,
        registry_row: Dict[str, Any],
        sync_state_row: Dict[str, Any],
        entities: Optional[List[GraphEntity]] = None,
        mentions: Optional[List[Dict[str, Any]]] = None,
        relationships: Optional[List[GraphRelationship]] = None,
        relationship_evidence: Optional[List[Dict[str, Any]]] = None,
        change_log_row: Optional[Dict[str, Any]] = None,
        replace_evidence: bool = False,
    ) -> None:
        """Persist a memory registry/sync row and optionally replace its graph evidence."""
        conn = self._require_connection()
        with self._lock:
            cursor = conn.cursor()
            try:
                self._upsert_registry_row(cursor, registry_row)
                self._upsert_sync_state_row(cursor, sync_state_row)

                if replace_evidence:
                    self._replace_graph_evidence(
                        cursor,
                        registry_row["memory_id"],
                        entities=entities,
                        mentions=mentions,
                        relationships=relationships,
                        relationship_evidence=relationship_evidence,
                    )

                if change_log_row:
                    self._insert_change_log(cursor, change_log_row)

                conn.commit()

                if replace_evidence:
                    self._load_graph()
            except Exception:
                conn.rollback()
                raise

    async def tombstone_memory_record(
        self,
        memory_id: str,
        deleted_at: str,
        updated_at: str,
        server_version: int,
        sync_state_updates: Dict[str, Any],
        change_log_row: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Mark a memory as deleted and garbage-collect its graph evidence."""
        conn = self._require_connection()
        with self._lock:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    UPDATE memory_registry
                    SET deleted_at = ?, updated_at = ?, server_version = ?
                    WHERE memory_id = ?
                    """,
                    (deleted_at, updated_at, server_version, memory_id),
                )
                self._upsert_sync_state_row(
                    cursor,
                    {
                        "memory_id": memory_id,
                        "sync_mode": sync_state_updates["sync_mode"],
                        "ownership_mode": sync_state_updates["ownership_mode"],
                        "sync_status": sync_state_updates["sync_status"],
                        "last_client_mutation_id": sync_state_updates.get("last_client_mutation_id"),
                        "last_client_seen_at": sync_state_updates.get("last_client_seen_at"),
                        "last_server_change_at": sync_state_updates.get("last_server_change_at"),
                        "base_server_version": sync_state_updates.get("base_server_version"),
                        "external_revision": sync_state_updates.get("external_revision"),
                        "external_updated_at": sync_state_updates.get("external_updated_at"),
                        "tombstone": sync_state_updates.get("tombstone", 1),
                    },
                )
                cursor.execute(
                    "DELETE FROM memory_relationship_evidence WHERE memory_id = ?",
                    (memory_id,),
                )
                cursor.execute(
                    "DELETE FROM memory_entity_mentions WHERE memory_id = ?",
                    (memory_id,),
                )
                self._prune_orphan_graph_objects(cursor)

                if change_log_row:
                    self._insert_change_log(cursor, change_log_row)

                conn.commit()
                self._load_graph()
            except Exception:
                conn.rollback()
                raise
