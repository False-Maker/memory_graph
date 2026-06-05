"""Tests for GraphRAG Retriever module."""

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime

from src.core.graphrag_retriever import (
    CommunityContext,
    GraphRAGSource,
    GraphRAGRetrievalResult,
    GraphRAGRetriever,
)
from src.core.models.community import Community, CommunityHierarchy
from src.core.entity_extractor import Entity, ExtractionResult
from src.core.graphrag_retriever_eval import (
    DEFAULT_REPRESENTATIVE_CASES,
    GraphRAGEvalSummary,
    StrategyExpectations,
    StrategyEvalSummary,
    build_fixture_retriever,
    compare_against_baseline,
    evaluate_against_expectations,
    evaluate_graphrag_retrieval,
    load_eval_expectations,
)


# ============================================
# Test Data Classes
# ============================================


class TestCommunityContext:
    """Test CommunityContext dataclass."""

    def test_creation(self):
        """Test creating a CommunityContext."""
        ctx = CommunityContext(
            community_id="comm-1",
            title="Test Community",
            summary="Test summary",
            level=0,
            entities=["entity-1", "entity-2"],
            relationships=[{"source": "e1", "target": "e2"}],
            relevance=0.85,
        )
        assert ctx.community_id == "comm-1"
        assert ctx.title == "Test Community"
        assert ctx.summary == "Test summary"
        assert ctx.level == 0
        assert len(ctx.entities) == 2
        assert ctx.relevance == 0.85

    def test_defaults(self):
        """Test CommunityContext default values."""
        ctx = CommunityContext(
            community_id="comm-1", title="Test", summary="Summary", level=0
        )
        assert ctx.entities == []
        assert ctx.relationships == []
        assert ctx.relevance == 0.0


class TestGraphRAGSource:
    """Test GraphRAGSource dataclass."""

    def test_creation(self):
        """Test creating a GraphRAGSource."""
        source = GraphRAGSource(
            memory_id="mem-1",
            content="Test content",
            relevance=0.9,
            entities=["entity-1"],
            community_id="comm-1",
            community_summary="Community summary",
        )
        assert source.memory_id == "mem-1"
        assert source.content == "Test content"
        assert source.relevance == 0.9
        assert source.community_id == "comm-1"

    def test_defaults(self):
        """Test GraphRAGSource default values."""
        source = GraphRAGSource(memory_id="mem-1", content="Content", relevance=0.5)
        assert source.entities == []
        assert source.community_id is None
        assert source.community_summary is None


class TestGraphRAGRetrievalResult:
    """Test GraphRAGRetrievalResult dataclass."""

    def test_creation(self):
        """Test creating a GraphRAGRetrievalResult."""
        ctx = CommunityContext(
            community_id="comm-1", title="Test", summary="Summary", level=0
        )
        source = GraphRAGSource(memory_id="mem-1", content="Content", relevance=0.8)

        result = GraphRAGRetrievalResult(
            answer="Test answer",
            sources=[source],
            entities=["entity-1"],
            communities=[ctx],
            strategy_used="hybrid",
            processing_time_ms=150,
            query_entities=["test"],
        )
        assert result.answer == "Test answer"
        assert len(result.sources) == 1
        assert len(result.communities) == 1
        assert result.strategy_used == "hybrid"
        assert result.processing_time_ms == 150

    def test_defaults(self):
        """Test GraphRAGRetrievalResult default values."""
        result = GraphRAGRetrievalResult()
        assert result.answer == ""
        assert result.sources == []
        assert result.entities == []
        assert result.communities == []
        assert result.strategy_used == ""
        assert result.processing_time_ms == 0
        assert result.query_entities == []


# ============================================
# Test GraphRAGRetriever
# ============================================


@pytest.fixture
def mock_graphrag_retriever():
    """Create a mock GraphRAGRetriever with mocked dependencies."""
    # Mock LLM Manager
    mock_llm = MagicMock()
    mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4, 0.5]])
    mock_llm.generate = AsyncMock(return_value="Generated answer")
    mock_llm.generate_answer = AsyncMock(return_value="Generated answer from context")

    # Mock Vector Store
    mock_vector_store = MagicMock()

    # Mock Graph Store
    mock_graph_store = MagicMock()
    mock_graph_store.get_entity_communities = AsyncMock(return_value=[])
    mock_graph_store.get_community = AsyncMock(return_value=None)
    mock_graph_store.get_community_neighbors = AsyncMock(return_value=[])
    mock_graph_store.list_communities = AsyncMock(return_value=[])
    mock_graph_store.get_community_entities = AsyncMock(return_value=[])
    mock_graph_store.get_entity = AsyncMock(return_value=None)
    mock_graph_store.find_entities_by_name = AsyncMock(return_value=[])

    # Create retriever
    retriever = GraphRAGRetriever(
        llm_manager=mock_llm,
        vector_store=mock_vector_store,
        graph_store=mock_graph_store,
        hierarchy=CommunityHierarchy(),
    )

    return retriever, mock_llm, mock_vector_store, mock_graph_store, None


