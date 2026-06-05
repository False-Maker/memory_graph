"""
Unified retrieval facade.

This module normalizes public retrieval strategies onto a single orchestration
surface so API routes can progressively converge on one entry point while
legacy callers keep using ``Retriever``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from src.core.entity_extractor import EntityExtractor
from src.core.graph_store import GraphStore
from src.core.graphrag_retriever import CommunityContext, GraphRAGRetriever
from src.core.llm_manager import LLMManager
from src.core.memory_contract import metadata_contract_view
from src.core.memory_layers import (
    MemoryLayerRequest,
    MemoryLayerResult,
    append_layer_fallback,
    finalize_memory_layer,
    resolve_memory_layer,
)
from src.core.vector_store import VectorStore
from src.core.config import get_settings


RetrievalBackend = Literal["legacy", "graphrag"]


@dataclass(frozen=True)
class RetrievalPlan:
    """Resolved execution plan for a public retrieval strategy."""

    requested_strategy: str
    normalized_strategy: str
    backend: RetrievalBackend
    execution_strategy: str


@dataclass
class Source:
    """Normalized source document."""

    memory_id: Optional[str]
    content: str
    relevance: float
    entities: list[str] = field(default_factory=list)
    community_id: Optional[str] = None
    community_summary: Optional[str] = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Unified retrieval result across legacy and GraphRAG backends."""

    answer: str = ""
    sources: list[Source] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    communities: list[CommunityContext] = field(default_factory=list)
    strategy_used: str = ""
    backend_used: RetrievalBackend = "legacy"
    query_entities: list[str] = field(default_factory=list)
    processing_time_ms: int = 0
    layer_requested: str = "auto"
    layer_used: str = "l2"
    layer_fallback_chain: list[str] = field(default_factory=list)
    context_token_estimate: int = 0
    layer_build_duration_ms: int = 0
    layer_warnings: list[str] = field(default_factory=list)
    layer_budget_max_tokens: int = 0
    layer_context_items: list[Any] = field(default_factory=list)


_STRATEGY_ALIASES: dict[str, tuple[RetrievalBackend, str]] = {
    "vector": ("legacy", "vector"),
    "graph": ("legacy", "graph"),
    "hybrid": ("legacy", "hybrid"),
    "graphrag": ("graphrag", "hybrid"),
    "local": ("graphrag", "local"),
    "global": ("graphrag", "global"),
    "graphrag_hybrid": ("graphrag", "hybrid"),
    "graphrag_local": ("graphrag", "local"),
    "graphrag_global": ("graphrag", "global"),
}
_DEFAULT_PLAN = ("legacy", "hybrid")


def resolve_retrieval_strategy(strategy: Optional[str]) -> RetrievalPlan:
    """Map a public strategy string onto a backend-specific execution plan."""

    requested_strategy = strategy if isinstance(strategy, str) else "hybrid"
    normalized_strategy = requested_strategy.strip().lower() or "hybrid"
    backend, execution_strategy = _STRATEGY_ALIASES.get(
        normalized_strategy,
        _DEFAULT_PLAN,
    )
    return RetrievalPlan(
        requested_strategy=requested_strategy,
        normalized_strategy=normalized_strategy,
        backend=backend,
        execution_strategy=execution_strategy,
    )


