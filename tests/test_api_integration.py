"""Focused integration tests for the default Web API stack."""

from contextlib import ExitStack
from datetime import datetime
import json
from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import Settings


class TestApiIntegration:
    """Focused API integration coverage for the default Web stack."""

    @pytest.mark.asyncio
    async def test_memory_ingest_graph_vector_query_integration(self, client, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult
        from src.core.graph_store import GraphStore
        from src.core.memory_service import MemoryService
        from src.core.vector_store import VectorStore

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
                    "faiss": {"persist_directory": str(tmp_path / "faiss")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                vectors = []
                for text in texts:
                    normalized = text.lower()
                    if "alice" in normalized:
                        vectors.append([1.0, 0.0, 0.0])
                    elif "memory graph" in normalized:
                        vectors.append([0.8, 0.2, 0.0])
                    else:
                        vectors.append([0.0, 1.0, 0.0])
                return vectors

            async def generate_answer(self, context, question):
                return f"Integrated answer for '{question}': {context.splitlines()[0]}"

        fake_llm = FakeLLM()
        extracted_entity = Entity(
            id="raw-entity-alice",
            name="Alice",
            type="person",
            properties={"role": "engineer"},
            source_text="Alice built Memory Graph integration tests.",
            confidence=0.95,
            created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
        )

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=[extracted_entity],
                    relationships=[],
                    facts=["Alice built Memory Graph integration tests."],
                    summary="Alice integration note",
                )
            )

            stack.enter_context(
                patch("src.api.routes.memories.get_memory_service", return_value=memory_service)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch("src.api.routes.graph.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_llm_manager", return_value=fake_llm)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_graph_store", return_value=graph_store)
            )

            create_response = await client.post(
                "/api/v1/memories",
                json={
                    "content": "Alice built Memory Graph integration tests.",
                    "metadata": {
                        "source": "manual",
                        "title": "Integration note",
                        "tags": ["integration", "api"],
                    },
                },
            )
            assert create_response.status_code == 200
            created = create_response.json()
            memory_id = created["memory_id"]
            assert created["entities_count"] == 1
            assert created["relationships_count"] == 0

            memories_response = await client.get("/api/v1/memories?limit=10&offset=0")
            assert memories_response.status_code == 200
            memories_payload = memories_response.json()
            assert memories_payload["total"] == 1
            assert memories_payload["memories"][0]["id"] == memory_id
            assert memories_payload["memories"][0]["metadata"]["tags"] == ["integration", "api"]

            entities_response = await client.get("/api/v1/graph/entities")
            assert entities_response.status_code == 200
            entities_payload = entities_response.json()
            assert entities_payload["total"] == 1
            assert entities_payload["entities"][0]["name"] == "Alice"
            assert entities_payload["entities"][0]["type"] == "person"

            query_response = await client.post(
                "/api/v1/query",
                json={"question": "What did Alice build?", "strategy": "vector"},
            )
            assert query_response.status_code == 200
            query_payload = query_response.json()
            assert query_payload["sources"][0]["memory_id"] == memory_id
            assert "Alice built Memory Graph integration tests." in query_payload["sources"][0]["content"]
            assert "What did Alice build?" in query_payload["answer"]

            await graph_store.close()
            await vector_store.close()

    @pytest.mark.asyncio
    async def test_memory_ingest_list_delete_integration(self, client, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult
        from src.core.graph_store import GraphStore
        from src.core.memory_service import MemoryService
        from src.core.vector_store import VectorStore

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
                    "faiss": {"persist_directory": str(tmp_path / "faiss-delete")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                return [[1.0, 0.0, 0.0] for _ in texts]

        fake_llm = FakeLLM()
        extracted_entity = Entity(
            id="raw-entity-delete",
            name="Delete Flow",
            type="concept",
            properties={"role": "regression"},
            source_text="Delete flow integration coverage.",
            confidence=0.95,
            created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
        )

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=[extracted_entity],
                    relationships=[],
                    facts=["Delete flow integration coverage."],
                    summary="Delete integration note",
                )
            )

            stack.enter_context(
                patch("src.api.routes.memories.get_memory_service", return_value=memory_service)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_graph_store", return_value=graph_store)
            )

            create_response = await client.post(
                "/api/v1/memories",
                json={
                    "content": "Delete flow integration coverage.",
                    "metadata": {
                        "source": "manual",
                        "title": "Delete integration note",
                        "tags": ["integration", "delete"],
                    },
                },
            )
            assert create_response.status_code == 200
            memory_id = create_response.json()["memory_id"]

            memories_response = await client.get("/api/v1/memories?limit=10&offset=0")
            assert memories_response.status_code == 200
            assert memories_response.json()["total"] == 1

            delete_response = await client.delete(f"/api/v1/memories/{memory_id}")
            assert delete_response.status_code == 200
            assert delete_response.json()["success"] is True
            assert delete_response.json()["memory_id"] == memory_id
            assert delete_response.json()["sync_status"] == "deleted"

            deleted_memory_response = await client.get(f"/api/v1/memories/{memory_id}")
            assert deleted_memory_response.status_code == 404

            memories_after_delete = await client.get("/api/v1/memories?limit=10&offset=0")
            assert memories_after_delete.status_code == 200
            assert memories_after_delete.json()["total"] == 0
            assert memories_after_delete.json()["memories"] == []

            registry_row = await graph_store.get_memory_registry(memory_id)
            sync_state = await graph_store.get_memory_sync_state(memory_id)
            assert registry_row is not None
            assert registry_row["deleted_at"] is not None
            assert sync_state["sync_status"] == "deleted"
            assert await vector_store.get_memory(memory_id) is None

            await graph_store.close()
            await vector_store.close()

    @pytest.mark.asyncio
    async def test_memory_ingest_and_graphrag_query_integration(self, client, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult
        from src.core.graph_store import GraphStore
        from src.core.memory_service import MemoryService
        from src.core.models.community import Community
        from src.core.vector_store import VectorStore

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
                    "faiss": {"persist_directory": str(tmp_path / "faiss-graphrag")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                vectors = []
                for text in texts:
                    normalized = text.lower()
                    if "alice" in normalized or "integration community" in normalized:
                        vectors.append([1.0, 0.0, 0.0])
                    elif "memory graph" in normalized:
                        vectors.append([0.8, 0.2, 0.0])
                    else:
                        vectors.append([0.0, 1.0, 0.0])
                return vectors

            async def generate_answer(self, context, question):
                return f"GraphRAG answer for '{question}': {context.splitlines()[0]}"

        fake_llm = FakeLLM()
        extracted_entity = Entity(
            id="raw-entity-alice",
            name="Alice",
            type="person",
            properties={"role": "engineer"},
            source_text="Alice built Memory Graph integration tests.",
            confidence=0.95,
            created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
        )

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=[extracted_entity],
                    relationships=[],
                    facts=["Alice built Memory Graph integration tests."],
                    summary="Alice integration note",
                )
            )

            stack.enter_context(
                patch("src.api.routes.memories.get_memory_service", return_value=memory_service)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch("src.api.routes.graph.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_llm_manager", return_value=fake_llm)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_graph_store", return_value=graph_store)
            )

            create_response = await client.post(
                "/api/v1/memories",
                json={
                    "content": "Alice built Memory Graph integration tests.",
                    "metadata": {
                        "source": "manual",
                        "title": "GraphRAG integration note",
                        "tags": ["integration", "graphrag"],
                    },
                },
            )
            assert create_response.status_code == 200
            memory_id = create_response.json()["memory_id"]

            entities = await graph_store.get_entities(limit=10)
            assert len(entities) == 1
            entity_id = entities[0].id

            community = Community(
                id="comm-integration",
                level=0,
                parent_id=None,
                entity_ids=[entity_id],
                summary="Alice integration community",
                title="Alice Community",
                rank=0.95,
            )
            await graph_store.create_community(community)
            await graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=[entity_id],
            )

            query_response = await client.post(
                "/api/v1/query",
                json={
                    "question": "Which community mentions Alice?",
                    "strategy": "graphrag",
                    "retrieval_mode": "global",
                    "top_k": 3,
                    "include_sources": True,
                },
            )

            assert query_response.status_code == 200
            query_payload = query_response.json()
            assert query_payload["answer"].startswith("GraphRAG answer for 'Which community mentions Alice?'")
            assert query_payload["entities"] == []
            assert query_payload["communities"][0]["community_id"] == "comm-integration"
            assert query_payload["communities"][0]["title"] == "Alice Community"
            assert query_payload["communities"][0]["summary"] == "Alice integration community"
            assert entity_id in query_payload["communities"][0]["entities"]
            assert query_payload["sources"][0]["memory_id"] == memory_id
            assert query_payload["sources"][0]["community_id"] == "comm-integration"
            assert query_payload["sources"][0]["community_summary"] == "Alice integration community"
            assert "Alice built Memory Graph integration tests." in query_payload["sources"][0]["content"]
            assert query_payload["processing_time_ms"] > 0

            await graph_store.close()
            await vector_store.close()

    @pytest.mark.asyncio
    async def test_memory_ingest_and_local_graphrag_query_integration(self, client, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult
        from src.core.graph_store import GraphStore
        from src.core.memory_service import MemoryService
        from src.core.models.community import Community
        from src.core.vector_store import VectorStore

        runtime_settings = Settings(
            llm={"provider": "ollama"},
            embedding={
                "model": "integration-test-embedding",
                "dimensions": 4,
                "cloud_dimensions": 4,
                "provider_preference": "remote_only",
            },
            database={
                "vector": {
                    "type": "faiss",
                    "faiss": {"persist_directory": str(tmp_path / "faiss-graphrag-local")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

            async def generate(self, prompt, temperature=0.7, max_tokens=None):
                if "Output Format (JSON)" in prompt:
                    return json.dumps(
                        {
                            "entities": [
                                {
                                    "id": "raw-alice",
                                    "name": "Alice",
                                    "type": "person",
                                    "properties": {"role": "owner"},
                                    "confidence": 0.98,
                                }
                            ],
                            "relationships": [],
                            "facts": ["Alice owns the launch checklist."],
                            "summary": "Launch ownership context",
                        }
                    )
                return "Alice owns the launch checklist and release coordination."

            async def generate_answer(self, context, question):
                return f"Local GraphRAG answer for '{question}': {context.splitlines()[0]}"

        fake_llm = FakeLLM()
        extracted_entity = Entity(
            id="raw-alice",
            name="Alice",
            type="person",
            properties={"role": "owner"},
            source_text="Alice owns the launch checklist and release coordination.",
            confidence=0.98,
            created_at=datetime.fromisoformat("2026-04-08T09:00:00"),
        )

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=[extracted_entity],
                    relationships=[],
                    facts=["Alice owns the launch checklist."],
                    summary="Launch ownership note",
                )
            )

            stack.enter_context(
                patch("src.api.routes.memories.get_memory_service", return_value=memory_service)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_llm_manager", return_value=fake_llm)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_graph_store", return_value=graph_store)
            )

            create_response = await client.post(
                "/api/v1/memories",
                json={
                    "content": "Alice owns the launch checklist and release coordination.",
                    "metadata": {
                        "source": "manual",
                        "title": "Launch ownership note",
                        "tags": ["integration", "local-graphrag"],
                    },
                },
            )
            assert create_response.status_code == 200
            memory_id = create_response.json()["memory_id"]

            entities = await graph_store.get_entities(limit=10)
            entity_id = entities[0].id
            community = Community(
                id="comm-launch-owners",
                level=1,
                parent_id=None,
                entity_ids=[entity_id],
                summary="Alice owns the launch checklist and release coordination.",
                title="Launch Owners",
                rank=0.97,
            )
            await graph_store.create_community(community)
            await graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=[entity_id],
            )

            query_response = await client.post(
                "/api/v1/query",
                json={
                    "question": "Who owns the launch checklist?",
                    "strategy": "graphrag",
                    "retrieval_mode": "local",
                    "top_k": 5,
                    "include_sources": True,
                },
            )

            assert query_response.status_code == 200
            query_payload = query_response.json()
            assert query_payload["answer"].startswith("Local GraphRAG answer for 'Who owns the launch checklist?'")
            assert query_payload["entities"] == ["Alice"]
            assert query_payload["communities"][0]["community_id"] == "comm-launch-owners"
            assert query_payload["sources"][0]["memory_id"] == memory_id
            assert query_payload["sources"][0]["community_id"] == "comm-launch-owners"
            assert "Alice owns the launch checklist" in query_payload["sources"][0]["content"]

            await graph_store.close()
            await vector_store.close()

    @pytest.mark.asyncio
    async def test_global_graphrag_query_returns_null_memory_id_when_source_has_no_memory_mapping(self, client, tmp_path):
        from src.core.graph_store import GraphStore
        from src.core.graph_store_models import GraphEntity
        from src.core.models.community import Community
        from src.core.vector_store import VectorStore

        runtime_settings = Settings(
            llm={"provider": "ollama"},
            embedding={
                "model": "integration-test-embedding",
                "dimensions": 4,
                "cloud_dimensions": 4,
                "provider_preference": "remote_only",
            },
            database={
                "vector": {
                    "type": "faiss",
                    "faiss": {"persist_directory": str(tmp_path / "faiss-graphrag-missing-memory-id")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

            async def generate_answer(self, context, question):
                return f"GraphRAG answer for '{question}': {context.splitlines()[0]}"

        fake_llm = FakeLLM()
        created_at = datetime.fromisoformat("2026-04-08T09:00:00")

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()

            stack.enter_context(
                patch("src.api.routes.query.get_llm_manager", return_value=fake_llm)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.query.get_graph_store", return_value=graph_store)
            )

            orphan_entity_ids = []
            for entity_id, name, entity_type in [
                ("entity-orphan-alice", "Alice", "person"),
                ("entity-orphan-launch-checklist", "Launch Checklist", "document"),
            ]:
                await graph_store.create_entity(
                    GraphEntity(
                        id=entity_id,
                        name=name,
                        type=entity_type,
                        properties={},
                        source_text="Alice owns the launch checklist through community-only evidence without a direct memory record.",
                        confidence=0.95,
                        created_at=created_at,
                    )
                )
                orphan_entity_ids.append(entity_id)

            community = Community(
                id="comm-missing-memory-id",
                level=1,
                parent_id=None,
                entity_ids=orphan_entity_ids,
                summary="Alice owns the launch checklist, but this community currently has no direct memory mapping.",
                title="Launch Owners Without Memory",
                rank=0.95,
            )
            await graph_store.create_community(community)
            await graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=orphan_entity_ids,
            )
            await graph_store.refresh_community_entity_count(community.id)

            query_response = await client.post(
                "/api/v1/query",
                json={
                    "question": "Who owns the launch checklist?",
                    "strategy": "graphrag",
                    "retrieval_mode": "global",
                    "top_k": 3,
                    "include_sources": True,
                },
            )

            assert query_response.status_code == 200
            query_payload = query_response.json()
            assert query_payload["answer"].startswith("GraphRAG answer for 'Who owns the launch checklist?'")
            assert query_payload["communities"][0]["community_id"] == "comm-missing-memory-id"
            assert query_payload["sources"][0]["memory_id"] is None
            assert query_payload["sources"][0]["community_id"] == "comm-missing-memory-id"
            assert "community-only evidence without a direct memory record" in query_payload["sources"][0]["content"]

            await graph_store.close()
            await vector_store.close()

    @pytest.mark.asyncio
    async def test_memory_context_and_community_detail_integration(self, client, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult, Relationship
        from src.core.graph_store import GraphStore
        from src.core.hierarchy import HierarchyBuilder
        from src.core.memory_service import MemoryService
        from src.core.models.community import Community
        from src.core.vector_store import VectorStore

        runtime_settings = Settings(
            llm={"provider": "ollama"},
            embedding={
                "model": "integration-test-embedding",
                "dimensions": 4,
                "cloud_dimensions": 4,
                "provider_preference": "remote_only",
            },
            database={
                "vector": {
                    "type": "faiss",
                    "faiss": {"persist_directory": str(tmp_path / "faiss-memory-community-detail")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

        fake_llm = FakeLLM()
        created_at = datetime.fromisoformat("2026-04-08T09:00:00")
        extracted_entities = [
            Entity(
                id="raw-alice",
                name="Alice",
                type="person",
                properties={"role": "owner"},
                source_text="Alice owns the launch checklist and release coordination.",
                confidence=0.97,
                created_at=created_at,
            ),
            Entity(
                id="raw-launch-checklist",
                name="Launch Checklist",
                type="document",
                properties={"status": "active"},
                source_text="Alice owns the launch checklist and release coordination.",
                confidence=0.95,
                created_at=created_at,
            ),
        ]

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.hierarchy.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=extracted_entities,
                    relationships=[
                        Relationship(
                            id="raw-rel-ownership",
                            source_id="raw-alice",
                            target_id="raw-launch-checklist",
                            type="owns",
                            properties={"scope": "release"},
                            confidence=0.96,
                            created_at=created_at,
                        )
                    ],
                    facts=["Alice owns the launch checklist."],
                    summary="Launch ownership note",
                )
            )

            stack.enter_context(
                patch("src.api.routes.memories.get_memory_service", return_value=memory_service)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch("src.api.routes.communities.get_graph_store", return_value=graph_store)
            )
            stack.enter_context(
                patch(
                    "src.api.routes.communities.HierarchyBuilder",
                    side_effect=lambda: HierarchyBuilder(graph_store),
                )
            )

            create_response = await client.post(
                "/api/v1/memories",
                json={
                    "content": "Alice owns the launch checklist and release coordination.",
                    "metadata": {
                        "source": "manual",
                        "title": "Launch ownership note",
                        "tags": ["integration", "memory-community-detail"],
                    },
                },
            )
            assert create_response.status_code == 200
            memory_id = create_response.json()["memory_id"]

            entities = await graph_store.get_entities(limit=10)
            entity_ids = [entity.id for entity in entities]
            community = Community(
                id="comm-launch-owners",
                level=1,
                parent_id=None,
                entity_ids=entity_ids,
                summary="Alice owns the launch checklist and release coordination.",
                title="Launch Owners",
                rank=0.97,
            )
            await graph_store.create_community(community)
            await graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=entity_ids,
            )
            await graph_store.refresh_community_entity_count(community.id)

            memory_context = await client.get(f"/api/v1/memories/{memory_id}/context")
            assert memory_context.status_code == 200
            assert memory_context.json()["total_entities"] == 2
            assert memory_context.json()["total_communities"] == 1
            assert memory_context.json()["communities"][0]["id"] == "comm-launch-owners"

            community_entities = await client.get("/api/v1/communities/comm-launch-owners/entities?limit=20")
            assert community_entities.status_code == 200
            assert community_entities.json()["total"] == 2
            assert {item["name"] for item in community_entities.json()["entities"]} == {"Alice", "Launch Checklist"}

            community_relationships = await client.get("/api/v1/communities/comm-launch-owners/relationships?limit=20")
            assert community_relationships.status_code == 200
            assert community_relationships.json()["total"] == 1
            assert community_relationships.json()["relationships"][0]["type"] == "owns"

            community_ancestors = await client.get("/api/v1/communities/comm-launch-owners/ancestors")
            community_descendants = await client.get("/api/v1/communities/comm-launch-owners/descendants")
            assert community_ancestors.status_code == 200
            assert community_descendants.status_code == 200
            assert community_ancestors.json()["total"] == 0
            assert community_descendants.json()["total"] == 0

            await graph_store.close()
            await vector_store.close()

    @pytest.mark.asyncio
    async def test_community_summary_route_integration(self, client, tmp_path):
        from src.core.entity_extractor import Entity, ExtractionResult
        from src.core.graph_store import GraphStore
        from src.core.graph_store_models import GraphEntity
        from src.core.hierarchy import HierarchyBuilder
        from src.core.memory_service import MemoryService
        from src.core.models.community import Community
        from src.core.vector_store import VectorStore

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
                    "faiss": {"persist_directory": str(tmp_path / "faiss-community-summary")},
                }
            },
            app={"host": "127.0.0.1", "port": 8000},
        )

        class FakeLLM:
            async def embed(self, texts):
                return [[1.0, 0.0, 0.0] for _ in texts]

            async def generate(self, prompt, temperature=0.5, max_tokens=500):
                assert "Alice Community" in prompt
                return "Summary: Alice integration cluster summary."

        fake_llm = FakeLLM()
        extracted_entity = Entity(
            id="raw-entity-alice",
            name="Alice",
            type="person",
            properties={"role": "engineer"},
            source_text="Alice built Memory Graph integration tests.",
            confidence=0.95,
            created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
        )

        with ExitStack() as stack:
            stack.enter_context(patch("src.core.graph_store.get_settings", return_value=runtime_settings))
            stack.enter_context(patch("src.core.vector_store.get_settings", return_value=runtime_settings))

            graph_store = GraphStore()
            vector_store = VectorStore()
            memory_service = MemoryService(
                llm=fake_llm,
                vector_store=vector_store,
                graph_store=graph_store,
            )
            memory_service.extractor.extract = AsyncMock(
                return_value=ExtractionResult(
                    entities=[extracted_entity],
                    relationships=[],
                    facts=["Alice built Memory Graph integration tests."],
                    summary="Alice integration note",
                )
            )

            stack.enter_context(
                patch("src.api.routes.memories.get_memory_service", return_value=memory_service)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_vector_store", return_value=vector_store)
            )
            stack.enter_context(
                patch("src.api.routes.memories.get_graph_store", return_value=graph_store)
            )

            create_response = await client.post(
                "/api/v1/memories",
                json={
                    "content": "Alice built Memory Graph integration tests.",
                    "metadata": {
                        "source": "manual",
                        "title": "Community summary integration note",
                        "tags": ["integration", "summary"],
                    },
                },
            )
            assert create_response.status_code == 200

            entities = await graph_store.get_entities(limit=10)
            assert len(entities) == 1
            primary_entity_id = entities[0].id

            extra_entity_ids = []
            for index, name in enumerate(["Memory Graph", "Integration Tests"], start=1):
                entity_id = f"extra-entity-{index}"
                await graph_store.create_entity(
                    GraphEntity(
                        id=entity_id,
                        name=name,
                        type="concept",
                        properties={},
                        source_text=f"{name} supports Alice integration coverage.",
                        confidence=0.9,
                        created_at=datetime.fromisoformat("2026-03-26T09:00:00"),
                    )
                )
                extra_entity_ids.append(entity_id)

            community = Community(
                id="comm-summary",
                level=1,
                parent_id=None,
                entity_ids=[primary_entity_id, *extra_entity_ids],
                summary="stale summary should be replaced",
                title="Alice Community",
                rank=0.95,
            )
            await graph_store.create_community(community)
            await graph_store.replace_community_memberships(
                community_id=community.id,
                entity_ids=[primary_entity_id, *extra_entity_ids],
            )

            hierarchy_builder = HierarchyBuilder(graph_store=graph_store)

            class BoundCommunitySummarizer:
                def __init__(self):
                    from src.core.community_summarizer import CommunitySummarizer

                    self._delegate = CommunitySummarizer(
                        graph_store=graph_store,
                        llm_manager=fake_llm,
                    )

                async def generate_summary(self, community_id, max_tokens=500, force_regenerate=False):
                    return await self._delegate.generate_summary(
                        community_id,
                        max_tokens=max_tokens,
                        force_regenerate=force_regenerate,
                    )

            stack.enter_context(
                patch("src.api.routes.communities.HierarchyBuilder", return_value=hierarchy_builder)
            )
            stack.enter_context(
                patch(
                    "src.api.routes.communities.CommunitySummarizer",
                    side_effect=BoundCommunitySummarizer,
                )
            )

            summary_response = await client.post(
                "/api/v1/communities/comm-summary/summarize",
                json={"regenerate": True, "max_tokens": 128},
            )

            assert summary_response.status_code == 200
            summary_payload = summary_response.json()
            assert summary_payload["community_id"] == "comm-summary"
            assert summary_payload["summary"] == "Alice integration cluster summary."
            assert summary_payload["token_count"] == 4

            stored_community = await graph_store.get_community("comm-summary")
            assert stored_community["summary"] == "Alice integration cluster summary."

            hierarchy_response = await client.get("/api/v1/communities")
            assert hierarchy_response.status_code == 200
            listed = hierarchy_response.json()
            assert listed["communities"][0]["id"] == "comm-summary"
            assert listed["communities"][0]["summary"] == "Alice integration cluster summary."

            await graph_store.close()
            await vector_store.close()