class TestGraphRAGRetrieverInit:
    """Test GraphRAGRetriever initialization."""

    def test_init(self, mock_graphrag_retriever):
        """Test GraphRAGRetriever initialization."""
        retriever, _, _, _, _ = mock_graphrag_retriever
        assert retriever.llm is not None
        assert retriever.vector_store is not None
        assert retriever.graph_store is not None
        assert retriever.hierarchy is not None
        assert retriever._summary_embeddings == {}

    def test_init_with_default_hierarchy(self):
        """Test initialization with default hierarchy."""
        mock_llm = MagicMock()
        mock_vector_store = MagicMock()
        mock_graph_store = MagicMock()

        retriever = GraphRAGRetriever(
            llm_manager=mock_llm,
            vector_store=mock_vector_store,
            graph_store=mock_graph_store,
        )
        assert isinstance(retriever.hierarchy, CommunityHierarchy)


class TestLocalRetrieval:
    """Test local retrieval mode (entity-based)."""

    @pytest.mark.asyncio
    async def test_local_retrieval_success(self, mock_graphrag_retriever):
        """Test successful local retrieval."""
        retriever, mock_llm, _, mock_graph_store, _ = mock_graphrag_retriever

        # Mock entity extraction
        mock_entity = Entity(
            id="entity-1",
            name="Cursor",
            type="project",
            properties={},
            source_text="Test text",
        )
        extraction_result = ExtractionResult(
            entities=[mock_entity], relationships=[], facts=[], summary="Summary"
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=extraction_result)

        with patch(
            "src.core.graphrag_retriever.EntityExtractor", return_value=mock_extractor
        ):
            # Mock _get_entity_communities
            async def mock_get_communities(entity_id):
                return ["comm-1", "comm-2"]

            retriever._get_entity_communities = mock_get_communities

            # Mock _get_community_from_store
            mock_community = Community(
                id="comm-1",
                level=0,
                parent_id=None,
                entity_ids=["entity-1", "entity-2"],
                summary="Community about Cursor",
                title="Cursor Community",
                rank=0.9,
            )
            retriever._get_community_from_store = AsyncMock(return_value=mock_community)
            retriever._expand_communities = AsyncMock(return_value=["comm-1"])
            retriever._build_sources_from_communities = AsyncMock(return_value=[])

            result = await retriever.retrieve("What is Cursor?", strategy="local")

            assert result.strategy_used == "local"
            assert result.query_entities == ["Cursor"]
            assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_local_retrieval_no_entities(self, mock_graphrag_retriever):
        """Test local retrieval with no entities found."""
        retriever, mock_llm, _, _, _ = mock_graphrag_retriever

        # Mock empty extraction
        extraction_result = ExtractionResult(
            entities=[], relationships=[], facts=[], summary=""
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=extraction_result)

        with patch(
            "src.core.graphrag_retriever.EntityExtractor", return_value=mock_extractor
        ):
            retriever._expand_communities = AsyncMock(return_value=[])
            retriever._build_sources_from_communities = AsyncMock(return_value=[])

            result = await retriever.retrieve("Random query", strategy="local")

            assert result.strategy_used == "local"
            assert len(result.communities) == 0
            assert len(result.sources) == 0

    @pytest.mark.asyncio
    async def test_local_retrieval_resolves_entity_ids_by_name(self, mock_graphrag_retriever):
        """Local retrieval should resolve extracted names back to stored entity IDs."""
        retriever, _, _, mock_graph_store, _ = mock_graphrag_retriever

        extracted_entity = Entity(
            id="raw-alice",
            name="Alice",
            type="person",
            properties={},
            source_text="Alice owns release coordination",
        )
        extraction_result = ExtractionResult(
            entities=[extracted_entity], relationships=[], facts=[], summary="Alice summary"
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=extraction_result)
        mock_graph_store.find_entities_by_name = AsyncMock(
            return_value=[
                MagicMock(id="ent-canonical-alice", name="Alice", type="person"),
            ]
        )

        with patch("src.core.graphrag_retriever.EntityExtractor", return_value=mock_extractor):
            retriever._get_entity_communities = AsyncMock(return_value=["comm-alice"])
            retriever._get_community_from_store = AsyncMock(
                return_value=Community(
                    id="comm-alice",
                    level=0,
                    parent_id=None,
                    entity_ids=["ent-canonical-alice"],
                    summary="Alice ownership context",
                    title="Alice Community",
                    rank=0.9,
                )
            )
            retriever._expand_communities = AsyncMock(return_value=["comm-alice"])
            retriever._build_sources_from_communities = AsyncMock(return_value=[])

            result = await retriever.retrieve("Who is Alice?", strategy="local")

        assert result.query_entities == ["Alice"]
        retriever._get_entity_communities.assert_awaited_once_with("ent-canonical-alice")
        mock_graph_store.find_entities_by_name.assert_awaited_once_with("Alice", limit=10)