class RetrievalFacade:
    """Unified retrieval entry point for legacy and GraphRAG flows."""

    def __init__(
        self,
        llm_manager: LLMManager,
        vector_store: VectorStore,
        graph_store: GraphStore,
        graphrag_retriever: Optional[GraphRAGRetriever] = None,
    ):
        self.llm = llm_manager
        self.vector_store = vector_store
        self.graph_store = graph_store
        self._graphrag_retriever = graphrag_retriever

    def resolve_strategy(self, strategy: Optional[str]) -> RetrievalPlan:
        """Expose strategy resolution for callers and focused tests."""

        return resolve_retrieval_strategy(strategy)

    def _get_graphrag_retriever(self) -> GraphRAGRetriever:
        """Lazily build the GraphRAG retriever only when needed."""

        if self._graphrag_retriever is None:
            self._graphrag_retriever = GraphRAGRetriever(
                self.llm,
                self.vector_store,
                self.graph_store,
            )
        return self._graphrag_retriever

    def _resolve_memory_layer(
        self,
        *,
        layer: Optional[str],
        strategy_plan: RetrievalPlan,
        layer_budget_override: Optional[int],
    ) -> MemoryLayerResult:
        return resolve_memory_layer(
            MemoryLayerRequest(
                requested_layer=str(layer or "auto"),
                strategy_plan=strategy_plan,
                budget_override=layer_budget_override,
            ),
            settings=get_settings(),
        )

    async def _build_l0_result(self) -> RetrievalResult:
        settings = get_settings()
        profile_text = (settings.memory_layers.identity.profile_text or "").strip()
        sources: list[Source] = []
        if profile_text:
            sources.append(
                Source(
                    memory_id=None,
                    content=profile_text,
                    relevance=1.0,
                    entities=[],
                    metadata={
                        "source": "memory_layer",
                        "record_type": "identity_profile",
                        "title": "Identity Profile",
                        "summary": profile_text[:160],
                    },
                )
            )
        return RetrievalResult(
            sources=sources,
            entities=[],
            communities=[],
            strategy_used="memory_layer_l0",
            backend_used="legacy",
        )

    async def _build_l1_result(self, *, top_k: int) -> RetrievalResult:
        settings = get_settings()
        l1_settings = settings.memory_layers.l1
        pinned_limit = max(0, int(getattr(l1_settings, "max_pinned_memories", 0) or 0))
        communities_limit = max(0, int(getattr(l1_settings, "max_communities", 0) or 0))
        entities_limit = max(0, int(getattr(l1_settings, "max_entities", 0) or 0))

        sources: list[Source] = []
        communities: list[CommunityContext] = []
        entity_names: list[str] = []

        if pinned_limit > 0:
            all_memories = await self.vector_store.get_memories(limit=None, offset=0)
            pinned_memories = []
            for memory in all_memories:
                metadata = metadata_contract_view(getattr(memory, "metadata", None) or {})
                if metadata.get("pinned") is True:
                    pinned_memories.append(memory)
            for memory in pinned_memories[:pinned_limit]:
                metadata = metadata_contract_view(getattr(memory, "metadata", None) or {})
                sources.append(
                    Source(
                        memory_id=memory.id,
                        content=memory.content,
                        relevance=0.97,
                        entities=[],
                        metadata=metadata,
                    )
                )

        if communities_limit > 0:
            raw_communities = await self.graph_store.list_communities(
                level=None,
                limit=communities_limit,
                offset=0,
                require_summary=True,
                include_entity_ids=True,
                order_by="rank_desc",
            )
            for community in raw_communities:
                summary = str(community.get("summary") or "").strip()
                if not summary:
                    continue
                community_context = CommunityContext(
                    community_id=str(community["id"]),
                    title=str(community.get("title") or ""),
                    summary=summary,
                    level=int(community.get("level", 0) or 0),
                    entities=list(community.get("entity_ids") or []),
                    relevance=float(community.get("rank", 0.0) or 0.0),
                )
                communities.append(community_context)
                sources.append(
                    Source(
                        memory_id=None,
                        content=summary,
                        relevance=float(community.get("rank", 0.9) or 0.9),
                        entities=[],
                        community_id=community_context.community_id,
                        community_summary=summary,
                        metadata={
                            "source": "memory_layer",
                            "record_type": "essential_community",
                            "title": community_context.title,
                            "summary": summary,
                        },
                    )
                )

        if entities_limit > 0:
            raw_entities = await self.graph_store.query_entities(limit=entities_limit, offset=0)
            sorted_entities = sorted(
                list(raw_entities),
                key=lambda entity: (
                    float(getattr(entity, "confidence", 0.0) or 0.0),
                    str(getattr(entity, "created_at", "")),
                ),
                reverse=True,
            )
            for entity in sorted_entities[:entities_limit]:
                entity_names.append(str(entity.name))
                summary = str(entity.source_text or f"{entity.name} ({entity.type})").strip()
                sources.append(
                    Source(
                        memory_id=None,
                        content=summary,
                        relevance=float(getattr(entity, "confidence", 1.0) or 1.0),
                        entities=[str(entity.name)],
                        metadata={
                            "source": "memory_layer",
                            "record_type": "essential_entity",
                            "title": str(entity.name),
                            "summary": summary,
                        },
                    )
                )

        return RetrievalResult(
            sources=sources[: max(top_k, len(sources))],
            entities=entity_names,
            communities=communities,
            strategy_used="memory_layer_l1",
            backend_used="legacy",
        )

    async def _execute_search_plan(
        self,
        *,
        query: str,
        plan: RetrievalPlan,
        top_k: int,
        include_sources: bool,
    ) -> RetrievalResult:
        start_time = time.time()

        if plan.backend == "graphrag":
            result = await self._get_graphrag_retriever().retrieve(
                query=query,
                strategy=plan.execution_strategy,
                top_k=top_k,
                include_sources=include_sources,
            )
            return self._map_graphrag_result(result, plan)

        if plan.execution_strategy == "vector":
            return await self._vector_search(query, top_k, start_time)
        if plan.execution_strategy == "graph":
            return await self._graph_search(query, top_k, start_time)
        return await self._hybrid_search(query, top_k, start_time)

    @staticmethod
    def _apply_layer_metadata(
        result: RetrievalResult,
        layer_result: MemoryLayerResult,
        *,
        layer_build_duration_ms: int,
    ) -> RetrievalResult:
        finalized_layer = finalize_memory_layer(
            layer_result,
            sources=result.sources,
            communities=result.communities,
        )
        result.layer_requested = finalized_layer.requested_layer
        result.layer_used = finalized_layer.resolved_layer
        result.layer_fallback_chain = list(finalized_layer.fallback_chain)
        result.context_token_estimate = finalized_layer.token_estimate
        result.layer_build_duration_ms = max(0, layer_build_duration_ms)
        result.layer_warnings = list(finalized_layer.diagnostics.warnings)
        result.layer_budget_max_tokens = finalized_layer.token_budget.max_tokens
        result.layer_context_items = list(finalized_layer.context_items)
        return result

    async def search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        include_sources: bool = True,
        layer: str = "auto",
        layer_budget_override: Optional[int] = None,
    ) -> RetrievalResult:
        """Retrieve matching memories through the resolved backend."""
        plan = self.resolve_strategy(strategy)
        layer_started_at = time.perf_counter()
        layer_result = self._resolve_memory_layer(
            layer=layer,
            strategy_plan=plan,
            layer_budget_override=layer_budget_override,
        )

        if layer_result.resolved_layer == "l0":
            return self._apply_layer_metadata(
                await self._build_l0_result(),
                layer_result,
                layer_build_duration_ms=int((time.perf_counter() - layer_started_at) * 1000),
            )
        if layer_result.resolved_layer == "l1":
            return self._apply_layer_metadata(
                await self._build_l1_result(top_k=top_k),
                layer_result,
                layer_build_duration_ms=int((time.perf_counter() - layer_started_at) * 1000),
            )

        execution_plan = plan
        if layer_result.resolved_layer == "l3" and plan.backend == "legacy":
            execution_plan = RetrievalPlan(
                requested_strategy=plan.requested_strategy,
                normalized_strategy=plan.normalized_strategy,
                backend="graphrag",
                execution_strategy="hybrid",
            )

        result = await self._execute_search_plan(
            query=query,
            plan=execution_plan,
            top_k=top_k,
            include_sources=include_sources,
        )

        if (
            layer_result.requested_layer == "auto"
            and layer_result.resolved_layer == "l2"
            and not result.sources
        ):
            append_layer_fallback(layer_result, "l3")
            fallback_plan = RetrievalPlan(
                requested_strategy=plan.requested_strategy,
                normalized_strategy=plan.normalized_strategy,
                backend="graphrag",
                execution_strategy="hybrid",
            )
            result = await self._execute_search_plan(
                query=query,
                plan=fallback_plan,
                top_k=top_k,
                include_sources=include_sources,
            )

        return self._apply_layer_metadata(
            result,
            layer_result,
            layer_build_duration_ms=int((time.perf_counter() - layer_started_at) * 1000),
        )

    async def answer(
        self,
        question: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        include_sources: bool = True,
        layer: str = "auto",
        layer_budget_override: Optional[int] = None,
    ) -> RetrievalResult:
        """Generate an answer using the resolved retrieval backend."""

        retrieval_result = await self.search(
            question,
            strategy=strategy,
            top_k=top_k,
            include_sources=include_sources,
            layer=layer,
            layer_budget_override=layer_budget_override,
        )

        if not retrieval_result.sources:
            retrieval_result.answer = "No relevant memories found."
            return retrieval_result

        context = "\n\n".join(
            f"[Source {index + 1}]: {source.content}"
            for index, source in enumerate(retrieval_result.sources)
        )

        retrieval_result.answer = await self.llm.generate_answer(context, question)
        return retrieval_result

    async def _vector_search(
        self,
        query: str,
        top_k: int,
        start_time: float,
    ) -> RetrievalResult:
        """Run legacy vector-only retrieval."""

        embeddings = await self.llm.embed([query])
        query_embedding = embeddings[0]

        results = await self.vector_store.search(query_embedding=query_embedding, top_k=top_k)
        sources = [
            Source(
                memory_id=item.id,
                content=item.content,
                relevance=item.relevance,
                metadata=metadata_contract_view(getattr(item, "metadata", None) or {}),
            )
            for item in results
        ]

        return RetrievalResult(
            sources=sources,
            strategy_used="vector",
            backend_used="legacy",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )

    async def _graph_search(
        self,
        query: str,
        top_k: int,
        start_time: float,
    ) -> RetrievalResult:
        """Run legacy entity-neighbor retrieval."""

        extractor = EntityExtractor(self.llm)
        extraction = await extractor.extract(query)

        all_entities: list[str] = []
        matched_memories: list[dict[str, object]] = []

        for entity in extraction.entities:
            graph_entity = await self.graph_store.get_entity(entity.id)
            if graph_entity is None:
                continue

            all_entities.append(entity.name)
            neighbors = await self.graph_store.get_neighbors(entity.id, depth=2)
            for neighbor in neighbors:
                nodes = neighbor.get("nodes")
                if isinstance(nodes, list):
                    for node in nodes:
                        source_text = node.get("source_text")
                        if source_text:
                            matched_memories.append(
                                {
                                    "id": node.get("id"),
                                    "content": source_text,
                                    "entities": all_entities.copy(),
                                }
                            )
                    continue

                source_text = neighbor.get("source_text")
                if source_text:
                    matched_memories.append(
                        {
                            "id": neighbor.get("id"),
                            "content": source_text,
                            "entities": all_entities.copy(),
                        }
                    )
                    continue

                fallback_name = neighbor.get("name")
                if fallback_name:
                    node_type = neighbor.get("type")
                    content = str(fallback_name)
                    if node_type:
                        content = f"{content} ({node_type})"
                    matched_memories.append(
                        {
                            "id": None,
                            "content": content,
                            "entities": all_entities.copy(),
                        }
                    )

        seen_ids: set[object] = set()
        unique_memories: list[dict[str, object]] = []
        for memory in matched_memories:
            memory_id = memory["id"]
            if memory_id in seen_ids:
                continue
            seen_ids.add(memory_id)
            unique_memories.append(memory)

        sources = [
            Source(
                memory_id=str(memory["id"]) if memory["id"] is not None else None,
                content=str(memory["content"]),
                relevance=0.8,
                entities=list(memory.get("entities", [])),
                metadata={},
            )
            for memory in unique_memories[:top_k]
        ]

        return RetrievalResult(
            sources=sources,
            entities=all_entities,
            strategy_used="graph",
            backend_used="legacy",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )

    async def _hybrid_search(
        self,
        query: str,
        top_k: int,
        start_time: float,
    ) -> RetrievalResult:
        """Run legacy hybrid retrieval by merging vector and graph matches."""

        vector_result = await self._vector_search(query, top_k * 2, start_time)
        graph_result = await self._graph_search(query, top_k * 2, start_time)

        seen_ids: set[Optional[str]] = set()
        merged_sources: list[Source] = []

        for source in vector_result.sources:
            if source.memory_id in seen_ids:
                continue
            seen_ids.add(source.memory_id)
            merged_sources.append(source)

        for source in graph_result.sources:
            if source.memory_id in seen_ids:
                continue
            seen_ids.add(source.memory_id)
            merged_sources.append(source)

        return RetrievalResult(
            sources=merged_sources[:top_k],
            entities=list(set(vector_result.entities + graph_result.entities)),
            strategy_used="hybrid",
            backend_used="legacy",
            processing_time_ms=int((time.time() - start_time) * 1000),
        )

    def _map_graphrag_result(
        self,
        result,
        plan: RetrievalPlan,
    ) -> RetrievalResult:
        """Normalize GraphRAG results onto the shared result model."""

        return RetrievalResult(
            answer=getattr(result, "answer", ""),
            sources=[
                Source(
                    memory_id=getattr(source, "memory_id", None),
                    content=source.content,
                    relevance=source.relevance,
                    entities=list(getattr(source, "entities", [])),
                    community_id=getattr(source, "community_id", None),
                    community_summary=getattr(source, "community_summary", None),
                    metadata=metadata_contract_view(getattr(source, "metadata", None) or {}),
                )
                for source in getattr(result, "sources", [])
            ],
            entities=list(getattr(result, "entities", [])),
            communities=list(getattr(result, "communities", [])),
            strategy_used=getattr(result, "strategy_used", "") or plan.execution_strategy,
            backend_used=plan.backend,
            query_entities=list(getattr(result, "query_entities", [])),
            processing_time_ms=getattr(result, "processing_time_ms", 0),
        )
