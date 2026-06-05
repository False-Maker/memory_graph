"""Tests for shared memory ingestion service."""

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.entity_extractor import ExtractionResult
from src.core.memory_service import MemoryService
from src.core.vector_store import MemoryDocument


class TestMemoryService:
    """Legacy/manual memory pipeline behavior."""

    @pytest.mark.asyncio
    async def test_ingest_memory_creates_registry_and_marks_community_dirty(self):
        """Manual ingest should write registry/evidence and dirty community state."""
        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        mock_vector_store = MagicMock()
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(return_value=None)
        mock_graph_store.get_memory_registry_by_external_key = AsyncMock(return_value=None)
        mock_graph_store.upsert_memory_record = AsyncMock()
        mock_graph_store.mark_community_dirty = AsyncMock()

        service = MemoryService(
            llm=mock_llm,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
        )
        service.extractor.extract = AsyncMock(return_value=ExtractionResult())

        result = await service.ingest_memory(
            content="We decided to use PostgreSQL as the primary database.",
            metadata={"source": "manual", "title": "Database decision"},
            source_system="manual",
        )

        assert result.result == "created"
        assert result.server_version == 1
        mock_graph_store.upsert_memory_record.assert_awaited_once()
        mock_graph_store.mark_community_dirty.assert_awaited_once()
        mock_vector_store.upsert_memory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_memory_tombstones_registry_and_marks_community_dirty(self):
        """Delete should remove vector content and tombstone registry-backed memories."""
        mock_llm = MagicMock()
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=MemoryDocument(
                id="mem_123",
                content="Stored content",
                metadata={},
            )
        )
        mock_vector_store.delete_memory = AsyncMock(return_value=True)

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(
            return_value={
                "memory_id": "mem_123",
                "source_system": "manual",
                "workspace_id": None,
                "external_id": None,
                "source_path": None,
                "record_type": "manual",
                "title": "Database decision",
                "tags_json": "[]",
                "content_checksum": "sha256:abc",
                "created_at": "2026-03-23T00:00:00+00:00",
                "updated_at": "2026-03-23T00:00:00+00:00",
                "deleted_at": None,
                "server_version": 4,
            }
        )
        mock_graph_store.get_memory_sync_state = AsyncMock(
            return_value={
                "sync_mode": "internal",
                "ownership_mode": "server_managed",
                "external_revision": None,
                "external_updated_at": None,
            }
        )
        mock_graph_store.tombstone_memory_record = AsyncMock()
        mock_graph_store.mark_community_dirty = AsyncMock()

        service = MemoryService(
            llm=mock_llm,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
        )

        result = await service.delete_memory("mem_123")

        assert result.deleted is True
        assert result.server_version == 5
        mock_vector_store.delete_memory.assert_awaited_once_with("mem_123")
        mock_graph_store.tombstone_memory_record.assert_awaited_once()
        mock_graph_store.mark_community_dirty.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ingest_memory_merges_regex_entity_hints_into_graph_evidence(self):
        """Regex entity hints from the import chain should reach persisted graph evidence."""
        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        mock_vector_store = MagicMock()
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(return_value=None)
        mock_graph_store.get_memory_registry_by_external_key = AsyncMock(return_value=None)
        mock_graph_store.upsert_memory_record = AsyncMock()
        mock_graph_store.mark_community_dirty = AsyncMock()

        service = MemoryService(
            llm=mock_llm,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
        )
        service.extractor.extract = AsyncMock(return_value=ExtractionResult())

        result = await service.ingest_memory(
            content="Alice worked on Memory Graph at OpenAI. Alice later mentioned OpenAI again.",
            metadata={
                "source": "claude_code",
                "title": "Imported conversation",
                "regex_entity_hints": [
                    {
                        "text": "Alice",
                        "type": "name",
                        "frequency": 2,
                        "confidence": 0.9,
                        "message_indexes": [0, 1],
                        "message_roles": ["user", "assistant"],
                    },
                    {
                        "text": "OpenAI",
                        "type": "organization",
                        "frequency": 2,
                        "confidence": 1.0,
                        "message_indexes": [0, 1],
                        "message_roles": ["user", "assistant"],
                    },
                ],
            },
            source_system="claude_code",
        )

        persisted_entities = mock_graph_store.upsert_memory_record.await_args.kwargs["entities"]

        assert result.entities_count == 2
        assert {entity.name for entity in persisted_entities} == {"Alice", "OpenAI"}

    @pytest.mark.asyncio
    async def test_ingest_memory_preserves_engram_metadata_and_updates_metadata_only_changes(self):
        """Engram-facing metadata fields should persist and trigger metadata-only updates."""
        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        mock_vector_store = MagicMock()
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(return_value=None)
        mock_graph_store.get_memory_sync_state = AsyncMock(return_value={"external_revision": "rev-1"})
        mock_graph_store.upsert_memory_record = AsyncMock()
        mock_graph_store.mark_community_dirty = AsyncMock()

        service = MemoryService(
            llm=mock_llm,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
        )
        service.extractor.extract = AsyncMock(return_value=ExtractionResult())

        mock_graph_store.get_memory_registry_by_external_key = AsyncMock(return_value=None)
        created = await service.ingest_memory(
            content="Scoped launch memory",
            metadata={
                "source": "manual",
                "workspace_id": "workspace-main",
                "external_id": "ext-1",
                "scope": "task",
                "scope_id": "task-123",
                "visibility": "private",
                "owner": "user-1",
                "session_id": "session-1",
                "thread_id": "thread-1",
                "task_id": "task-123",
                "artifact_id": "artifact-7",
                "summary": "Launch summary",
                "confidence": 0.93,
                "freshness": 0.72,
                "pinned": True,
                "expires_at": datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            },
        )

        assert created.result == "created"
        created_metadata = mock_vector_store.upsert_memory.await_args.kwargs["metadata"]
        assert created_metadata["scope"] == "task"
        assert created_metadata["scope_id"] == "task-123"
        assert created_metadata["visibility"] == "private"
        assert created_metadata["owner"] == "user-1"
        assert created_metadata["session_id"] == "session-1"
        assert created_metadata["thread_id"] == "thread-1"
        assert created_metadata["task_id"] == "task-123"
        assert created_metadata["artifact_id"] == "artifact-7"
        assert created_metadata["summary"] == "Launch summary"
        assert created_metadata["confidence"] == 0.93
        assert created_metadata["freshness"] == 0.72
        assert created_metadata["pinned"] is True
        assert created_metadata["expires_at"] == datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)

        existing_row = {
            "memory_id": mock_graph_store.upsert_memory_record.await_args.kwargs["registry_row"]["memory_id"],
            "source_system": "manual",
            "workspace_id": "workspace-main",
            "external_id": "ext-1",
            "source_path": None,
            "record_type": "manual",
            "title": None,
            "tags_json": "[]",
            "content_checksum": created_metadata["content_checksum"],
            "timestamp": None,
            "created_at": "2026-04-01T00:00:00+00:00",
            "updated_at": "2026-04-01T00:00:00+00:00",
            "deleted_at": None,
            "server_version": 1,
        }
        current_doc = MemoryDocument(
            id=existing_row["memory_id"],
            content="Scoped launch memory",
            metadata=created_metadata,
            embedding=[0.1, 0.2, 0.3],
        )
        mock_graph_store.get_memory_registry_by_external_key = AsyncMock(return_value=existing_row)
        mock_vector_store.get_memory = AsyncMock(return_value=current_doc)
        mock_vector_store.upsert_memory.reset_mock()
        mock_vector_store.update_memory.reset_mock()

        updated = await service.ingest_memory(
            content="Scoped launch memory",
            metadata={
                "source": "manual",
                "workspace_id": "workspace-main",
                "external_id": "ext-1",
                "scope": "task",
                "scope_id": "task-123",
                "visibility": "private",
                "owner": "user-1",
                "session_id": "session-1",
                "thread_id": "thread-1",
                "task_id": "task-123",
                "artifact_id": "artifact-7",
                "summary": "Updated launch summary",
                "confidence": 0.95,
                "freshness": 0.8,
                "pinned": False,
                "expires_at": datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
            },
        )

        assert updated.result == "updated"
        mock_vector_store.update_memory.assert_awaited_once()
        updated_metadata = mock_vector_store.update_memory.await_args.kwargs["metadata"]
        assert updated_metadata["summary"] == "Updated launch summary"
        assert updated_metadata["confidence"] == 0.95
        assert updated_metadata["freshness"] == 0.8
        assert updated_metadata["pinned"] is False