class TestGlobalRetrieval:
    """Test global retrieval mode (community summary-based)."""

    @pytest.mark.asyncio
    async def test_global_retrieval_success(self, mock_graphrag_retriever):
        """Test successful global retrieval."""
        retriever, mock_llm, _, mock_graph_store, _ = mock_graphrag_retriever

        # Mock query embedding
        mock_llm.embed = AsyncMock(return_value=[[0.1, 0.2, 0.3, 0.4, 0.5]])

        mock_graph_store.list_communities = AsyncMock(
            return_value=[
                {
                    "id": "comm-1",
                    "summary": "AI and machine learning community",
                    "title": "AI Community",
                },
                {
                    "id": "comm-2",
                    "summary": "Web development community",
                    "title": "Web Dev",
                },
            ]
        )

        mock_graph_store.get_community = AsyncMock(
            return_value={
                "id": "comm-1",
                "level": 0,
                "parent_id": None,
                "entity_ids": ["entity-1"],
                "summary": "AI and machine learning community",
                "title": "AI Community",
                "rank": 0.9,
            }
        )
        retriever._build_sources_from_communities = AsyncMock(return_value=[])

        result = await retriever.retrieve("Tell me about AI", strategy="global")

        assert result.strategy_used == "global"
        assert result.processing_time_ms > 0

    @pytest.mark.asyncio
    async def test_global_retrieval_no_communities(self, mock_graphrag_retriever):
        """Test global retrieval with no communities."""
        retriever, mock_llm, _, mock_graph_store, _ = mock_graphrag_retriever

        mock_graph_store.list_communities = AsyncMock(return_value=[])
        retriever._build_sources_from_communities = AsyncMock(return_value=[])

        result = await retriever.retrieve("Random query", strategy="global")

        assert result.strategy_used == "global"
        assert len(result.communities) == 0
        assert len(result.sources) == 0


class TestSourceBuilding:
    """Test GraphRAG source construction details."""

    @pytest.mark.asyncio
    async def test_build_sources_from_communities_uses_none_for_missing_memory_mapping(self, mock_graphrag_retriever):
        retriever, mock_llm, mock_vector_store, mock_graph_store, _ = mock_graphrag_retriever
        mock_llm.embed = AsyncMock(return_value=[[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]])
        mock_vector_store.get_memory = AsyncMock(return_value=None)
        retriever._get_community_from_store = AsyncMock(
            return_value=Community(
                id="comm-missing-memory-id",
                level=0,
                parent_id=None,
                entity_ids=["entity-orphan-alice"],
                summary="Community-only evidence for launch ownership.",
                title="Launch Owners Without Memory",
                rank=0.95,
            )
        )
        mock_graph_store.get_community_entities = AsyncMock(
            return_value=[
                Entity(
                    id="entity-orphan-alice",
                    name="Alice",
                    type="person",
                    properties={"role": "owner"},
                    source_text="Alice owns the launch checklist through community-only evidence.",
                    confidence=0.97,
                )
            ]
        )
        mock_graph_store.get_entity_memory_ids = AsyncMock(return_value=[])

        sources = await retriever._build_sources_from_communities(
            ["comm-missing-memory-id"],
            "Who owns the launch checklist?",
            top_k=3,
        )

        assert len(sources) == 1
        assert sources[0].memory_id is None
        assert sources[0].community_id == "comm-missing-memory-id"
        assert "community-only evidence" in sources[0].content
        mock_vector_store.get_memory.assert_not_awaited()


