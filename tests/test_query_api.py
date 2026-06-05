"""Focused tests for /api/v1/query endpoint."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.query_trace import reset_query_trace_store


@pytest.fixture(autouse=True)
def reset_query_trace_store_fixture():
    reset_query_trace_store()
    yield
    reset_query_trace_store()


def _expected_source(**overrides):
    payload = {
        "memory_id": None,
        "content": "",
        "relevance": 0.0,
        "entities": [],
        "source": None,
        "workspace_id": None,
        "external_id": None,
        "source_path": None,
        "record_type": None,
        "title": None,
        "tags": [],
        "timestamp": None,
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
        "provenance": {
            "type": None,
            "time": None,
            "imported_from": None,
        },
        "community_id": None,
        "community_summary": None,
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


def _expected_layer_response(**overrides):
    payload = {
        "layer_used": None,
        "layer_fallback_chain": [],
        "context_token_estimate": 0,
    }
    payload.update(overrides)
    return payload


class TestQueryEndpoint:
    """Test /api/v1/query endpoint."""

    @pytest.mark.asyncio
    async def test_query_missing_question(self, client):
        response = await client.post("/api/v1/query", json={})

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_query_with_question_returns_answer(self, client):
        mock_result = SimpleNamespace(
            answer="Answer from retriever",
            sources=[
                SimpleNamespace(
                    memory_id="mem-1",
                    content="Relevant memory",
                    relevance=0.91,
                    entities=["alice"],
                )
            ],
            entities=["alice"],
            processing_time_ms=12,
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=32,
            layer_build_duration_ms=4,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=SimpleNamespace(
                metadata={
                    "source": "manual",
                    "workspace_id": "workspace-main",
                    "external_id": "ext-1",
                    "source_path": "memory/decision.md",
                    "record_type": "decision",
                    "title": "Decision",
                    "timestamp": "2026-04-02T10:00:00+00:00",
                }
            )
        )

        with patch("src.api.routes.query.get_llm_manager", return_value=MagicMock()):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(return_value=mock_result),
                    ):
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "test question",
                                "strategy": "hybrid",
                                "session_id": "session-main",
                            },
                        )

        assert response.status_code == 200
        assert response.headers["x-query-run-id"].startswith("qrun_")
        assert response.headers["x-query-session-id"] == "session-main"
        assert response.json() == {
            "answer": "Answer from retriever",
            "sources": [
                _expected_source(
                    memory_id="mem-1",
                    content="Relevant memory",
                    relevance=0.91,
                    entities=["alice"],
                    source="manual",
                    workspace_id="workspace-main",
                    external_id="ext-1",
                    source_path="memory/decision.md",
                    record_type="decision",
                    title="Decision",
                    timestamp="2026-04-02T10:00:00+00:00",
                    provenance={
                        "type": "decision",
                        "time": "2026-04-02T10:00:00+00:00",
                        "imported_from": "memory/decision.md",
                    },
                )
            ],
            "entities": ["alice"],
            "communities": [],
            "processing_time_ms": 12,
            "next_cursor": None,
            "diagnostics": _expected_collection_diagnostics(
                applied_filters={"session_id": "session-main"},
            ),
            **_expected_layer_response(
                layer_used="l2",
                layer_fallback_chain=["l2"],
                context_token_estimate=32,
            ),
        }
        mock_vector_store.get_memory.assert_awaited_once_with("mem-1")

    @pytest.mark.asyncio
    async def test_query_with_graphrag_maps_source_and_community_fields(self, client):
        mock_result = SimpleNamespace(
            answer="Answer from graphrag",
            sources=[
                SimpleNamespace(
                    memory_id="mem-42",
                    content="GraphRAG source",
                    relevance=0.87,
                    entities=["alice", "graph"],
                    community_id="comm-1",
                    community_summary="Shared graph context",
                )
            ],
            entities=["alice", "graph"],
            communities=[
                SimpleNamespace(
                    community_id="comm-1",
                    title="Graph Cluster",
                    summary="Shared graph context",
                    level=1,
                    entities=["entity-1", "entity-2"],
                    relevance=0.91,
                )
            ],
            processing_time_ms=21,
            layer_used="l3",
            layer_fallback_chain=["l3"],
            context_token_estimate=41,
            layer_build_duration_ms=5,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            return_value=SimpleNamespace(
                metadata={
                    "source": "sync",
                    "workspace_id": "workspace-graph",
                    "external_id": "ext-42",
                    "source_path": "notes/graph.md",
                    "record_type": "note",
                    "title": "Graph note",
                    "timestamp": "2026-04-01T09:00:00+00:00",
                }
            )
        )

        with patch("src.api.routes.query.get_llm_manager", return_value=MagicMock()):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(return_value=mock_result),
                    ) as mock_answer:
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "test graphrag question",
                                "strategy": "graphrag",
                                "retrieval_mode": "global",
                                "top_k": 3,
                                "include_sources": True,
                            },
                        )

        assert response.status_code == 200
        assert response.headers["x-query-run-id"].startswith("qrun_")
        assert response.json() == {
            "answer": "Answer from graphrag",
            "sources": [
                _expected_source(
                    memory_id="mem-42",
                    content="GraphRAG source",
                    relevance=0.87,
                    entities=["alice", "graph"],
                    source="sync",
                    workspace_id="workspace-graph",
                    external_id="ext-42",
                    source_path="notes/graph.md",
                    record_type="note",
                    title="Graph note",
                    timestamp="2026-04-01T09:00:00+00:00",
                    provenance={
                        "type": "note",
                        "time": "2026-04-01T09:00:00+00:00",
                        "imported_from": "notes/graph.md",
                    },
                    community_id="comm-1",
                    community_summary="Shared graph context",
                )
            ],
            "entities": ["alice", "graph"],
            "communities": [
                {
                    "community_id": "comm-1",
                    "title": "Graph Cluster",
                    "summary": "Shared graph context",
                    "level": 1,
                    "entities": ["entity-1", "entity-2"],
                    "relevance": 0.91,
                }
            ],
            "processing_time_ms": 21,
            "next_cursor": None,
            "diagnostics": _expected_collection_diagnostics(),
            **_expected_layer_response(
                layer_used="l3",
                layer_fallback_chain=["l3"],
                context_token_estimate=41,
            ),
        }
        mock_answer.assert_awaited_once_with(
            question="test graphrag question",
            strategy="global",
            top_k=3,
            include_sources=True,
            layer="auto",
            layer_budget_override=None,
        )
        mock_vector_store.get_memory.assert_awaited_once_with("mem-42")

    @pytest.mark.asyncio
    async def test_query_source_provenance_falls_back_to_source_attributes(self, client):
        source_timestamp = datetime(2026, 4, 2, 10, 30, tzinfo=timezone.utc)
        mock_result = SimpleNamespace(
            answer="Answer with source attrs",
            sources=[
                SimpleNamespace(
                    memory_id="mem-attr-1",
                    content="Relevant memory",
                    relevance=0.77,
                    entities=["source"],
                    source="manual",
                    workspace_id="workspace-attrs",
                    external_id="ext-attrs",
                    source_path="attrs/source.md",
                    record_type="note",
                    timestamp=source_timestamp,
                )
            ],
            entities=["source"],
            processing_time_ms=9,
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=24,
            layer_build_duration_ms=3,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        with patch("src.api.routes.query.get_llm_manager", return_value=MagicMock()):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(return_value=mock_result),
                    ):
                        response = await client.post(
                            "/api/v1/query",
                            json={"question": "test source attrs", "strategy": "hybrid"},
                        )

        assert response.status_code == 200
        assert response.headers["x-query-run-id"].startswith("qrun_")
        assert response.json() == {
            "answer": "Answer with source attrs",
            "sources": [
                _expected_source(
                    memory_id="mem-attr-1",
                    content="Relevant memory",
                    relevance=0.77,
                    entities=["source"],
                    source="manual",
                    workspace_id="workspace-attrs",
                    external_id="ext-attrs",
                    source_path="attrs/source.md",
                    record_type="note",
                    timestamp="2026-04-02T10:30:00+00:00",
                    provenance={
                        "type": "note",
                        "time": "2026-04-02T10:30:00+00:00",
                        "imported_from": "attrs/source.md",
                    },
                )
            ],
            "entities": ["source"],
            "communities": [],
            "processing_time_ms": 9,
            "next_cursor": None,
            "diagnostics": _expected_collection_diagnostics(),
            **_expected_layer_response(
                layer_used="l2",
                layer_fallback_chain=["l2"],
                context_token_estimate=24,
            ),
        }
        mock_vector_store.get_memory.assert_awaited_once_with("mem-attr-1")

    @pytest.mark.asyncio
    async def test_graphrag_query_allows_missing_memory_id_without_vector_lookup(self, client):
        source_timestamp = datetime(2026, 4, 8, 11, 0, tzinfo=timezone.utc)
        mock_result = SimpleNamespace(
            answer="Answer with community-only source",
            sources=[
                SimpleNamespace(
                    memory_id=None,
                    content="Alice owns the launch checklist through community-only evidence.",
                    relevance=0.82,
                    entities=["Alice", "Launch Checklist"],
                    community_id="comm-missing-memory-id",
                    community_summary="Community-only evidence for launch ownership.",
                    source="community_only",
                    source_path="community://launch-owners",
                    record_type="community_summary",
                    timestamp=source_timestamp,
                    title="Launch ownership without direct memory",
                )
            ],
            entities=["Alice"],
            communities=[],
            processing_time_ms=17,
            layer_used="l3",
            layer_fallback_chain=["l3"],
            context_token_estimate=28,
            layer_build_duration_ms=4,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        with patch("src.api.routes.query.get_llm_manager", return_value=MagicMock()):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(return_value=mock_result),
                    ):
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "who owns the launch checklist?",
                                "strategy": "graphrag",
                                "retrieval_mode": "global",
                            },
                        )

        assert response.status_code == 200
        assert response.json() == {
            "answer": "Answer with community-only source",
            "sources": [
                _expected_source(
                    memory_id=None,
                    content="Alice owns the launch checklist through community-only evidence.",
                    relevance=0.82,
                    entities=["Alice", "Launch Checklist"],
                    source="community_only",
                    source_path="community://launch-owners",
                    record_type="community_summary",
                    title="Launch ownership without direct memory",
                    timestamp="2026-04-08T11:00:00+00:00",
                    provenance={
                        "type": "community_summary",
                        "time": "2026-04-08T11:00:00+00:00",
                        "imported_from": "community://launch-owners",
                    },
                    community_id="comm-missing-memory-id",
                    community_summary="Community-only evidence for launch ownership.",
                )
            ],
            "entities": ["Alice"],
            "communities": [],
            "processing_time_ms": 17,
            "next_cursor": None,
            "diagnostics": _expected_collection_diagnostics(),
            **_expected_layer_response(
                layer_used="l3",
                layer_fallback_chain=["l3"],
                context_token_estimate=28,
            ),
        }
        mock_vector_store.get_memory.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_query_with_structured_filters_filters_sources_server_side(self, client):
        llm = MagicMock()
        llm.generate_answer = AsyncMock(return_value="Scoped answer")

        mock_result = SimpleNamespace(
            sources=[
                SimpleNamespace(
                    memory_id="mem-keep",
                    content="Keep this scoped memory",
                    relevance=0.91,
                    entities=["launch"],
                ),
                SimpleNamespace(
                    memory_id="mem-drop",
                    content="Drop this other memory",
                    relevance=0.89,
                    entities=["ops"],
                ),
            ],
            communities=[],
            processing_time_ms=18,
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=22,
            layer_build_duration_ms=6,
        )
        mock_vector_store = MagicMock()

        async def get_memory(memory_id):
            if memory_id == "mem-keep":
                return SimpleNamespace(
                    metadata={
                        "source": "manual",
                        "workspace_id": "workspace-main",
                        "scope": "task",
                        "scope_id": "task-123",
                        "task_id": "task-123",
                        "visibility": "private",
                        "tags": ["launch"],
                        "summary": "Keep summary",
                    }
                )
            return SimpleNamespace(
                metadata={
                    "source": "manual",
                    "workspace_id": "workspace-main",
                    "scope": "task",
                    "scope_id": "task-999",
                    "task_id": "task-999",
                    "visibility": "private",
                    "tags": ["ops"],
                    "summary": "Drop summary",
                }
            )

        mock_vector_store.get_memory = AsyncMock(side_effect=get_memory)

        with patch("src.api.routes.query.get_llm_manager", return_value=llm):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.search",
                        new=AsyncMock(return_value=mock_result),
                    ) as mock_search:
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "launch scope query",
                                "strategy": "hybrid",
                                "workspace_id": "workspace-main",
                                "scopes": ["task"],
                                "scope_ids": ["task-123"],
                                "task_id": "task-123",
                                "tags": ["launch"],
                                "visibility": "private",
                            },
                        )

        assert response.status_code == 200
        assert response.json()["answer"] == "Scoped answer"
        assert [item["memory_id"] for item in response.json()["sources"]] == ["mem-keep"]
        assert response.json()["sources"][0]["summary"] == "Keep summary"
        assert response.json()["next_cursor"] is None
        assert response.json()["diagnostics"] == _expected_collection_diagnostics(
            applied_filters={
                "scopes": ["task"],
                "scope_ids": ["task-123"],
                "tags": ["launch"],
                "visibility": "private",
                "workspace_id": "workspace-main",
                "task_id": "task-123",
            },
            server_side_filtered=True,
            candidate_window=50,
            warnings=[],
        )
        assert response.json()["layer_used"] == "l2"
        assert response.json()["layer_fallback_chain"] == ["l2"]
        assert response.json()["context_token_estimate"] == 22
        mock_search.assert_awaited_once()
        llm.generate_answer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_query_with_structured_filters_returns_next_cursor_when_more_results_exist(self, client):
        llm = MagicMock()
        llm.generate_answer = AsyncMock(return_value="Paged answer")

        mock_result = SimpleNamespace(
            sources=[
                SimpleNamespace(memory_id="mem-1", content="One", relevance=0.91, entities=["launch"]),
                SimpleNamespace(memory_id="mem-2", content="Two", relevance=0.9, entities=["launch"]),
                SimpleNamespace(memory_id="mem-3", content="Three", relevance=0.89, entities=["launch"]),
            ],
            communities=[],
            processing_time_ms=20,
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=44,
            layer_build_duration_ms=6,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(
            side_effect=[
                SimpleNamespace(metadata={"workspace_id": "workspace-main", "scope": "task", "scope_id": "task-123", "tags": ["launch"]}),
                SimpleNamespace(metadata={"workspace_id": "workspace-main", "scope": "task", "scope_id": "task-123", "tags": ["launch"]}),
                SimpleNamespace(metadata={"workspace_id": "workspace-main", "scope": "task", "scope_id": "task-123", "tags": ["launch"]}),
            ]
        )

        with patch("src.api.routes.query.get_llm_manager", return_value=llm):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch("src.api.routes.query.RetrievalFacade.search", new=AsyncMock(return_value=mock_result)):
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "paged launch query",
                                "strategy": "hybrid",
                                "workspace_id": "workspace-main",
                                "scopes": ["task"],
                                "scope_ids": ["task-123"],
                                "tags": ["launch"],
                                "top_k": 2,
                            },
                        )

        assert response.status_code == 200
        assert [item["memory_id"] for item in response.json()["sources"]] == ["mem-1", "mem-2"]
        assert response.json()["next_cursor"] == "2"
        assert response.json()["diagnostics"]["truncated"] is True
        assert response.json()["layer_used"] == "l2"
        assert response.json()["context_token_estimate"] == 44

    @pytest.mark.asyncio
    async def test_query_explicit_l0_layer_round_trips_response_and_trace(self, client):
        mock_result = SimpleNamespace(
            answer="Identity answer",
            sources=[
                SimpleNamespace(
                    memory_id=None,
                    content="User focuses on launch planning.",
                    relevance=1.0,
                    entities=[],
                    metadata={"record_type": "identity_profile", "source": "memory_layer"},
                )
            ],
            entities=[],
            communities=[],
            processing_time_ms=7,
            layer_requested="l0",
            layer_used="l0",
            layer_fallback_chain=["l0"],
            context_token_estimate=12,
            layer_build_duration_ms=3,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        llm = MagicMock()
        llm.settings = SimpleNamespace(
            llm=SimpleNamespace(
                provider="openai",
                openai=SimpleNamespace(model="gpt-4o-mini"),
            )
        )

        with patch("src.api.routes.query.get_llm_manager", return_value=llm):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch("src.api.routes.query.RetrievalFacade.answer", new=AsyncMock(return_value=mock_result)):
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "who am i",
                                "strategy": "hybrid",
                                "layer": "l0",
                            },
                        )

        assert response.status_code == 200
        assert response.json()["layer_used"] == "l0"
        run_id = response.headers["x-query-run-id"]
        detail_response = await client.get(f"/api/v1/query/runs/{run_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["layer_requested"] == "l0"
        assert detail_response.json()["layer_used"] == "l0"

    @pytest.mark.asyncio
    async def test_query_run_trace_endpoints_return_recent_run_details(self, client):
        mock_result = SimpleNamespace(
            answer="Traceable answer",
            sources=[SimpleNamespace(memory_id="mem-trace", content="Trace source", relevance=0.88, entities=["trace"])],
            entities=["trace"],
            communities=[],
            processing_time_ms=14,
            layer_requested="auto",
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=19,
            layer_build_duration_ms=5,
        )
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        llm = MagicMock()
        llm.settings = SimpleNamespace(
            llm=SimpleNamespace(
                provider="openai",
                openai=SimpleNamespace(model="gpt-4o-mini"),
            )
        )
        llm.generate_answer = AsyncMock(return_value="Traceable answer")

        with patch("src.api.routes.query.get_llm_manager", return_value=llm):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(return_value=mock_result),
                    ):
                        query_response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "trace this query",
                                "strategy": "hybrid",
                                "top_k": 6,
                                "include_sources": False,
                                "session_id": "session-trace",
                            },
                        )

        assert query_response.status_code == 200
        run_id = query_response.headers["x-query-run-id"]

        list_response = await client.get("/api/v1/query/runs?limit=5")
        assert list_response.status_code == 200
        assert list_response.json() == {
            "runs": [
                {
                    "run_id": run_id,
                    "session_id": "session-trace",
                    "question": "trace this query",
                    "strategy": "hybrid",
                    "retrieval_mode": None,
                    "status": "succeeded",
                    "llm_provider": "openai",
                    "llm_model": "gpt-4o-mini",
                    "llm_duration_ms": 0,
                    "processing_time_ms": 14,
                    "layer_requested": "auto",
                    "layer_used": "l2",
                    "layer_fallback_chain": ["l2"],
                    "context_token_estimate": 19,
                    "layer_build_duration_ms": 5,
                    "source_count": 1,
                    "community_count": 0,
                    "started_at": list_response.json()["runs"][0]["started_at"],
                    "completed_at": list_response.json()["runs"][0]["completed_at"],
                    "failure_reason": None,
                }
            ],
            "total": 1,
        }

        detail_response = await client.get(f"/api/v1/query/runs/{run_id}")
        assert detail_response.status_code == 200
        detail_body = detail_response.json()
        assert detail_body == {
            "run_id": run_id,
            "session_id": "session-trace",
            "question": "trace this query",
            "strategy": "hybrid",
            "retrieval_mode": None,
            "status": "succeeded",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_duration_ms": 0,
            "processing_time_ms": 14,
            "layer_requested": "auto",
            "layer_used": "l2",
            "layer_fallback_chain": ["l2"],
            "context_token_estimate": 19,
            "layer_build_duration_ms": 5,
            "source_count": 1,
            "community_count": 0,
            "started_at": detail_body["started_at"],
            "completed_at": detail_body["completed_at"],
            "failure_reason": None,
            "top_k": 6,
            "include_sources": False,
            "entities_count": 1,
        }

    @pytest.mark.asyncio
    async def test_query_failure_records_trace_and_returns_run_id_header(self, client):
        failing_llm = MagicMock()
        failing_llm.settings = SimpleNamespace(
            llm=SimpleNamespace(
                provider="anthropic",
                anthropic=SimpleNamespace(model="claude-sonnet-4-20250514"),
            )
        )
        failing_llm.generate_answer = AsyncMock(return_value="unused")

        with patch("src.api.routes.query.get_llm_manager", return_value=failing_llm):
            with patch("src.api.routes.query.get_vector_store", return_value=MagicMock()):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(side_effect=RuntimeError("retrieval exploded")),
                    ):
                        response = await client.post(
                            "/api/v1/query",
                            json={
                                "question": "fail this query",
                                "strategy": "graphrag",
                                "retrieval_mode": "global",
                                "session_id": "session-fail",
                            },
                        )

        assert response.status_code == 500
        run_id = response.headers["x-query-run-id"]
        assert response.headers["x-query-session-id"] == "session-fail"
        assert response.json() == {"detail": "retrieval exploded"}

        detail_response = await client.get(f"/api/v1/query/runs/{run_id}")
        assert detail_response.status_code == 200
        assert detail_response.json()["status"] == "failed"
        assert detail_response.json()["failure_reason"] == "retrieval exploded"
        assert detail_response.json()["strategy"] == "global"
        assert detail_response.json()["retrieval_mode"] == "global"
        assert detail_response.json()["layer_requested"] == "auto"

    @pytest.mark.asyncio
    async def test_query_runs_list_supports_status_strategy_layer_and_session_filters(self, client):
        llm = MagicMock()
        llm.settings = SimpleNamespace(
            llm=SimpleNamespace(
                provider="openai",
                openai=SimpleNamespace(model="gpt-4o-mini"),
            )
        )
        llm.generate_answer = AsyncMock(return_value="ok")
        mock_vector_store = MagicMock()
        mock_vector_store.get_memory = AsyncMock(return_value=None)

        success_result = SimpleNamespace(
            answer="ok",
            sources=[SimpleNamespace(memory_id="mem-a", content="A", relevance=0.9, entities=["a"])],
            entities=["a"],
            communities=[],
            processing_time_ms=10,
            layer_requested="auto",
            layer_used="l2",
            layer_fallback_chain=["l2"],
            context_token_estimate=11,
            layer_build_duration_ms=3,
        )
        failure_result = RuntimeError("boom")

        with patch("src.api.routes.query.get_llm_manager", return_value=llm):
            with patch("src.api.routes.query.get_vector_store", return_value=mock_vector_store):
                with patch("src.api.routes.query.get_graph_store", return_value=MagicMock()):
                    with patch(
                        "src.api.routes.query.RetrievalFacade.answer",
                        new=AsyncMock(side_effect=[success_result, failure_result]),
                    ):
                        await client.post(
                            "/api/v1/query",
                            json={"question": "success case", "strategy": "hybrid", "session_id": "session-1"},
                        )
                        await client.post(
                            "/api/v1/query",
                            json={"question": "failure case", "strategy": "graphrag", "retrieval_mode": "global", "session_id": "session-2"},
                        )

        response = await client.get("/api/v1/query/runs?status=succeeded&strategy=hybrid&layer_used=l2&session_id=session-1")

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["runs"][0]["question"] == "success case"
        assert body["runs"][0]["status"] == "succeeded"
        assert body["runs"][0]["strategy"] == "hybrid"
        assert body["runs"][0]["layer_used"] == "l2"
        assert body["runs"][0]["session_id"] == "session-1"
