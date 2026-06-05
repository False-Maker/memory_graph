"""Focused tests for /api/v1/data endpoints."""

from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDataEndpoint:
    """Test /api/v1/data endpoints."""

    @pytest.mark.asyncio
    async def test_import_data_accepts_json_file(self, client):
        with patch(
            "src.api.routes.data.batch_create_memories",
            new=AsyncMock(return_value={"success": True, "memory_ids": ["mem-1"], "count": 1}),
        ):
            response = await client.post(
                "/api/v1/data/import",
                files={
                    "file": (
                        "memories.json",
                        json.dumps(
                            {
                                "content": "Imported memory",
                                "metadata": {"source": "manual", "title": "Import"},
                            }
                        ),
                        "application/json",
                    )
                },
            )

        assert response.status_code == 200
        assert response.json() == {"success": True, "imported": 1}

    @pytest.mark.asyncio
    async def test_import_data_rejects_oversized_file(self, client, monkeypatch):
        from src.core.config import get_settings

        settings = get_settings()
        original_limit = settings.app.max_upload_bytes
        settings.app.max_upload_bytes = 5
        try:
            response = await client.post(
                "/api/v1/data/import",
                files={"file": ("memories.json", b'{"content":"too large"}', "application/json")},
            )
        finally:
            settings.app.max_upload_bytes = original_limit

        assert response.status_code == 413
        assert "too large" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_data_returns_memories_entities_and_relationships(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.get_memories = AsyncMock(
            return_value=[
                SimpleNamespace(id="mem-1", content="Remember this", metadata={"source": "manual"})
            ]
        )
        mock_graph_store = MagicMock()
        mock_graph_store.get_entities = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="entity-1",
                    name="Alice",
                    type="Person",
                    properties={"role": "engineer"},
                    source_text="Alice works here",
                )
            ]
        )
        mock_graph_store.get_relationships = AsyncMock(
            return_value=[
                SimpleNamespace(
                    id="rel-1",
                    source_id="entity-1",
                    target_id="entity-2",
                    type="WORKS_WITH",
                    properties={"weight": 1},
                )
            ]
        )

        with patch("src.api.routes.data.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.data.get_graph_store", return_value=mock_graph_store):
                response = await client.get("/api/v1/data/export")

        assert response.status_code == 200
        body = response.json()
        assert body["manifest"]["format"] == "memory_graph_export"
        assert body["manifest"]["version"] == 1
        assert body["manifest"]["exported_at"]
        assert body["manifest"]["counts"] == {
            "memories": 1,
            "entities": 1,
            "relationships": 1,
        }
        assert body == {
            "manifest": body["manifest"],
            "memories": [
                {
                    "id": "mem-1",
                    "content": "Remember this",
                    "metadata": {"source": "manual"},
                }
            ],
            "entities": [
                {
                    "id": "entity-1",
                    "name": "Alice",
                    "type": "Person",
                    "properties": {"role": "engineer"},
                    "source_text": "Alice works here",
                }
            ],
            "relationships": [
                {
                    "id": "rel-1",
                    "source_id": "entity-1",
                    "target_id": "entity-2",
                    "type": "WORKS_WITH",
                    "properties": {"weight": 1},
                }
            ],
        }

    @pytest.mark.asyncio
    async def test_clear_all_data_clears_vector_and_graph_store(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.clear_all = AsyncMock(return_value=True)
        mock_graph_store = MagicMock()
        mock_graph_store.clear_all = AsyncMock(return_value=True)

        with patch("src.api.routes.data.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.data.get_graph_store", return_value=mock_graph_store):
                response = await client.delete("/api/v1/data")

        assert response.status_code == 200
        assert response.json() == {"success": True, "message": "All data cleared"}
        mock_vector_store.clear_all.assert_awaited_once()
        mock_graph_store.clear_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reindex_without_reembed_uses_existing_embeddings(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.rebuild_index = AsyncMock(return_value=3)
        mock_vector_store.get_count = AsyncMock(return_value=3)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 3})

        with patch("src.api.routes.data.get_vector_store", return_value=mock_vector_store):
            response = await client.post("/api/v1/data/reindex")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "result": {"documents": 3, "reembedded": 0, "indexed": 3},
            "state": {"indexed_documents": 3},
        }
        mock_vector_store.rebuild_index.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reindex_with_reembed_uses_llm_embeddings(self, client):
        mock_vector_store = MagicMock()
        mock_vector_store.reembed_all = AsyncMock(
            return_value={"documents": 2, "reembedded": 2, "indexed": 2}
        )
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 2})
        mock_llm = MagicMock()
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

        with patch("src.api.routes.data.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.data.get_llm_manager", return_value=mock_llm):
                response = await client.post("/api/v1/data/reindex?reembed=true&batch_size=8")

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "result": {"documents": 2, "reembedded": 2, "indexed": 2},
            "state": {"indexed_documents": 2},
        }
        mock_vector_store.reembed_all.assert_awaited_once()
        kwargs = mock_vector_store.reembed_all.await_args.kwargs
        assert kwargs["embed_texts"] is mock_llm.embed
        assert kwargs["batch_size"] == 8

    @pytest.mark.asyncio
    async def test_restore_data_clears_then_restores_and_reindexes(self, client):
        export_payload = {
            "memories": [
                {"content": "Recovered memory 1", "metadata": {"source": "backup", "title": "One"}},
                {"content": "Recovered memory 2", "metadata": {"source": "backup", "title": "Two"}},
            ],
            "entities": [],
            "relationships": [],
        }

        mock_vector_store = MagicMock()
        mock_vector_store.clear_all = AsyncMock(return_value=True)
        mock_vector_store.rebuild_index = AsyncMock(return_value=2)
        mock_vector_store.get_count = AsyncMock(return_value=2)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 2})

        mock_graph_store = MagicMock()
        mock_graph_store.clear_all = AsyncMock(return_value=True)

        with patch("src.api.routes.data.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.data.get_graph_store", return_value=mock_graph_store):
                with patch(
                    "src.api.routes.data.batch_create_memories",
                    new=AsyncMock(return_value={"success": True, "memory_ids": ["mem-1", "mem-2"], "count": 2}),
                ):
                    response = await client.post(
                        "/api/v1/data/restore",
                        files={
                            "file": (
                                "export.json",
                                json.dumps(export_payload),
                                "application/json",
                            )
                        },
                    )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "restored": 2,
            "cleared_existing": True,
            "reindex": {"documents": 2, "reembedded": 0, "indexed": 2},
            "state": {"indexed_documents": 2},
        }
        mock_vector_store.clear_all.assert_awaited_once()
        mock_graph_store.clear_all.assert_awaited_once()
        mock_vector_store.rebuild_index.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_restore_data_skips_clear_and_reindex_when_disabled(self, client):
        export_payload = {
            "memories": [
                {"content": "Recovered memory", "metadata": {"source": "backup", "title": "One"}},
            ],
            "entities": [],
            "relationships": [],
        }

        mock_vector_store = MagicMock()
        mock_vector_store.clear_all = AsyncMock(return_value=True)
        mock_vector_store.rebuild_index = AsyncMock(return_value=1)
        mock_vector_store.get_count = AsyncMock(return_value=1)
        mock_vector_store.get_index_state = AsyncMock(return_value={"indexed_documents": 1})

        mock_graph_store = MagicMock()
        mock_graph_store.clear_all = AsyncMock(return_value=True)

        with patch("src.api.routes.data.get_vector_store", return_value=mock_vector_store):
            with patch("src.api.routes.data.get_graph_store", return_value=mock_graph_store):
                with patch(
                    "src.api.routes.data.batch_create_memories",
                    new=AsyncMock(return_value={"success": True, "memory_ids": ["mem-1"], "count": 1}),
                ):
                    response = await client.post(
                        "/api/v1/data/restore?clear_existing=false&reindex=false",
                        files={
                            "file": (
                                "export.json",
                                json.dumps(export_payload),
                                "application/json",
                            )
                        },
                    )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "restored": 1,
            "cleared_existing": False,
            "reindex": None,
            "state": None,
        }
        mock_vector_store.clear_all.assert_not_awaited()
        mock_graph_store.clear_all.assert_not_awaited()
        mock_vector_store.rebuild_index.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_restore_data_dry_run_validates_payload_without_mutations(self, client):
        export_payload = {
            "manifest": {
                "format": "memory_graph_export",
                "version": 1,
                "exported_at": "2026-04-02T12:00:00+00:00",
                "counts": {"memories": 1, "entities": 0, "relationships": 0},
            },
            "memories": [
                {"content": "Recovered memory", "metadata": {"source": "backup", "title": "One"}},
            ],
            "entities": [],
            "relationships": [],
        }

        with patch("src.api.routes.data.get_vector_store") as mock_get_vector_store:
            with patch("src.api.routes.data.get_graph_store") as mock_get_graph_store:
                with patch("src.api.routes.data.batch_create_memories") as mock_batch_create:
                    response = await client.post(
                        "/api/v1/data/restore?dry_run=true&clear_existing=true&reindex=true&reembed=true",
                        files={
                            "file": (
                                "export.json",
                                json.dumps(export_payload),
                                "application/json",
                            )
                        },
                    )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "dry_run": True,
            "validated": True,
            "preview": {"memories": 1, "entities": 0, "relationships": 0},
            "manifest": {
                "present": True,
                "version": 1,
                "exported_at": "2026-04-02T12:00:00+00:00",
                "counts": {"memories": 1, "entities": 0, "relationships": 0},
                "matches_payload": True,
            },
            "would_clear_existing": True,
            "would_reindex": True,
            "would_reembed": True,
        }
        mock_get_vector_store.assert_not_called()
        mock_get_graph_store.assert_not_called()
        mock_batch_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_restore_data_rejects_payload_without_memories_list(self, client):
        response = await client.post(
            "/api/v1/data/restore",
            files={
                "file": (
                    "broken-export.json",
                    json.dumps({"items": []}),
                    "application/json",
                )
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid restore payload: expected 'memories' list"}

    @pytest.mark.asyncio
    async def test_restore_data_rejects_manifest_count_mismatch(self, client):
        response = await client.post(
            "/api/v1/data/restore?dry_run=true",
            files={
                "file": (
                    "broken-export.json",
                    json.dumps(
                        {
                            "manifest": {"counts": {"memories": 2}},
                            "memories": [{"content": "only one"}],
                            "entities": [],
                            "relationships": [],
                        }
                    ),
                    "application/json",
                )
            },
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Restore manifest count mismatch: memories: expected 2, got 1"
        }

    @pytest.mark.asyncio
    async def test_batch_create_memories(self, client):
        mock_service = MagicMock()
        mock_service.ingest_memory = AsyncMock(
            side_effect=[
                SimpleNamespace(memory_id="mem-1"),
                SimpleNamespace(memory_id="mem-2"),
            ]
        )

        with patch("src.api.routes.data.get_memory_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/data/memories/batch",
                json=[
                    {"content": "Memory one", "metadata": {"source": "import", "title": "One"}},
                    {"content": "Memory two", "metadata": {"source": "import", "title": "Two"}},
                ],
            )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "memory_ids": ["mem-1", "mem-2"],
            "count": 2,
        }
        assert mock_service.ingest_memory.await_count == 2

    @pytest.mark.asyncio
    async def test_get_import_formats(self, client):
        response = await client.get("/api/v1/data/import/formats")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["formats"]) >= 4

    @pytest.mark.asyncio
    async def test_import_conversations_file(self, client):
        fake_conversation = SimpleNamespace(
            platform=SimpleNamespace(value="claude"),
            title="Imported Chat",
            messages=[
                {"role": "user", "content": "Alice Johnson is coordinating the rollout with OpenAI."},
                {"role": "assistant", "content": "OpenAI confirmed Alice Johnson owns the migration."},
            ],
            created_at=datetime.fromisoformat("2026-03-31T10:00:00"),
            metadata={"conversation_id": "conv-1"},
            to_memory_content=lambda: "# Imported Chat\n\nHello",
            to_plain_text=lambda: "[USER] Hello",
        )
        mock_detector = MagicMock()
        mock_detector.parse_file.return_value = ([fake_conversation], "claude")
        mock_service = MagicMock()
        mock_service.ingest_memory = AsyncMock(return_value=SimpleNamespace(memory_id="mem-1"))

        with patch("src.api.routes.data.get_detector", return_value=mock_detector):
            with patch("src.api.routes.data.get_memory_service", return_value=mock_service):
                response = await client.post(
                    "/api/v1/data/import/conversations",
                    files={"file": ("claude.json", b"{}", "application/json")},
                    data={"output_format": "markdown"},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["imported_memories"] == 1
        assert body["failed_count"] == 0
        assert body["platform"] == "claude"
        assert body["parsed_conversations"][0]["conversation_id"] == "conv-1"
        assert body["parsed_conversations"][0]["title"] == "Imported Chat"
        ingest_call = mock_service.ingest_memory.await_args.kwargs
        regex_entity_texts = {item["text"] for item in ingest_call["metadata"]["regex_entity_hints"]}
        assert "OpenAI" in regex_entity_texts
        assert "Alice Johnson" in regex_entity_texts

    @pytest.mark.asyncio
    async def test_import_conversations_file_returns_400_on_parse_error(self, client):
        from src.core.parsers.base import ParseError

        mock_detector = MagicMock()
        mock_detector.parse_file.side_effect = ParseError("bad export")

        with patch("src.api.routes.data.get_detector", return_value=mock_detector):
            response = await client.post(
                "/api/v1/data/import/conversations",
                files={"file": ("broken.json", b"{}", "application/json")},
                data={"output_format": "markdown"},
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "Failed to parse conversation: bad export"}

    @pytest.mark.asyncio
    async def test_import_conversations_file_supports_claude_code_jsonl(self, client):
        fixture_path = Path(__file__).parent / "fixtures" / "phase1_import" / "claude_code_session.jsonl"
        mock_service = MagicMock()
        mock_service.ingest_memory = AsyncMock(return_value=SimpleNamespace(memory_id="mem-claude-code"))

        with patch("src.api.routes.data.get_memory_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/data/import/conversations",
                files={"file": (fixture_path.name, fixture_path.read_bytes(), "application/json")},
                data={"output_format": "markdown"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["imported_memories"] == 1
        assert body["platform"] == "claude_code"
        assert body["parsed_conversations"][0]["conversation_id"] == "claude_code_session"
        assert body["parsed_conversations"][0]["message_count"] == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("fixture_name", "expected_platform", "expected_title"),
        [
            ("chatgpt_export.json", "chatgpt", "ChatGPT Sample Export"),
            ("chatgpt_export_collection.json", "chatgpt", "ChatGPT Collection Variant"),
            ("claude_export.json", "claude", "Claude Sample Export"),
            ("claude_chat_variant.json", "claude", "Claude Chat Variant"),
            ("claude_code_session.jsonl", "claude_code", "Claude Code Session claude_code_session"),
            ("claude_code_session_variant.jsonl", "claude_code", "Claude Code Session claude_code_session_variant"),
            ("slack_export.json", "slack", "Slack Conversation slack_export"),
            ("slack_thread_variant.json", "slack", "Slack Conversation slack_thread_variant"),
            ("codex_export.json", "codex", "Codex Session codex_export"),
            ("codex_export_variant.json", "codex", "Codex Session codex_export_variant"),
        ],
    )
    async def test_import_conversations_file_supports_phase1_sample_exports(
        self,
        client,
        phase1_import_fixture_dir,
        fixture_name,
        expected_platform,
        expected_title,
    ):
        fixture_path = Path(phase1_import_fixture_dir) / fixture_name
        mock_service = MagicMock()
        mock_service.ingest_memory = AsyncMock(return_value=SimpleNamespace(memory_id=f"mem-{expected_platform}"))

        with patch("src.api.routes.data.get_memory_service", return_value=mock_service):
            response = await client.post(
                "/api/v1/data/import/conversations",
                files={"file": (fixture_path.name, fixture_path.read_bytes(), "application/json")},
                data={"output_format": "markdown"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["imported_memories"] == 1
        assert body["failed_count"] == 0
        assert body["platform"] == expected_platform
        assert body["parsed_conversations"][0]["title"] == expected_title
        assert body["parsed_conversations"][0]["message_count"] == 2
        mock_service.ingest_memory.assert_awaited_once()
        ingest_call = mock_service.ingest_memory.await_args.kwargs
        assert ingest_call["source_system"] == expected_platform
        assert ingest_call["metadata"]["title"] == expected_title

    @pytest.mark.asyncio
    async def test_import_conversations_json(self, client):
        fake_conversation = SimpleNamespace(
            platform=SimpleNamespace(value="chatgpt"),
            title="JSON Import",
            messages=[{"role": "user"}],
            created_at=datetime.fromisoformat("2026-03-31T11:00:00"),
            metadata={"conversation_id": "conv-json"},
            to_memory_content=lambda: "# JSON Import\n\nHi",
            to_plain_text=lambda: "[USER] Hi",
        )
        mock_detector = MagicMock()
        mock_detector.detect_and_parse.return_value = ([fake_conversation], "chatgpt")
        mock_service = MagicMock()
        mock_service.ingest_memory = AsyncMock(return_value=SimpleNamespace(memory_id="mem-json"))

        with patch("src.api.routes.data.get_detector", return_value=mock_detector):
            with patch("src.api.routes.data.get_memory_service", return_value=mock_service):
                response = await client.post(
                    "/api/v1/data/import/conversations/json",
                    json={
                        "content": json.dumps({"messages": [{"role": "user", "content": "Hi"}]}),
                        "output_format": "plain_text",
                    },
                )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["imported_memories"] == 1
        assert body["platform"] == "chatgpt"
        assert body["parsed_conversations"][0]["conversation_id"] == "conv-json"

    @pytest.mark.asyncio
    async def test_import_conversations_json_returns_400_when_no_conversations_found(self, client):
        mock_detector = MagicMock()
        mock_detector.detect_and_parse.return_value = ([], "unknown")

        with patch("src.api.routes.data.get_detector", return_value=mock_detector):
            response = await client.post(
                "/api/v1/data/import/conversations/json",
                json={"content": "[]", "output_format": "markdown"},
            )

        assert response.status_code == 400
        assert response.json() == {"detail": "No valid conversations found"}