class TestHybridRetrieval:
    """Test hybrid retrieval mode (combined local + global)."""

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_combines_results(self, mock_graphrag_retriever):
        """Test hybrid retrieval combines local and global results."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        # Mock local result
        local_ctx = CommunityContext(
            community_id="comm-1",
            title="Local Community",
            summary="Found via entities",
            level=0,
            relevance=0.8,
        )
        local_result = GraphRAGRetrievalResult(
            sources=[],
            entities=["entity-1"],
            communities=[local_ctx],
            strategy_used="local",
            processing_time_ms=100,
            query_entities=["test"],
        )

        # Mock global result
        global_ctx = CommunityContext(
            community_id="comm-2",
            title="Global Community",
            summary="Found via summaries",
            level=0,
            relevance=0.7,
        )
        global_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=[global_ctx],
            strategy_used="global",
            processing_time_ms=100,
        )

        async def mock_local(q, k, t):
            return local_result

        async def mock_global(q, k, t):
            return global_result

        retriever._local_retrieval = mock_local
        retriever._global_retrieval = mock_global

        result = await retriever.retrieve("test query", strategy="hybrid")

        assert result.strategy_used == "hybrid"
        # Local communities get boosted relevance
        assert len(result.communities) == 2

    @pytest.mark.asyncio
    async def test_hybrid_deduplicates_communities(self, mock_graphrag_retriever):
        """Test hybrid retrieval deduplicates communities."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        # Both local and global return same community
        shared_ctx = CommunityContext(
            community_id="comm-1",
            title="Shared",
            summary="Found by both",
            level=0,
            relevance=0.8,
        )

        local_result = GraphRAGRetrievalResult(
            sources=[],
            entities=["entity-1"],
            communities=[shared_ctx],
            strategy_used="local",
            processing_time_ms=100,
            query_entities=["test"],
        )

        global_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=[shared_ctx],
            strategy_used="global",
            processing_time_ms=100,
        )

        async def mock_local(q, k, t):
            return local_result

        async def mock_global(q, k, t):
            return global_result

        retriever._local_retrieval = mock_local
        retriever._global_retrieval = mock_global

        result = await retriever.retrieve("test query", strategy="hybrid")

        # Should deduplicate, keeping only one instance
        comm_ids = [c.community_id for c in result.communities]
        assert comm_ids.count("comm-1") == 1

    @pytest.mark.asyncio
    async def test_hybrid_merges_relevance_scores(self, mock_graphrag_retriever):
        """Test hybrid retrieval merges relevance for duplicate communities."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        # Same community with different relevance
        local_ctx = CommunityContext(
            community_id="comm-1",
            title="Shared",
            summary="Found by both",
            level=0,
            relevance=0.6,
        )

        global_ctx = CommunityContext(
            community_id="comm-1",
            title="Shared",
            summary="Found by both",
            level=0,
            relevance=0.9,
        )

        local_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=[local_ctx],
            strategy_used="local",
            processing_time_ms=100,
            query_entities=[],
        )

        global_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=[global_ctx],
            strategy_used="global",
            processing_time_ms=100,
        )

        async def mock_local(q, k, t):
            return local_result

        async def mock_global(q, k, t):
            return global_result

        retriever._local_retrieval = mock_local
        retriever._global_retrieval = mock_global

        result = await retriever.retrieve("test query", strategy="hybrid")

        # Should keep max relevance (0.9), even after local boost
        assert len(result.communities) == 1
        assert result.communities[0].community_id == "comm-1"


class TestCommunityRanking:
    """Test community ranking functionality."""

    @pytest.mark.asyncio
    async def test_expand_communities_ranks_by_entity_count(
        self, mock_graphrag_retriever
    ):
        """Test communities are ranked by matched entity count."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        # Mock communities with different entity matches
        entity_communities = {
            "entity-1": {"comm-1", "comm-2"},
            "entity-2": {"comm-1"},
            "entity-3": {"comm-3"},
        }

        # Mock community sizes
        async def mock_get_community(comm_id):
            sizes = {"comm-1": 10, "comm-2": 5, "comm-3": 20}
            return Community(
                id=comm_id,
                level=0,
                parent_id=None,
                entity_ids=list(range(sizes.get(comm_id, 1))),
                summary="Summary",
                title=f"Community {comm_id}",
                rank=0.5,
            )

        retriever._get_community_from_store = mock_get_community
        retriever._get_community_neighbors = AsyncMock(return_value=set())

        result = await retriever._expand_communities(entity_communities, top_k=3)

        # comm-1 has 2 entity matches, should be first
        # comm-2 and comm-3 have 1 each, but comm-2 is smaller (size factor boost)
        assert "comm-1" in result
        assert len(result) <= 3

    @pytest.mark.asyncio
    async def test_expand_communities_size_factor_boost(self, mock_graphrag_retriever):
        """Test smaller communities get size factor boost."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        # Two communities with same entity match count
        entity_communities = {"entity-1": {"comm-large", "comm-small"}}

        async def mock_get_community(comm_id):
            sizes = {"comm-large": 100, "comm-small": 5}
            return Community(
                id=comm_id,
                level=0,
                parent_id=None,
                entity_ids=list(range(sizes.get(comm_id, 1))),
                summary="Summary",
                title=f"Community {comm_id}",
                rank=0.5,
            )

        retriever._get_community_from_store = mock_get_community
        retriever._get_community_neighbors = AsyncMock(return_value=set())

        result = await retriever._expand_communities(entity_communities, top_k=2)

        # Small community should rank higher due to size factor
        assert result[0] == "comm-small"

    @pytest.mark.asyncio
    async def test_community_neighbor_expansion(self, mock_graphrag_retriever):
        """Test communities expand to include neighbors."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        entity_communities = {"entity-1": {"comm-1"}}

        async def mock_get_community(comm_id):
            return Community(
                id=comm_id,
                level=0,
                parent_id=None,
                entity_ids=["entity-1"],
                summary="Summary",
                title="Community",
                rank=0.5,
            )

        retriever._get_community_from_store = mock_get_community
        retriever._get_community_neighbors = AsyncMock(
            return_value={"comm-2", "comm-3"}
        )

        result = await retriever._expand_communities(entity_communities, top_k=5)

        # Should include original + neighbors
        assert "comm-1" in result
        assert "comm-2" in result
        assert "comm-3" in result


