"""Focused tests for the unified retrieval facade."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.retrieval_facade import RetrievalFacade, RetrievalResult, resolve_retrieval_strategy
from src.core.retriever import Retriever


@pytest.mark.parametrize(
    ("strategy", "backend", "execution_strategy"),
    [
        ("vector", "legacy", "vector"),
        ("graph", "legacy", "graph"),
        ("hybrid", "legacy", "hybrid"),
        ("graphrag", "graphrag", "hybrid"),
        ("local", "graphrag", "local"),
        ("global", "graphrag", "global"),
        ("graphrag_local", "graphrag", "local"),
        (" GRAPH ", "legacy", "graph"),
        ("unknown", "legacy", "hybrid"),
        (None, "legacy", "hybrid"),
    ],
)
def test_resolve_retrieval_strategy_maps_supported_values(
    strategy,
    backend,
    execution_strategy,
):
    plan = resolve_retrieval_strategy(strategy)

    assert plan.backend == backend
    assert plan.execution_strategy == execution_strategy


@pytest.mark.asyncio
async def test_facade_search_maps_graphrag_results_onto_unified_model():
    graphrag_result = SimpleNamespace(
        answer="GraphRAG answer",
        sources=[
            SimpleNamespace(
                memory_id="mem-42",
                content="Graph context",
                relevance=0.91,
                entities=["alice"],
                community_id="comm-1",
                community_summary="Shared context",
            )
        ],
        entities=["alice"],
        communities=[
            SimpleNamespace(
                community_id="comm-1",
                title="Graph Cluster",
                summary="Shared context",
                level=1,
                entities=["alice"],
                relevance=0.88,
            )
        ],
        strategy_used="hybrid",
        query_entities=["alice"],
        processing_time_ms=17,
    )
    graphrag_retriever = MagicMock()
    graphrag_retriever.retrieve = AsyncMock(return_value=graphrag_result)

    facade = RetrievalFacade(
        llm_manager=MagicMock(),
        vector_store=MagicMock(),
        graph_store=MagicMock(),
        graphrag_retriever=graphrag_retriever,
    )

    result = await facade.search(
        "who is alice",
        strategy="graphrag",
        top_k=4,
        include_sources=False,
    )

    assert result.answer == "GraphRAG answer"
    assert result.backend_used == "graphrag"
    assert result.strategy_used == "hybrid"
    assert result.query_entities == ["alice"]
    assert result.communities == graphrag_result.communities
    assert result.sources[0].community_id == "comm-1"
    assert result.sources[0].community_summary == "Shared context"
    graphrag_retriever.retrieve.assert_awaited_once_with(
        query="who is alice",
        strategy="hybrid",
        top_k=4,
        include_sources=False,
    )


@pytest.mark.asyncio
async def test_facade_answer_runs_legacy_vector_flow():
    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])
    llm.generate_answer = AsyncMock(return_value="Synthesized answer")

    vector_store = MagicMock()
    vector_store.search = AsyncMock(
        return_value=[SimpleNamespace(id="mem-1", content="Vector match", relevance=0.84)]
    )

    facade = RetrievalFacade(
        llm_manager=llm,
        vector_store=vector_store,
        graph_store=MagicMock(),
    )

    result = await facade.answer("what happened", strategy="vector", top_k=1)

    assert result.answer == "Synthesized answer"
    assert result.backend_used == "legacy"
    assert result.strategy_used == "vector"
    assert [source.memory_id for source in result.sources] == ["mem-1"]
    llm.generate_answer.assert_awaited_once_with("[Source 1]: Vector match", "what happened")


@pytest.mark.asyncio
async def test_facade_graph_search_accepts_flat_neighbor_shape():
    llm = MagicMock()

    graph_store = MagicMock()
    graph_store.get_entity = AsyncMock(return_value=SimpleNamespace(id="ent-1"))
    graph_store.get_neighbors = AsyncMock(
        return_value=[{"id": "ent-2", "name": "Project Atlas", "type": "project"}]
    )

    facade = RetrievalFacade(
        llm_manager=llm,
        vector_store=MagicMock(),
        graph_store=graph_store,
    )

    extractor = MagicMock()
    extractor.extract = AsyncMock(
        return_value=SimpleNamespace(entities=[SimpleNamespace(id="ent-1", name="Alice")])
    )

    with patch("src.core.retrieval_facade.EntityExtractor", return_value=extractor):
        result = await facade.search("alice", strategy="graph", top_k=5)

    assert result.backend_used == "legacy"
    assert result.strategy_used == "graph"
    assert result.entities == ["Alice"]
    assert result.sources[0].memory_id is None
    assert result.sources[0].content == "Project Atlas (project)"
    assert result.sources[0].entities == ["Alice"]


@pytest.mark.asyncio
async def test_retriever_remains_a_thin_compatibility_layer():
    retriever = Retriever(MagicMock(), MagicMock(), MagicMock())

    search_result = RetrievalResult(answer="", processing_time_ms=3)
    answer_result = RetrievalResult(answer="from facade", processing_time_ms=5)
    retriever.facade.search = AsyncMock(return_value=search_result)
    retriever.facade.answer = AsyncMock(return_value=answer_result)

    observed_search = await retriever.search(
        "question",
        strategy="global",
        top_k=2,
        include_sources=False,
    )
    observed_answer = await retriever.answer(
        "question",
        strategy="graphrag",
        top_k=3,
        include_sources=True,
    )

    assert observed_search is search_result
    assert observed_answer is answer_result
    retriever.facade.search.assert_awaited_once_with(
        "question",
        strategy="global",
        top_k=2,
        include_sources=False,
    )
    retriever.facade.answer.assert_awaited_once_with(
        "question",
        strategy="graphrag",
        top_k=3,
        include_sources=True,
    )


@pytest.mark.asyncio
async def test_facade_search_auto_layer_falls_back_to_l3_when_legacy_returns_empty():
    llm = MagicMock()
    llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3]])

    vector_store = MagicMock()
    vector_store.search = AsyncMock(return_value=[])

    graphrag_result = SimpleNamespace(
        answer="",
        sources=[SimpleNamespace(memory_id="mem-99", content="Graph fallback", relevance=0.9, entities=["alice"])],
        entities=["alice"],
        communities=[],
        strategy_used="hybrid",
        query_entities=["alice"],
        processing_time_ms=11,
    )
    graphrag_retriever = MagicMock()
    graphrag_retriever.retrieve = AsyncMock(return_value=graphrag_result)

    facade = RetrievalFacade(
        llm_manager=llm,
        vector_store=vector_store,
        graph_store=MagicMock(),
        graphrag_retriever=graphrag_retriever,
    )

    result = await facade.search("who is alice", strategy="hybrid", layer="auto", top_k=3)

    assert result.layer_requested == "auto"
    assert result.layer_used == "l3"
    assert result.layer_fallback_chain == ["l2", "l3"]
    graphrag_retriever.retrieve.assert_awaited_once_with(
        query="who is alice",
        strategy="hybrid",
        top_k=3,
        include_sources=True,
    )


@pytest.mark.asyncio
async def test_facade_answer_accepts_explicit_l3_layer():
    llm = MagicMock()
    llm.generate_answer = AsyncMock(return_value="Deep answer")

    graphrag_result = SimpleNamespace(
        answer="Deep answer",
        sources=[SimpleNamespace(memory_id="mem-deep", content="Deep context", relevance=0.9, entities=["deep"])],
        entities=["deep"],
        communities=[],
        strategy_used="hybrid",
        query_entities=["deep"],
        processing_time_ms=8,
    )
    graphrag_retriever = MagicMock()
    graphrag_retriever.retrieve = AsyncMock(return_value=graphrag_result)

    facade = RetrievalFacade(
        llm_manager=llm,
        vector_store=MagicMock(),
        graph_store=MagicMock(),
        graphrag_retriever=graphrag_retriever,
    )

    result = await facade.answer("deep question", strategy="hybrid", top_k=2, layer="l3", layer_budget_override=2048)

    assert result.layer_requested == "l3"
    assert result.layer_used == "l3"
    assert result.layer_fallback_chain == ["l3"]
    assert result.context_token_estimate > 0


@pytest.mark.asyncio
async def test_facade_answer_uses_identity_profile_for_l0_layer():
    llm = MagicMock()
    llm.generate_answer = AsyncMock(return_value="Profile answer")

    facade = RetrievalFacade(
        llm_manager=llm,
        vector_store=MagicMock(),
        graph_store=MagicMock(),
    )

    with patch("src.core.retrieval_facade.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(
            memory_layers=SimpleNamespace(
                identity=SimpleNamespace(profile_text="User focuses on launch planning."),
                l0=SimpleNamespace(max_tokens=120),
                l1=SimpleNamespace(max_tokens=700, max_entities=12, max_communities=4, max_pinned_memories=6),
                l2=SimpleNamespace(max_tokens=400, default_top_k=5),
                l3=SimpleNamespace(enabled=True, max_tokens=1200, default_strategy="hybrid"),
            )
        )
        result = await facade.answer("What do I focus on?", layer="l0")

    assert result.layer_requested == "l0"
    assert result.layer_used == "l0"
    assert result.sources[0].metadata["record_type"] == "identity_profile"
    llm.generate_answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_facade_search_builds_l1_from_pinned_memories_communities_and_entities():
    llm = MagicMock()
    vector_store = MagicMock()
    vector_store.get_memories = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="mem-pinned",
                content="Pinned launch memory",
                metadata={"pinned": True, "summary": "Pinned launch memory"},
            ),
            SimpleNamespace(
                id="mem-unpinned",
                content="Ordinary memory",
                metadata={"pinned": False},
            ),
        ]
    )
    graph_store = MagicMock()
    graph_store.list_communities = AsyncMock(
        return_value=[
            {
                "id": "comm-1",
                "title": "Launch Cluster",
                "summary": "Launch planning cluster",
                "level": 1,
                "rank": 0.91,
                "entity_ids": ["entity-1"],
            }
        ]
    )
    graph_store.query_entities = AsyncMock(
        return_value=[
            SimpleNamespace(
                id="entity-1",
                name="Alice",
                type="person",
                source_text="Alice owns launch",
                confidence=0.95,
                created_at="2026-04-01T00:00:00+00:00",
            )
        ]
    )

    facade = RetrievalFacade(
        llm_manager=llm,
        vector_store=vector_store,
        graph_store=graph_store,
    )

    with patch("src.core.retrieval_facade.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(
            memory_layers=SimpleNamespace(
                identity=SimpleNamespace(profile_text=""),
                l0=SimpleNamespace(max_tokens=120),
                l1=SimpleNamespace(max_tokens=700, max_entities=1, max_communities=1, max_pinned_memories=1),
                l2=SimpleNamespace(max_tokens=400, default_top_k=5),
                l3=SimpleNamespace(enabled=True, max_tokens=1200, default_strategy="hybrid"),
            )
        )
        result = await facade.search("launch", layer="l1")

    assert result.layer_requested == "l1"
    assert result.layer_used == "l1"
    assert any(source.memory_id == "mem-pinned" for source in result.sources)
    assert any(source.community_id == "comm-1" for source in result.sources)
    assert any(source.metadata.get("record_type") == "essential_entity" for source in result.sources)
    assert result.entities == ["Alice"]
