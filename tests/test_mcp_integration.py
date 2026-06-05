"""Focused real-stack integration coverage for the MCP server."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip(
    "mcp.server.fastmcp",
    reason="Install mcp>=1.27,<2 before running MCP integration tests.",
)

from src.core.config import Settings
from src.core.models.community import Community
from src.core.query_trace import QueryTraceStore
from src.core.temporal_kg import TemporalKnowledgeGraph
from src.mcp.server import create_mcp_server


class TestMCPIntegration:
    @pytest.mark.asyncio
    async def test_mcp_server_tools_work_against_real_graph_vector_temporal_state(self, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult
        from src.core.graph_store import GraphStore
        from src.core.graph_store_models import GraphEntity
        from src.core.memory_service import MemoryService
        from src.core.vector_store import VectorStore
        from src.mcp.service import MemoryGraphMCPService

        runtime_settings = Settings(
            llm={"provider": "openai"},
            embedding={
                "model": "integration-test-embedding",
                "dimensions": 3,
                "cloud_dimensions": 3,
            },
            database={
                "vector": {
                    "type": "faiss",
                    "faiss": {"persist_directory": str(tmp_path / "faiss-mcp")},
                }
            },
            storage={"data_dir": str(tmp_path / "data")},
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            settings = runtime_settings

            async def embed(self, texts):
                vectors = []
                for text in texts:
                    normalized = text.lower()
                    if "alice" in normalized or "launch" in normalized:
                        vectors.append([1.0, 0.0, 0.0])
                    elif "roadmap" in normalized:
                        vectors.append([0.8, 0.2, 0.0])
                    else:
                        vectors.append([0.0, 1.0, 0.0])
                return vectors

            async def generate_answer(self, context, question):
                return f"MCP answer for '{question}': {context.splitlines()[0]}"

        fake_llm = FakeLLM()
        extracted_entity = Entity(
            id="raw-entity-alice",
            name="Alice",
            type="person",
            properties={"role": "owner"},
            source_text="Alice owns the launch checklist and roadmap.",
            confidence=0.95,
            created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
        )

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.temporal_kg.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            temporal_kg = TemporalKnowledgeGraph(db_path=graph_store._db_path)
            query_trace_store = QueryTraceStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=[extracted_entity],
                    relationships=[],
                    facts=["Alice owns the launch checklist and roadmap."],
                    summary="Launch ownership note",
                )
            )

            ingest_result = await memory_service.ingest_memory(
                "Alice owns the launch checklist and roadmap.",
                metadata={
                    "source": "manual",
                    "title": "Launch ownership note",
                    "tags": ["mcp", "integration"],
                },
            )
            memory_id = ingest_result.memory_id

            entities = await graph_store.get_entities(limit=10)
            assert len(entities) == 1
            entity_id = entities[0].id

            community = Community(
                id="comm-mcp",
                level=1,
                parent_id=None,
                entity_ids=[entity_id],
                summary="Alice launch planning cluster",
                title="Launch Cluster",
                rank=0.97,
            )
            await graph_store.create_community(community)
            await graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=[entity_id],
            )

            timeline_entity_id = "entity-timeline-mcp"
            await graph_store.create_entity(
                GraphEntity(
                    id=timeline_entity_id,
                    name="Launch Timeline",
                    type="project",
                    properties={"surface": "mcp"},
                    source_text="Launch timeline integration entity.",
                    confidence=0.9,
                    created_at=datetime(2026, 4, 15, tzinfo=timezone.utc),
                )
            )

            await temporal_kg.upsert_triple(
                triple_id="triple-mcp",
                entity_id=timeline_entity_id,
                relation_type="owns",
                target_entity_id=None,
                valid_from="2026-04-01",
                source="integration",
                metadata={"surface": "mcp"},
            )

            assert len(await temporal_kg.get_entity_timeline(timeline_entity_id)) == 1

            query_trace_store.start_run(
                run_id="qrun-mcp",
                question="Who owns the launch checklist?",
                strategy="vector",
                session_id="session-mcp",
            )
            query_trace_store.complete_success(
                "qrun-mcp",
                llm_provider="openai",
                llm_model="integration-test",
                processing_time_ms=12,
                source_hit_count=1,
                community_hit_count=1,
                entities_count=1,
            )

            service = MemoryGraphMCPService(
                llm_manager_getter=lambda: fake_llm,
                vector_store_getter=lambda: vector_store,
                graph_store_getter=lambda: graph_store,
                memory_service_getter=lambda: memory_service,
                query_trace_store_getter=lambda: query_trace_store,
                temporal_kg_getter=lambda: temporal_kg,
            )
            server = create_mcp_server(service=service)

            _content, answer_payload = await server.call_tool(
                "answer_question",
                {
                    "question": "Who owns the launch checklist?",
                    "strategy": "vector",
                    "top_k": 3,
                },
            )
            assert answer_payload["answer"].startswith("MCP answer for 'Who owns the launch checklist?'")
            assert answer_payload["total_sources"] >= 1

            _content, search_payload = await server.call_tool(
                "search_memories",
                {
                    "query": "launch checklist",
                    "backend": "standard",
                    "strategy": "vector",
                    "top_k": 3,
                },
            )
            assert search_payload["total_sources"] >= 1
            assert search_payload["sources"][0]["memory_id"] == memory_id

            _content, memory_payload = await server.call_tool("get_memory", {"memory_id": memory_id})
            assert memory_payload["id"] == memory_id
            assert memory_payload["metadata"]["title"] == "Launch ownership note"

            _content, entities_payload = await server.call_tool("list_entities", {"limit": 10})
            assert entities_payload["total"] >= 1
            assert entities_payload["entities"][0]["name"] == "Alice"

            _content, community_payload = await server.call_tool("get_community", {"community_id": "comm-mcp"})
            assert community_payload["title"] == "Launch Cluster"

            _content, query_runs_payload = await server.call_tool("list_query_runs", {"limit": 5})
            assert query_runs_payload["runs"][0]["run_id"] == "qrun-mcp"

            _content, timeline_payload = await server.call_tool(
                "get_entity_timeline",
                {"entity_id": timeline_entity_id},
            )
            assert timeline_payload["total"] == 1
            assert timeline_payload["triples"][0]["relation_type"] == "owns"

            _content, saved_payload = await server.call_tool(
                "save_memory",
                {
                    "content": "Bob archived the retrospective note.",
                    "metadata": {"source": "manual", "title": "Retrospective note", "tags": ["mcp", "write"]},
                    "source_system": "manual",
                },
            )
            saved_memory_id = saved_payload["memory_id"]
            assert saved_payload["result"] in {"created", "updated", "restored"}
            assert saved_payload["memory"]["metadata"]["title"] == "Retrospective note"

            _content, archived_payload = await server.call_tool(
                "archive_memory",
                {"memory_id": saved_memory_id},
            )
            assert archived_payload["archived"] is True

            _content, unarchived_payload = await server.call_tool(
                "unarchive_memory",
                {"memory_id": saved_memory_id},
            )
            assert unarchived_payload["archived"] is False

            stats_resource = await server.read_resource("memory-graph://stats")
            assert len(stats_resource) == 1
            assert '"total_entities"' in stats_resource[0].content

            query_runs_resource = await server.read_resource("memory-graph://query-runs/recent")
            assert len(query_runs_resource) == 1
            assert '"qrun-mcp"' in query_runs_resource[0].content

            _content, deleted_payload = await server.call_tool(
                "delete_memory",
                {"memory_id": saved_memory_id},
            )
            assert deleted_payload["deleted"] is True

            temporal_kg.close()
            await graph_store.close()
            await vector_store.close()