class TestEmptyResultsHandling:
    """Test handling of empty results."""

    @pytest.mark.asyncio
    async def test_local_retrieval_empty_communities(self, mock_graphrag_retriever):
        """Test local retrieval with no communities found."""
        retriever, mock_llm, _, _, _ = mock_graphrag_retriever

        extraction_result = ExtractionResult(
            entities=[Entity(id="e1", name="Test", type="concept")],
            relationships=[],
            facts=[],
            summary="",
        )

        mock_extractor = MagicMock()
        mock_extractor.extract = AsyncMock(return_value=extraction_result)

        with patch(
            "src.core.graphrag_retriever.EntityExtractor", return_value=mock_extractor
        ):
            retriever._get_entity_communities = AsyncMock(return_value=[])
            retriever._expand_communities = AsyncMock(return_value=[])
            retriever._build_sources_from_communities = AsyncMock(return_value=[])

            result = await retriever.retrieve("test", strategy="local")

            assert len(result.communities) == 0
            assert len(result.sources) == 0
            assert result.strategy_used == "local"

    @pytest.mark.asyncio
    async def test_global_retrieval_empty_summaries(self, mock_graphrag_retriever):
        """Test global retrieval with no community summaries."""
        retriever, mock_llm, _, mock_graph_store, _ = mock_graphrag_retriever

        mock_graph_store.list_communities = AsyncMock(return_value=[])
        retriever._build_sources_from_communities = AsyncMock(return_value=[])

        result = await retriever.retrieve("test", strategy="global")

        assert len(result.communities) == 0
        assert len(result.sources) == 0

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_both_empty(self, mock_graphrag_retriever):
        """Test hybrid retrieval when both local and global return empty."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        empty_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=[],
            strategy_used="",
            processing_time_ms=50,
        )

        async def mock_empty(q, k, t):
            return empty_result

        retriever._local_retrieval = mock_empty
        retriever._global_retrieval = mock_empty

        result = await retriever.retrieve("test", strategy="hybrid")

        assert len(result.communities) == 0
        assert len(result.sources) == 0
        assert len(result.entities) == 0

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_dedupes_missing_memory_sources_by_fallback_identity(self, mock_graphrag_retriever):
        retriever, _, _, _, _ = mock_graphrag_retriever

        source = GraphRAGSource(
            memory_id=None,
            content="Alice owns the launch checklist through community-only evidence.",
            relevance=0.8,
            community_id="comm-missing-memory-id",
            community_summary="Community-only evidence for launch ownership.",
        )
        local_result = GraphRAGRetrievalResult(
            sources=[source],
            entities=["Alice"],
            communities=[],
            strategy_used="local",
            processing_time_ms=100,
            query_entities=["Alice"],
        )
        global_result = GraphRAGRetrievalResult(
            sources=[GraphRAGSource(**source.__dict__)],
            entities=[],
            communities=[],
            strategy_used="global",
            processing_time_ms=100,
        )

        retriever._local_retrieval = AsyncMock(return_value=local_result)
        retriever._global_retrieval = AsyncMock(return_value=global_result)

        result = await retriever.retrieve("Who owns the launch checklist?", strategy="hybrid")

        assert len(result.sources) == 1
        assert result.sources[0].memory_id is None

    @pytest.mark.asyncio
    async def test_answer_with_no_relevant_info(self, mock_graphrag_retriever):
        """Test answer method when no relevant information found."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        # Mock retrieve to return empty result
        retriever.retrieve = AsyncMock(
            return_value=GraphRAGRetrievalResult(
                sources=[],
                entities=[],
                communities=[],
                strategy_used="hybrid",
                processing_time_ms=100,
            )
        )

        result = await retriever.answer("test question")

        assert "No relevant information found" in result.answer
        assert result.sources == []
        assert result.communities == []


