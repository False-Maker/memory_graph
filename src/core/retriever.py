"""
Retriever compatibility layer.

Historically this module owned all retrieval orchestration. New callers should
prefer ``RetrievalFacade`` directly; ``Retriever`` remains as a thin shim for
existing imports and route wiring.
"""

from src.core.graph_store import GraphStore
from src.core.llm_manager import LLMManager
from src.core.retrieval_facade import RetrievalFacade, RetrievalResult, Source
from src.core.vector_store import VectorStore


class Retriever:
    """Compatibility shim that delegates to the unified retrieval facade."""

    def __init__(
        self,
        llm_manager: LLMManager,
        vector_store: VectorStore,
        graph_store: GraphStore
    ):
        self.llm = llm_manager
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.facade = RetrievalFacade(llm_manager, vector_store, graph_store)

    async def search(
        self,
        query: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        include_sources: bool = True,
        layer: str = "auto",
        layer_budget_override: int | None = None,
    ) -> RetrievalResult:
        """Search memories through the unified retrieval facade."""

        return await self.facade.search(
            query,
            strategy=strategy,
            top_k=top_k,
            include_sources=include_sources,
            **(
                {}
                if layer == "auto" and layer_budget_override is None
                else {
                    "layer": layer,
                    "layer_budget_override": layer_budget_override,
                }
            ),
        )

    async def _vector_search(self, query: str, top_k: int, start_time: float) -> RetrievalResult:
        """Compatibility wrapper for tests that still touch legacy internals."""

        return await self.facade._vector_search(query, top_k, start_time)

    async def _graph_search(self, query: str, top_k: int, start_time: float) -> RetrievalResult:
        """Compatibility wrapper for tests that still touch legacy internals."""

        return await self.facade._graph_search(query, top_k, start_time)

    async def _hybrid_search(self, query: str, top_k: int, start_time: float) -> RetrievalResult:
        """Compatibility wrapper for tests that still touch legacy internals."""

        return await self.facade._hybrid_search(query, top_k, start_time)

    async def answer(
        self,
        question: str,
        strategy: str = "hybrid",
        top_k: int = 5,
        include_sources: bool = True,
        layer: str = "auto",
        layer_budget_override: int | None = None,
    ) -> RetrievalResult:
        """Answer a question through the unified retrieval facade."""

        return await self.facade.answer(
            question,
            strategy=strategy,
            top_k=top_k,
            include_sources=include_sources,
            **(
                {}
                if layer == "auto" and layer_budget_override is None
                else {
                    "layer": layer,
                    "layer_budget_override": layer_budget_override,
                }
            ),
        )
