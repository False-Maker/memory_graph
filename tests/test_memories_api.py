"""Focused tests for /api/v1/memories endpoints."""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _expected_metadata(**overrides):
    payload = {
        "source": None,
        "workspace_id": None,
        "external_id": None,
        "source_path": None,
        "record_type": None,
        "title": None,
        "tags": [],
        "timestamp": None,
        "content_checksum": None,
        "external_revision": None,
        "external_updated_at": None,
        "platform": None,
        "conversation_id": None,
        "archived": None,
        "archived_at": None,
        "scope": None,
        "scope_id": None,
        "visibility": None,
        "owner": None,
        "session_id": None,
        "thread_id": None,
        "task_id": None,
        "artifact_id": None,
        "summary": None,
        "confidence": None,
        "freshness": None,
        "pinned": None,
        "expires_at": None,
    }
    payload.update(overrides)
    return payload


def _expected_collection_diagnostics(**overrides):
    payload = {
        "applied_filters": {},
        "server_side_filtered": False,
        "truncated": False,
        "candidate_window": None,
        "warnings": [],
    }
    payload.update(overrides)
    return payload


class TestMemoriesEndpoint:
    """Test /api/v1/memories endpoints."""

    @pytest.mark.asyncio
    async def test_list_memories_returns_serialized_items(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memories = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="mem-1",
                    content="Remember this",
                    metadata={"source": "manual", "tags": ["important"]},
                )
            ]
        )
        mock_vector_store.get_count = AsyncMock(return_value=1)

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(
            return_value={"created_at": "2026-03-26T09:00:00"}
        )

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                response = await client.get("/api/v1/memories?limit=10&offset=0")

        assert response.status_code == 200
        assert response.json() == {
            "memories": [
                {
                    "id": "mem-1",
                    "content": "Remember this",
                    "summary": None,
                    "metadata": _expected_metadata(source="manual", tags=["important"]),
                    "provenance": {
                        "type": "manual",
                        "time": "2026-03-26T09:00:00",
                        "imported_from": None,
                    },
                    "created_at": "2026-03-26T09:00:00",
                }
            ],
            "total": 1,
            "limit": 10,
            "offset": 0,
            "next_cursor": None,
            "diagnostics": _expected_collection_diagnostics(),
        }
        mock_vector_store.get_memories.assert_awaited_once_with(limit=None, offset=0)

    @pytest.mark.asyncio
    async def test_list_memories_filters_active_and_archived_status(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memories = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="mem-active",
                    content="Visible memory",
                    metadata={"source": "manual", "archived": False},
                ),
                SimpleNamespace(
                    id="mem-archived",
                    content="Archived memory",
                    metadata={"source": "manual", "archived": True, "archived_at": "2026-04-05T12:00:00"},
                ),
            ]
        )

        mock_graph_store = MagicMock()
        async def get_registry(memory_id):
            if memory_id == "mem-active":
                return {"created_at": "2026-04-04T09:00:00"}
            return {"created_at": "2026-04-05T09:00:00"}

        mock_graph_store.get_memory_registry = AsyncMock(side_effect=get_registry)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                active_response = await client.get("/api/v1/memories?limit=10&offset=0&status=active")
                archived_response = await client.get("/api/v1/memories?limit=10&offset=0&status=archived")
                all_response = await client.get("/api/v1/memories?limit=10&offset=0&status=all")

        assert active_response.status_code == 200
        assert [item["id"] for item in active_response.json()["memories"]] == ["mem-active"]
        assert active_response.json()["total"] == 1

        assert archived_response.status_code == 200
        assert [item["id"] for item in archived_response.json()["memories"]] == ["mem-archived"]
        assert archived_response.json()["total"] == 1

        assert all_response.status_code == 200
        assert [item["id"] for item in all_response.json()["memories"]] == ["mem-archived", "mem-active"]
        assert all_response.json()["total"] == 2

    @pytest.mark.asyncio
    async def test_list_memories_rejects_invalid_status_filter(self, client):
        response = await client.get("/api/v1/memories?status=broken")

        assert response.status_code == 400
        assert "Invalid status filter" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_memories_supports_qa_forced_failure(self, client):
        with patch.dict(os.environ, {"MEMORY_GRAPH_QA_FAIL_MEMORIES_LIST": "1"}, clear=False):
            response = await client.get("/api/v1/memories?limit=10&offset=0")

        assert response.status_code == 500
        assert response.json() == {"detail": "QA forced failure for memories list"}

    @pytest.mark.asyncio
    async def test_list_memories_returns_most_recent_items_first(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memories = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="mem-old",
                    content="Older memory",
                    metadata={"source": "manual", "title": "Old"},
                ),
                SimpleNamespace(
                    id="mem-new",
                    content="Newer memory",
                    metadata={"source": "manual", "title": "New"},
                ),
            ]
        )

        async def get_registry(memory_id):
            if memory_id == "mem-old":
                return {"created_at": "2026-04-01T09:00:00"}
            return {"created_at": "2026-04-03T09:00:00"}

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(side_effect=get_registry)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                response = await client.get("/api/v1/memories?limit=10&offset=0")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()["memories"]] == ["mem-new", "mem-old"]

    @pytest.mark.asyncio
    async def test_get_memory_returns_provenance_summary(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=SimpleNamespace(
                id="mem-2",
                content="Restore checklist",
                metadata={
                    "source": "sync",
                    "record_type": "decision",
                    "source_path": "notes/restore.md",
                    "timestamp": "2026-04-02T10:30:00",
                },
            )
        )
        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(
            return_value={"created_at": "2026-04-02T09:00:00"}
        )

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                response = await client.get("/api/v1/memories/mem-2")

        assert response.status_code == 200
        assert response.json() == {
            "id": "mem-2",
            "content": "Restore checklist",
            "summary": None,
            "metadata": _expected_metadata(
                source="sync",
                source_path="notes/restore.md",
                record_type="decision",
                timestamp="2026-04-02T10:30:00",
            ),
            "provenance": {
                "type": "decision",
                "time": "2026-04-02T10:30:00",
                "imported_from": "notes/restore.md",
            },
            "created_at": "2026-04-02T09:00:00",
        }

    @pytest.mark.asyncio
    async def test_list_memories_supports_structured_metadata_filters(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memories = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="mem-keep",
                    content="Keep this memory",
                    metadata={
                        "source": "manual",
                        "workspace_id": "workspace-main",
                        "session_id": "session-1",
                        "scope": "task",
                        "scope_id": "task-123",
                        "visibility": "private",
                        "task_id": "task-123",
                        "tags": ["launch"],
                    },
                ),
                SimpleNamespace(
                    id="mem-drop",
                    content="Drop this memory",
                    metadata={
                        "source": "manual",
                        "workspace_id": "workspace-main",
                        "session_id": "session-2",
                        "scope": "task",
                        "scope_id": "task-999",
                        "visibility": "private",
                        "task_id": "task-999",
                        "tags": ["ops"],
                    },
                ),
            ]
        )
        mock_graph_store = MagicMock()

        async def get_registry(memory_id):
            return {"created_at": "2026-04-06T10:00:00"} if memory_id == "mem-keep" else {"created_at": "2026-04-05T10:00:00"}

        mock_graph_store.get_memory_registry = AsyncMock(side_effect=get_registry)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                response = await client.get(
                    "/api/v1/memories?workspace_id=workspace-main&session_id=session-1&scope=task&scope_id=task-123&task_id=task-123&tags=launch&visibility=private"
                )

        assert response.status_code == 200
        assert [item["id"] for item in response.json()["memories"]] == ["mem-keep"]
        assert response.json()["total"] == 1
        assert response.json()["next_cursor"] is None
        assert response.json()["diagnostics"] == _expected_collection_diagnostics(
            applied_filters={
                "workspace_id": "workspace-main",
                "session_id": "session-1",
                "task_id": "task-123",
                "scope": "task",
                "scope_id": "task-123",
                "tags": ["launch"],
                "visibility": "private",
            },
            server_side_filtered=True,
        )

    @pytest.mark.asyncio
    async def test_list_memories_returns_next_cursor_for_pagination(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memories = AsyncMock(
            return_value=[
                SimpleNamespace(id="mem-1", content="First", metadata={"source": "manual"}),
                SimpleNamespace(id="mem-2", content="Second", metadata={"source": "manual"}),
                SimpleNamespace(id="mem-3", content="Third", metadata={"source": "manual"}),
            ]
        )

        async def get_registry(memory_id):
            mapping = {
                "mem-1": {"created_at": "2026-04-01T09:00:00"},
                "mem-2": {"created_at": "2026-04-02T09:00:00"},
                "mem-3": {"created_at": "2026-04-03T09:00:00"},
            }
            return mapping[memory_id]

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_registry = AsyncMock(side_effect=get_registry)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                response = await client.get("/api/v1/memories?limit=2&offset=0")
                cursor_response = await client.get("/api/v1/memories?limit=2&cursor=2")

        assert response.status_code == 200
        assert [item["id"] for item in response.json()["memories"]] == ["mem-3", "mem-2"]
        assert response.json()["next_cursor"] == "2"
        assert response.json()["diagnostics"]["truncated"] is True

        assert cursor_response.status_code == 200
        assert [item["id"] for item in cursor_response.json()["memories"]] == ["mem-1"]
        assert cursor_response.json()["offset"] == 2
        assert cursor_response.json()["next_cursor"] is None

    @pytest.mark.asyncio
    async def test_get_memory_not_found_returns_404(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            response = await client.get("/api/v1/memories/nonexistent")

        assert response.status_code == 404
        assert response.json() == {"detail": "Memory not found"}

    @pytest.mark.asyncio
    async def test_get_memory_context_returns_entities_and_communities(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=SimpleNamespace(
                id="mem-ctx",
                content="Context memory",
                metadata={"source": "manual"},
            )
        )

        mock_graph_store = MagicMock()
        mock_graph_store.get_memory_context = AsyncMock(
            return_value={
                "entities": [
                    {
                        "id": "ent-1",
                        "name": "Alice",
                        "type": "person",
                        "mention_text": "Alice built the rollout",
                        "confidence": 0.9,
                        "created_at": "2026-04-03T11:00:00+00:00",
                    }
                ],
                "communities": [
                    {
                        "id": "comm-1",
                        "title": "Rollout Cluster",
                        "level": 1,
                        "parent_id": None,
                        "summary": "Release and rollout notes",
                        "entity_count": 4,
                        "rank": 0.7,
                        "created_at": "2026-04-03T10:00:00+00:00",
                    }
                ],
            }
        )

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.memories.get_graph_store", return_value=mock_graph_store):
                response = await client.get("/api/v1/memories/mem-ctx/context")

        assert response.status_code == 200
        assert response.json() == {
            "memory_id": "mem-ctx",
            "entities": [
                {
                    "id": "ent-1",
                    "name": "Alice",
                    "type": "person",
                    "mention_text": "Alice built the rollout",
                    "confidence": 0.9,
                    "created_at": "2026-04-03T11:00:00+00:00",
                }
            ],
            "communities": [
                {
                    "id": "comm-1",
                    "title": "Rollout Cluster",
                    "level": 1,
                    "parent_id": None,
                    "summary": "Release and rollout notes",
                    "entity_count": 4,
                    "rank": 0.7,
                    "created_at": "2026-04-03T10:00:00+00:00",
                }
            ],
            "total_entities": 1,
            "total_communities": 1,
        }

    @pytest.mark.asyncio
    async def test_get_memory_context_returns_404_when_memory_missing(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            response = await client.get("/api/v1/memories/mem-missing/context")

        assert response.status_code == 404
        assert response.json() == {"detail": "Memory not found"}

    @pytest.mark.asyncio
    async def test_delete_memory_returns_deleted_payload(self, client):
        mock_service = MagicMock()
        mock_service.delete_memory = AsyncMock(
            return_value=SimpleNamespace(
                deleted=True,
                memory_id="mem-1",
                server_version=2,
                sync_status="deleted",
            )
        )

        with patch("src.api.routes.memories.get_memory_service", return_value=mock_service):
            response = await client.delete("/api/v1/memories/mem-1")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Memory deleted",
            "memory_id": "mem-1",
            "server_version": 2,
            "sync_status": "deleted",
        }

    @pytest.mark.asyncio
    async def test_delete_memory_returns_404_when_not_found(self, client):
        mock_service = MagicMock()
        mock_service.delete_memory = AsyncMock(
            return_value=SimpleNamespace(
                deleted=False,
                memory_id="mem-missing",
                server_version=None,
                sync_status="not_found",
            )
        )

        with patch("src.api.routes.memories.get_memory_service", return_value=mock_service):
            response = await client.delete("/api/v1/memories/mem-missing")

        assert response.status_code == 404
        assert response.json() == {"detail": "Memory not found"}

    @pytest.mark.asyncio
    async def test_archive_memory_updates_metadata(self, client):
        memory = SimpleNamespace(id="mem-1", content="Remember", metadata={"source": "manual", "title": "Memory One"})
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=memory)
        mock_vector_store.update_memory = AsyncMock(return_value=True)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            response = await client.post("/api/v1/memories/mem-1/archive")

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["memory_id"] == "mem-1"
        assert body["archived"] is True
        assert body["archived_at"]
        updated_metadata = mock_vector_store.update_memory.await_args.kwargs["metadata"]
        assert updated_metadata["archived"] is True
        assert updated_metadata["archived_at"]

    @pytest.mark.asyncio
    async def test_unarchive_memory_clears_archive_metadata(self, client):
        memory = SimpleNamespace(
            id="mem-1",
            content="Remember",
            metadata={"source": "manual", "archived": True, "archived_at": "2026-04-05T12:00:00"},
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=memory)
        mock_vector_store.update_memory = AsyncMock(return_value=True)

        with patch("src.api.routes.memories.get_vector_store", return_value=mock_vector_store):
            response = await client.post("/api/v1/memories/mem-1/unarchive")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "memory_id": "mem-1",
            "archived": False,
            "archived_at": None,
        }
        updated_metadata = mock_vector_store.update_memory.await_args.kwargs["metadata"]
        assert updated_metadata["archived"] is False
        assert "archived_at" not in updated_metadata