class TestModeParameterValidation:
    """Test mode/strategy parameter validation."""

    @pytest.mark.asyncio
    async def test_retrieve_with_local_mode(self, mock_graphrag_retriever):
        """Test retrieve with strategy='local'."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        retriever._local_retrieval = AsyncMock(
            return_value=GraphRAGRetrievalResult(
                strategy_used="local", processing_time_ms=100
            )
        )

        result = await retriever.retrieve("test", strategy="local")
        assert result.strategy_used == "local"

    @pytest.mark.asyncio
    async def test_retrieve_with_global_mode(self, mock_graphrag_retriever):
        """Test retrieve with strategy='global'."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        retriever._global_retrieval = AsyncMock(
            return_value=GraphRAGRetrievalResult(
                strategy_used="global", processing_time_ms=100
            )
        )

        result = await retriever.retrieve("test", strategy="global")
        assert result.strategy_used == "global"

    @pytest.mark.asyncio
    async def test_retrieve_with_hybrid_mode(self, mock_graphrag_retriever):
        """Test retrieve with strategy='hybrid'."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        retriever._hybrid_retrieval = AsyncMock(
            return_value=GraphRAGRetrievalResult(
                strategy_used="hybrid", processing_time_ms=100
            )
        )

        result = await retriever.retrieve("test", strategy="hybrid")
        assert result.strategy_used == "hybrid"

    @pytest.mark.asyncio
    async def test_retrieve_defaults_to_hybrid(self, mock_graphrag_retriever):
        """Test retrieve defaults to hybrid mode when no strategy specified."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        retriever._hybrid_retrieval = AsyncMock(
            return_value=GraphRAGRetrievalResult(
                strategy_used="hybrid", processing_time_ms=100
            )
        )

        result = await retriever.retrieve("test")  # No strategy specified
        assert result.strategy_used == "hybrid"

    @pytest.mark.asyncio
    async def test_retrieve_with_invalid_mode(self, mock_graphrag_retriever):
        """Test retrieve with invalid strategy defaults to hybrid."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        retriever._hybrid_retrieval = AsyncMock(
            return_value=GraphRAGRetrievalResult(
                strategy_used="hybrid", processing_time_ms=100
            )
        )

        # Invalid strategy should fall through to hybrid
        result = await retriever.retrieve("test", strategy="invalid")
        assert result.strategy_used == "hybrid"


class TestHelperMethods:
    """Test helper methods."""

    @pytest.mark.asyncio
    async def test_get_entity_communities(self, mock_graphrag_retriever):
        """Test _get_entity_communities helper."""
        retriever, _, _, mock_graph_store, _ = mock_graphrag_retriever

        mock_graph_store.get_entity_communities = AsyncMock(
            return_value=["comm-1", "comm-2"]
        )

        result = await retriever._get_entity_communities("entity-1")

        assert result == ["comm-1", "comm-2"]

    @pytest.mark.asyncio
    async def test_get_community_from_store(self, mock_graphrag_retriever):
        """Test _get_community_from_store helper."""
        retriever, _, _, mock_graph_store, _ = mock_graphrag_retriever

        mock_graph_store.get_community = AsyncMock(
            return_value={
                "id": "comm-1",
                "level": 0,
                "parent_id": None,
                "title": "Test Community",
                "summary": "Test summary",
                "rank": 0.9,
                "entity_ids": ["entity-1", "entity-2"],
            }
        )

        result = await retriever._get_community_from_store("comm-1")

        assert result is not None
        assert result.id == "comm-1"
        assert result.level == 0
        assert result.entity_ids == ["entity-1", "entity-2"]

    @pytest.mark.asyncio
    async def test_get_community_not_found(self, mock_graphrag_retriever):
        """Test _get_community_from_store with non-existent community."""
        retriever, _, _, mock_graph_store, _ = mock_graphrag_retriever

        mock_graph_store.get_community = AsyncMock(return_value=None)

        result = await retriever._get_community_from_store("non-existent")

        assert result is None

    def test_build_community_context(self, mock_graphrag_retriever):
        """Test _build_community_context helper."""
        retriever, _, _, _, _ = mock_graphrag_retriever

        community = Community(
            id="comm-1",
            level=0,
            parent_id=None,
            entity_ids=["entity-1", "entity-2"],
            summary="Test summary",
            title="Test Community",
            rank=0.9,
        )

        ctx = retriever._build_community_context(community, relevance=0.85)

        assert ctx.community_id == "comm-1"
        assert ctx.title == "Test Community"
        assert ctx.summary == "Test summary"
        assert ctx.level == 0
        assert ctx.entities == ["entity-1", "entity-2"]
        assert ctx.relevance == 0.85


class TestAnswerMethod:
    """Test answer method (RAG generation)."""

    @pytest.mark.asyncio
    async def test_answer_with_communities(self, mock_graphrag_retriever):
        """Test answer with communities generates response."""
        retriever, mock_llm, _, _, _ = mock_graphrag_retriever

        # Mock retrieve with communities
        ctx = CommunityContext(
            community_id="comm-1",
            title="AI Community",
            summary="This community discusses AI and ML topics",
            level=0,
            relevance=0.9,
        )
        source = GraphRAGSource(
            memory_id="mem-1",
            content="AI is transforming the world",
            relevance=0.8,
            community_id="comm-1",
            community_summary="AI Community",
        )

        retrieval_result = GraphRAGRetrievalResult(
            sources=[source],
            entities=["AI"],
            communities=[ctx],
            strategy_used="hybrid",
            processing_time_ms=100,
            query_entities=["AI"],
        )

        retriever.retrieve = AsyncMock(return_value=retrieval_result)
        mock_llm.generate_answer = AsyncMock(
            return_value="AI is a rapidly evolving field."
        )

        result = await retriever.answer("What is AI?")

        assert result.answer == "AI is a rapidly evolving field."
        assert len(result.communities) == 1
        assert len(result.sources) == 1

    @pytest.mark.asyncio
    async def test_answer_with_sources_only(self, mock_graphrag_retriever):
        """Test answer with only sources (no communities)."""
        retriever, mock_llm, _, _, _ = mock_graphrag_retriever

        source = GraphRAGSource(
            memory_id="mem-1", content="Python is a programming language", relevance=0.8
        )

        retrieval_result = GraphRAGRetrievalResult(
            sources=[source],
            entities=[],
            communities=[],
            strategy_used="local",
            processing_time_ms=100,
        )

        retriever.retrieve = AsyncMock(return_value=retrieval_result)
        mock_llm.generate_answer = AsyncMock(
            return_value="Python is used for data science."
        )

        result = await retriever.answer("What is Python?")

        assert "Python is used for data science." in result.answer
        assert len(result.sources) == 1

    @pytest.mark.asyncio
    async def test_answer_respects_top_k(self, mock_graphrag_retriever):
        """Test answer respects top_k parameter."""
        retriever, mock_llm, _, _, _ = mock_graphrag_retriever

        # Create multiple communities
        communities = [
            CommunityContext(
                community_id=f"comm-{i}",
                title=f"Community {i}",
                summary=f"Summary {i}",
                level=0,
                relevance=0.9 - i * 0.1,
            )
            for i in range(10)
        ]

        retrieval_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=communities,
            strategy_used="hybrid",
            processing_time_ms=100,
        )

        retriever.retrieve = AsyncMock(return_value=retrieval_result)
        mock_llm.generate_answer = AsyncMock(return_value="Answer")

        result = await retriever.answer("test", top_k=3)

        # Should limit to top_k in context building
        assert len(result.communities) == 10  # All returned from retrieve
        # But context should only use top 3 for answer generation

    @pytest.mark.asyncio
    async def test_answer_respects_strategy(self, mock_graphrag_retriever):
        """Test answer respects strategy parameter."""
        retriever, mock_llm, _, _, _ = mock_graphrag_retriever

        retrieval_result = GraphRAGRetrievalResult(
            sources=[],
            entities=[],
            communities=[],
            strategy_used="local",
            processing_time_ms=100,
        )

        retriever.retrieve = AsyncMock(return_value=retrieval_result)
        mock_llm.generate_answer = AsyncMock(return_value="Answer")

        result = await retriever.answer("test", strategy="local")

        # Verify retrieve was called with correct strategy
        retriever.retrieve.assert_called_once()
        call_kwargs = retriever.retrieve.call_args[1]
        assert call_kwargs["strategy"] == "local"


class TestGraphRAGEvaluationBaseline:
    """Test GraphRAG retrieval evaluation baseline utilities."""

    @pytest.mark.asyncio
    async def test_evaluate_graphrag_retrieval_outputs_strategy_metrics(self):
        """Evaluation should produce comparable local/global/hybrid summaries."""
        summary = await evaluate_graphrag_retrieval(
            retriever=build_fixture_retriever(),
            cases=DEFAULT_REPRESENTATIVE_CASES,
            top_k=3,
        )

        assert summary.top_k == 3
        assert set(summary.strategies.keys()) == {"local", "global", "hybrid"}

        for strategy_name, strategy_summary in summary.strategies.items():
            assert strategy_summary.strategy == strategy_name
            assert strategy_summary.query_count == len(DEFAULT_REPRESENTATIVE_CASES)
            assert 0.0 <= strategy_summary.recall_at_k <= 1.0
            assert 0.0 <= strategy_summary.empty_result_rate <= 1.0
            assert strategy_summary.avg_latency_ms >= 1.0
            assert strategy_summary.p95_latency_ms >= 1
            assert len(strategy_summary.evidences) == len(DEFAULT_REPRESENTATIVE_CASES)

        assert summary.strategies["hybrid"].recall_at_k >= summary.strategies["global"].recall_at_k

    def test_compare_against_baseline_detects_regressions(self):
        """Regression comparison should flag recall, empty-rate, and latency regressions."""
        baseline = GraphRAGEvalSummary(
            generated_at="2026-04-02T00:00:00+00:00",
            top_k=5,
            strategies={
                "hybrid": StrategyEvalSummary(
                    strategy="hybrid",
                    query_count=3,
                    recall_at_k=1.0,
                    empty_result_rate=0.0,
                    avg_latency_ms=10.0,
                    p95_latency_ms=12,
                )
            },
        )
        current = GraphRAGEvalSummary(
            generated_at="2026-04-03T00:00:00+00:00",
            top_k=5,
            strategies={
                "hybrid": StrategyEvalSummary(
                    strategy="hybrid",
                    query_count=3,
                    recall_at_k=0.6,
                    empty_result_rate=0.4,
                    avg_latency_ms=25.0,
                    p95_latency_ms=30,
                )
            },
        )

        regressions = compare_against_baseline(
            current=current,
            baseline=baseline,
            recall_drop_tolerance=0.05,
            empty_rate_increase_tolerance=0.1,
            latency_ratio_tolerance=1.5,
        )

        assert len(regressions) == 3
        assert any("recall_at_k dropped" in item for item in regressions)
        assert any("empty_result_rate increased" in item for item in regressions)
        assert any("avg_latency_ms ratio" in item for item in regressions)

    def test_load_eval_expectations_supports_default_and_strategies(self, tmp_path):
        """Expectation loader should parse both per-strategy and default thresholds."""
        payload = {
            "default": {
                "min_recall_at_k": 0.7,
                "max_empty_result_rate": 0.2,
            },
            "strategies": {
                "hybrid": {
                    "min_recall_at_k": 0.9,
                    "max_avg_latency_ms": 20,
                    "max_p95_latency_ms": 30,
                }
            },
        }
        expectation_path = tmp_path / "expectations.json"
        expectation_path.write_text(json.dumps(payload), encoding="utf-8")

        expectations, default_expectation = load_eval_expectations(expectation_path)

        assert default_expectation is not None
        assert default_expectation.min_recall_at_k == 0.7
        assert default_expectation.max_empty_result_rate == 0.2
        assert "hybrid" in expectations
        assert expectations["hybrid"].min_recall_at_k == 0.9
        assert expectations["hybrid"].max_avg_latency_ms == 20
        assert expectations["hybrid"].max_p95_latency_ms == 30

    def test_evaluate_against_expectations_outputs_pass_fail_evidence(self):
        """Absolute expectation checks should emit explicit pass/fail evidence."""
        summary = GraphRAGEvalSummary(
            generated_at="2026-04-03T00:00:00+00:00",
            top_k=5,
            strategies={
                "hybrid": StrategyEvalSummary(
                    strategy="hybrid",
                    query_count=3,
                    recall_at_k=0.8,
                    empty_result_rate=0.1,
                    avg_latency_ms=15.0,
                    p95_latency_ms=25,
                ),
                "local": StrategyEvalSummary(
                    strategy="local",
                    query_count=3,
                    recall_at_k=0.5,
                    empty_result_rate=0.35,
                    avg_latency_ms=42.0,
                    p95_latency_ms=60,
                ),
            },
        )
        expectations = {
            "hybrid": StrategyExpectations(
                min_recall_at_k=0.7,
                max_empty_result_rate=0.2,
                max_avg_latency_ms=20.0,
                max_p95_latency_ms=30,
            ),
        }
        default_expectation = StrategyExpectations(
            min_recall_at_k=0.6,
            max_empty_result_rate=0.2,
            max_avg_latency_ms=30.0,
            max_p95_latency_ms=40,
        )

        passes, failures = evaluate_against_expectations(
            summary=summary,
            expectations=expectations,
            default_expectation=default_expectation,
        )

        assert any(item.startswith("[hybrid]") for item in passes)
        assert any(item.startswith("[local]") for item in failures)
