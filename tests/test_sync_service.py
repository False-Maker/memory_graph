"""Tests for the generic sync service."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.schemas.sync import (
    SyncBatchUpsertRequest,
    SyncDeleteRequest,
    SyncRecordInput,
)
from src.core.entity_extractor import ExtractionResult
from src.core.vector_store import MemoryDocument


def build_record(**overrides) -> SyncRecordInput:
    """Build a default sync record input for tests."""
    payload = {
        "external_id": "external:workspace-main:dec_001",
        "source_path": "memory/2026-03-23.md",
        "record_type": "decision",
        "title": "Choose PostgreSQL",
        "content": "We decided to use PostgreSQL as the primary store.",
        "tags": ["database", "architecture"],
        "content_checksum": "sha256:abc",
        "external_updated_at": "2026-03-23T10:45:00+08:00",
        "external_revision": "git:abcd1234",
        "base_server_version": None,
        "client_mutation_id": "mut_001",
    }
    payload.update(overrides)
    return SyncRecordInput(**payload)


class TestSyncService:
    """Service-level sync semantics."""

    @pytest.mark.asyncio
    async def test_batch_upsert_creates_new_memory(self):
        """New external IDs should create a registry row and return created."""
        from src.core.sync.service import SyncService

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=None)
        mock_repository.save_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[build_record()],
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    with patch("src.core.sync.service.get_llm_manager", return_value=mock_llm):
                        with patch(
                            "src.core.sync.service.EntityExtractor.extract",
                            AsyncMock(return_value=ExtractionResult()),
                        ):
                            response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "created"
        assert response.results[0].sync_status == "synced"
        mock_repository.save_memory.assert_awaited_once()
        mock_vector_store.upsert_memory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_upsert_skips_duplicate_records_within_same_batch(self):
        """Semantic duplicates in one request should be short-circuited as noop."""
        from src.core.sync.service import SyncService

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=None)
        mock_repository.save_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[
                build_record(client_mutation_id="mut_001"),
                build_record(client_mutation_id="mut_002"),
            ],
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    with patch("src.core.sync.service.get_llm_manager", return_value=mock_llm):
                        with patch(
                            "src.core.sync.service.EntityExtractor.extract",
                            AsyncMock(return_value=ExtractionResult()),
                        ):
                            response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "created"
        assert response.results[1].result == "noop"
        assert response.results[1].detail == "duplicate record skipped in request batch"
        mock_repository.save_memory.assert_awaited_once()
        mock_vector_store.upsert_memory.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_upsert_restores_deleted_record_with_reused_embedding(self):
        """Restore should reuse an existing stored embedding when content is unchanged."""
        from src.core.sync.service import SyncService

        existing = {
            "memory_id": "mem_existing",
            "source_system": "external",
            "workspace_id": "workspace-main",
            "external_id": "external:workspace-main:dec_001",
            "source_path": "memory/2026-03-23.md",
            "record_type": "decision",
            "title": "Choose PostgreSQL",
            "tags_json": '["database"]',
            "content_checksum": "sha256:abc",
            "timestamp": "2026-03-23T10:45:00+08:00",
            "created_at": "2026-03-23T02:45:00+00:00",
            "updated_at": "2026-03-23T02:45:00+00:00",
            "deleted_at": "2026-03-23T03:00:00+00:00",
            "server_version": 2,
        }
        current_sync_state = {
            "memory_id": "mem_existing",
            "sync_mode": "two_way",
            "ownership_mode": "shared_with_external_anchor",
            "sync_status": "deleted",
            "last_server_change_at": "2026-03-23T03:00:00+00:00",
            "external_revision": "git:remote",
            "external_updated_at": "2026-03-23T10:45:00+08:00",
            "tombstone": 1,
        }

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=existing)
        mock_repository.get_memory_sync_state = AsyncMock(return_value=current_sync_state)
        mock_repository.save_memory = AsyncMock()

        existing_embedding = [0.1, 0.2, 0.3]
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=MemoryDocument(
                id="mem_existing",
                content="We decided to use PostgreSQL as the primary store.",
                metadata={},
                embedding=existing_embedding,
            )
        )
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(side_effect=RuntimeError("embed should not be called"))

        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[build_record(base_server_version=2)],
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    with patch("src.core.sync.service.get_llm_manager", return_value=mock_llm):
                        with patch(
                            "src.core.sync.service.EntityExtractor.extract",
                            AsyncMock(return_value=ExtractionResult()),
                        ):
                            response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "updated"
        mock_llm.embed.assert_not_awaited()
        mock_vector_store.upsert_memory.assert_awaited_once_with(
            memory_id="mem_existing",
            content="We decided to use PostgreSQL as the primary store.",
            embedding=existing_embedding,
            metadata=mock_vector_store.upsert_memory.await_args.kwargs["metadata"],
        )
        assert mock_repository.save_memory.await_args.kwargs["change_log_row"]["change_type"] == "restored"

    @pytest.mark.asyncio
    async def test_batch_upsert_skips_extraction_for_dated_session_artifact(self):
        """Date-prefixed session artifacts should embed but skip graph extraction."""
        from src.core.sync.service import SyncService

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=None)
        mock_repository.save_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[
                build_record(
                    source_path="memory/2026-03-24-analysis.md",
                    record_type="master_memory_entry",
                )
            ],
        )

        extract_mock = AsyncMock(side_effect=RuntimeError("extract should not be called"))
        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    with patch("src.core.sync.service.get_llm_manager", return_value=mock_llm):
                        with patch("src.core.sync.service.EntityExtractor.extract", extract_mock):
                            response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "created"
        extract_mock.assert_not_awaited()
        mock_llm.embed.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_batch_upsert_truncates_long_content_for_embedding(self):
        """Very long content should be truncated before embedding requests."""
        from src.core.sync.service import SyncService

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=None)
        mock_repository.save_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        long_content = "A" * 5000
        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[build_record(content=long_content, content_checksum="sha256:long")],
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    with patch("src.core.sync.service.get_llm_manager", return_value=mock_llm):
                        with patch(
                            "src.core.sync.service.EntityExtractor.extract",
                            AsyncMock(return_value=ExtractionResult()),
                        ):
                            response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "created"
        mock_llm.embed.assert_awaited_once_with(["A" * 4000])

    @pytest.mark.asyncio
    async def test_batch_upsert_preserves_engram_metadata_fields(self):
        """Sync upsert should keep Engram metadata in vector state and change payloads."""
        from src.core.sync.service import SyncService

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=None)
        mock_repository.save_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)
        mock_vector_store.upsert_memory = AsyncMock()
        mock_vector_store.update_memory = AsyncMock()

        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[
                build_record(
                    scope="task",
                    scope_id="task-123",
                    visibility="private",
                    owner="user-1",
                    session_id="session-1",
                    thread_id="thread-1",
                    task_id="task-123",
                    artifact_id="artifact-7",
                    summary="Launch summary",
                    confidence=0.93,
                    freshness=0.72,
                    pinned=True,
                    expires_at="2026-05-01T10:00:00+00:00",
                )
            ],
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    with patch("src.core.sync.service.get_llm_manager", return_value=mock_llm):
                        with patch(
                            "src.core.sync.service.EntityExtractor.extract",
                            AsyncMock(return_value=ExtractionResult()),
                        ):
                            response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "created"
        vector_metadata = mock_vector_store.upsert_memory.await_args.kwargs["metadata"]
        assert vector_metadata["scope"] == "task"
        assert vector_metadata["scope_id"] == "task-123"
        assert vector_metadata["visibility"] == "private"
        assert vector_metadata["owner"] == "user-1"
        assert vector_metadata["session_id"] == "session-1"
        assert vector_metadata["thread_id"] == "thread-1"
        assert vector_metadata["task_id"] == "task-123"
        assert vector_metadata["artifact_id"] == "artifact-7"
        assert vector_metadata["summary"] == "Launch summary"
        assert vector_metadata["confidence"] == 0.93
        assert vector_metadata["freshness"] == 0.72
        assert vector_metadata["pinned"] is True
        assert vector_metadata["expires_at"] == "2026-05-01T10:00:00+00:00"

        change_log_row = mock_repository.save_memory.await_args.kwargs["change_log_row"]
        payload = json.loads(change_log_row["payload_json"])
        assert payload["scope"] == "task"
        assert payload["scope_id"] == "task-123"
        assert payload["visibility"] == "private"
        assert payload["owner"] == "user-1"
        assert payload["session_id"] == "session-1"
        assert payload["thread_id"] == "thread-1"
        assert payload["task_id"] == "task-123"
        assert payload["artifact_id"] == "artifact-7"
        assert payload["summary"] == "Launch summary"
        assert payload["confidence"] == 0.93
        assert payload["freshness"] == 0.72
        assert payload["pinned"] is True
        assert payload["expires_at"] == "2026-05-01T10:00:00+00:00"

    @pytest.mark.asyncio
    async def test_batch_upsert_returns_conflict_for_stale_version(self):
        """Stale base_server_version should return conflict and mark sync state."""
        from src.core.sync.service import SyncService

        existing = {
            "memory_id": "mem_existing",
            "source_system": "external",
            "workspace_id": "workspace-main",
            "external_id": "external:workspace-main:dec_001",
            "source_path": "memory/2026-03-23.md",
            "record_type": "decision",
            "title": "Choose PostgreSQL",
            "tags_json": '["database"]',
            "content_checksum": "sha256:old",
            "timestamp": "2026-03-23T10:45:00+08:00",
            "created_at": "2026-03-23T02:45:00+00:00",
            "updated_at": "2026-03-23T02:45:00+00:00",
            "deleted_at": None,
            "server_version": 3,
        }
        current_sync_state = {
            "memory_id": "mem_existing",
            "sync_mode": "two_way",
            "ownership_mode": "shared_with_external_anchor",
            "sync_status": "synced",
            "last_server_change_at": "2026-03-23T02:45:00+00:00",
            "external_revision": "git:remote",
            "external_updated_at": "2026-03-23T10:45:00+08:00",
            "tombstone": 0,
        }

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=existing)
        mock_repository.get_memory_sync_state = AsyncMock(return_value=current_sync_state)
        mock_repository.save_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=MemoryDocument(
                id="mem_existing",
                content="Remote content",
                metadata={},
            )
        )

        request = SyncBatchUpsertRequest(
            workspace_id="workspace-main",
            client_id="external-sync",
            records=[build_record(content_checksum="sha256:new", base_server_version=2)],
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    response = await SyncService().batch_upsert_source_memories("external", request)

        assert response.results[0].result == "conflict"
        assert response.results[0].server_version == 3
        mock_repository.save_memory.assert_awaited_once()
        kwargs = mock_repository.save_memory.await_args.kwargs
        assert kwargs["sync_state_row"]["sync_status"] == "conflict"

    @pytest.mark.asyncio
    async def test_delete_source_memory_marks_tombstone(self):
        """Delete should remove the vector doc and tombstone the registry row."""
        from src.core.sync.service import SyncService

        existing = {
            "memory_id": "mem_existing",
            "source_system": "external",
            "workspace_id": "workspace-main",
            "external_id": "external:workspace-main:dec_001",
            "source_path": "memory/2026-03-23.md",
            "record_type": "decision",
            "title": "Choose PostgreSQL",
            "tags_json": '["database"]',
            "content_checksum": "sha256:old",
            "timestamp": "2026-03-23T10:45:00+08:00",
            "created_at": "2026-03-23T02:45:00+00:00",
            "updated_at": "2026-03-23T02:45:00+00:00",
            "deleted_at": None,
            "server_version": 5,
        }
        current_sync_state = {
            "memory_id": "mem_existing",
            "sync_mode": "two_way",
            "ownership_mode": "shared_with_external_anchor",
            "sync_status": "synced",
            "external_revision": "git:remote",
            "external_updated_at": "2026-03-23T10:45:00+08:00",
            "tombstone": 0,
        }

        mock_repository = MagicMock()
        mock_repository.get_memory_by_external_key = AsyncMock(return_value=existing)
        mock_repository.get_memory_sync_state = AsyncMock(return_value=current_sync_state)
        mock_repository.tombstone_memory = AsyncMock()

        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=MemoryDocument(
                id="mem_existing",
                content="Remote content",
                metadata={},
            )
        )
        mock_vector_store.delete_memory = AsyncMock(return_value=True)

        request = SyncDeleteRequest(
            base_server_version=5,
            external_revision="git:local",
            client_mutation_id="mut_delete",
        )

        with patch("src.core.sync.service.SyncRepository", return_value=mock_repository):
            with patch("src.core.sync.service.get_graph_store"):
                with patch("src.core.sync.service.get_vector_store", return_value=mock_vector_store):
                    response = await SyncService().delete_source_memory(
                        "external",
                        workspace_id="workspace-main",
                        external_id="external:workspace-main:dec_001",
                        request=request,
                    )

        assert response.result == "deleted"
        assert response.sync_status == "deleted"
        mock_vector_store.delete_memory.assert_awaited_once_with("mem_existing")
        mock_repository.tombstone_memory.assert_awaited_once()
