"""
GraphRAG Retriever Module
Dual-layer retrieval combining local entity-based and global community-based search
"""

import time
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

from src.core.entity_extractor import EntityExtractor
from src.core.llm_manager import LLMManager
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.core.models.community import Community, CommunityHierarchy


# ============================================
# Data Models
# ============================================


@dataclass
class CommunityContext:
    """Community context for retrieval"""

    community_id: str
    title: str
    summary: str
    level: int
    entities: List[str] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    relevance: float = 0.0


@dataclass
class GraphRAGSource:
    """Source document with community context"""

    memory_id: Optional[str]
    content: str
    relevance: float
    entities: List[str] = field(default_factory=list)
    community_id: Optional[str] = None
    community_summary: Optional[str] = None


@dataclass
class GraphRAGRetrievalResult:
    """GraphRAG Retrieval Result"""

    answer: str = ""
    sources: List[GraphRAGSource] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    communities: List[CommunityContext] = field(default_factory=list)
    strategy_used: str = ""
    processing_time_ms: int = 0
    query_entities: List[str] = field(default_factory=list)


from src.core.graphrag_retriever_flows import (
    build_sources_from_communities_flow,
    expand_communities_flow,
    run_global_retrieval,
    run_hybrid_retrieval,
    run_local_retrieval,
    search_community_summaries_flow,
)
from src.core.graphrag_retriever_helpers import (
    build_answer_context,
    build_community_context,
    community_record_to_model,
)


# ============================================
# GraphRAG Retriever
# ============================================


class GraphRAGRetriever:
    """
    GraphRAG Retriever
    Dual-layer retrieval combining local (entity-based) and global (community-based) search
    """

    def __init__(
        self,
        llm_manager: LLMManager,
        vector_store: VectorStore,
        graph_store: GraphStore,
        hierarchy: Optional[CommunityHierarchy] = None,
    ):
        self.llm = llm_manager
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.hierarchy = hierarchy or CommunityHierarchy()

        # Cache for community summaries as embeddings
        self._summary_embeddings: Dict[str, List[float]] = {}

    def _create_entity_extractor(self) -> EntityExtractor:
        """Create the entity extractor used by local retrieval."""
        return EntityExtractor(self.llm)

    async def retrieve(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        include_sources: bool = True,
    ) -> GraphRAGRetrievalResult:
        """
        Main retrieval entry point with mode selection

        Args:
            query: Search query
            strategy: Retrieval strategy - "local", "global", or "hybrid"
            top_k: Number of results to return
            include_sources: Whether to include detailed sources

        Returns:
            GraphRAGRetrievalResult with context and community information
        """
        start_time = time.time()

        if strategy == "local":
            return await self._local_retrieval(query, top_k, start_time)
        elif strategy == "global":
            return await self._global_retrieval(query, top_k, start_time)
        else:  # hybrid
            return await self._hybrid_retrieval(query, top_k, start_time)

    async def _local_retrieval(
        self, query: str, top_k: int, start_time: float
    ) -> GraphRAGRetrievalResult:
        """Run local entity-driven retrieval."""
        return await run_local_retrieval(self, query, top_k, start_time)

    async def _global_retrieval(
        self, query: str, top_k: int, start_time: float
    ) -> GraphRAGRetrievalResult:
        """Run global community-summary retrieval."""
        return await run_global_retrieval(self, query, top_k, start_time)

    async def _hybrid_retrieval(
        self, query: str, top_k: int, start_time: float
    ) -> GraphRAGRetrievalResult:
        """Run hybrid retrieval."""
        return await run_hybrid_retrieval(self, query, top_k, start_time)

    # ========================================
    # Helper Methods
    # ========================================

    async def _get_entity_communities(self, entity_id: str) -> List[str]:
        """Get community IDs that contain an entity"""
        return await self.graph_store.get_entity_communities(entity_id)

    async def _resolve_query_entity_ids(self, entity) -> List[str]:
        """Resolve extracted entity hints to stored GraphStore entity IDs."""
        candidate_ids: List[str] = []

        raw_id = getattr(entity, "id", None)
        if raw_id:
            stored_entity = await self.graph_store.get_entity(raw_id)
            if stored_entity is not None:
                candidate_ids.append(raw_id)

        raw_name = getattr(entity, "name", None)
        if raw_name:
            matched_entities = await self.graph_store.find_entities_by_name(raw_name, limit=10)
            for matched in matched_entities:
                if matched.id not in candidate_ids:
                    candidate_ids.append(matched.id)

        if candidate_ids:
            return candidate_ids
        if raw_id:
            return [raw_id]
        return []

    async def _get_community_from_store(self, community_id: str) -> Optional[Community]:
        """Get a Community object from GraphStore."""
        record = await self.graph_store.get_community(
            community_id,
            include_entity_ids=True,
        )
        return community_record_to_model(record)

    def _build_community_context(
        self, community: Community, relevance: float = 0.8
    ) -> CommunityContext:
        """Build CommunityContext from Community object"""
        return build_community_context(community, relevance)

    async def _expand_communities(
        self, entity_communities: Dict[str, Set[str]], top_k: int
    ) -> List[str]:
        """Expand matched communities with neighboring communities."""
        return await expand_communities_flow(self, entity_communities, top_k)

    async def _get_community_neighbors(self, community_id: str) -> Set[str]:
        """Find neighboring communities via inter-community entity relationships"""
        return set(await self.graph_store.get_community_neighbors(community_id))

    async def _search_community_summaries(
        self, query_embedding: List[float], top_k: int
    ) -> List[tuple[str, float]]:
        """Vector search over community summaries."""
        return await search_community_summaries_flow(self, query_embedding, top_k)

    async def _build_sources_from_communities(
        self, community_ids: List[str], query: str, top_k: int
    ) -> List[GraphRAGSource]:
        """Build source list from community entities."""
        return await build_sources_from_communities_flow(self, community_ids, query, top_k)

    async def answer(
        self,
        question: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        include_sources: bool = True,
    ) -> GraphRAGRetrievalResult:
        """
        Answer a question using retrieved community context

        Args:
            question: User's question
            strategy: Retrieval strategy (local/global/hybrid)
            top_k: Number of communities to use
            include_sources: Whether to include source references

        Returns:
            GraphRAGRetrievalResult with generated answer
        """
        retrieval_result = await self.retrieve(
            question,
            strategy=strategy,
            top_k=top_k,
            include_sources=include_sources,
        )

        if not retrieval_result.communities and not retrieval_result.sources:
            retrieval_result.answer = (
                "No relevant information found in the knowledge graph."
            )
            return retrieval_result

        context = build_answer_context(retrieval_result)

        # Generate answer using LLM
        answer = await self.llm.generate_answer(context, question)
        retrieval_result.answer = answer

        return retrieval_result
