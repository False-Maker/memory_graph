"""Query/admin operations for VectorStore."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.core.vector_store_models import SearchResult
from src.core.vector_store_runtime import search_documents


class VectorStoreQueryOps:
    """Own search, stats, and admin/runtime behavior for VectorStore."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None,
    ) -> List[SearchResult]:
        """Vector similarity search."""
        index = self._store._get_index()
        if index.ntotal == 0:
            return []

        return search_documents(
            index=index,
            documents=self._store._state.documents,
            idx_to_id=self._store._state.idx_to_id,
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )

    async def search_by_text(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Search by text."""
        return await self.search(query_embedding, top_k)

    async def get_count(self) -> int:
        """Get total memory count."""
        self._store._ensure_loaded()
        return len(self._store._state.documents)

    async def clear_all(self) -> bool:
        """Clear all memories."""
        state = self._store._state
        state.index = self._store._create_index()
        state.documents = {}
        state.id_to_idx = {}
        state.idx_to_id = {}
        state.next_vector_id = 1
        self._store._save_index()
        return True

    async def rebuild_index(self) -> int:
        """Rebuild the FAISS index from persisted documents."""
        self._store._ensure_loaded()
        self._store._rebuild_index_from_documents()
        self._store._state.index_dimension_mismatch = False
        return self._store._state.index.ntotal if self._store._state.index is not None else 0

    async def reembed_all(
        self,
        embed_texts,
        batch_size: int = 32,
    ) -> Dict[str, int]:
        """Regenerate embeddings for all documents and rebuild the index."""
        self._store._ensure_loaded()
        all_docs = list(self._store._state.documents.values())
        updated = 0

        for batch_start in range(0, len(all_docs), batch_size):
            batch_docs = all_docs[batch_start : batch_start + batch_size]
            texts = [doc.content for doc in batch_docs]
            embeddings = await embed_texts(texts)
            for doc, embedding in zip(batch_docs, embeddings):
                doc.embedding = embedding
                updated += 1

        rebuilt = await self.rebuild_index()
        return {
            "documents": len(all_docs),
            "reembedded": updated,
            "indexed": rebuilt,
        }

    async def get_index_state(self) -> Dict[str, Any]:
        """Return runtime information about the current index state."""
        self._store._ensure_loaded()
        index = self._store._get_index()
        return {
            "configured_dimension": self._store.dimension,
            "loaded_index_dimension": self._store._state.loaded_index_dimension,
            "active_index_dimension": getattr(index, "d", None),
            "dimension_mismatch": self._store._state.index_dimension_mismatch,
            "indexed_documents": index.ntotal,
            "stored_documents": len(self._store._state.documents),
        }

    async def close(self):
        """Close and save."""
        self._store._save_index()

    async def test_connection(self) -> bool:
        """Test connection."""
        try:
            self._store._get_index()
            return True
        except Exception:
            return False
