"""Document CRUD operations for VectorStore."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import faiss
import numpy as np

from src.core.vector_store_models import MemoryDocument


class VectorStoreDocumentOps:
    """Own persisted document CRUD behavior for VectorStore."""

    def __init__(self, store: Any) -> None:
        self._store = store

    async def add_memory(
        self,
        memory_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a memory document."""
        return await self.upsert_memory(memory_id, content, embedding, metadata)

    async def upsert_memory(
        self,
        memory_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create or replace a memory document and its vector."""
        state = self._store._state
        index = self._store._get_index()

        existing_vector_id = state.id_to_idx.get(memory_id)
        if existing_vector_id is not None:
            index.remove_ids(np.array([existing_vector_id], dtype=np.int64))
            state.idx_to_id.pop(existing_vector_id, None)

        vec = np.array([embedding], dtype=np.float32)
        faiss.normalize_L2(vec)

        vector_id = state.next_vector_id
        state.next_vector_id += 1
        index.add_with_ids(vec, np.array([vector_id], dtype=np.int64))

        state.id_to_idx[memory_id] = vector_id
        state.idx_to_id[vector_id] = memory_id

        doc = MemoryDocument(
            id=memory_id,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
        )
        state.documents[memory_id] = doc
        self._store._save_index()
        return memory_id

    async def get_memory(self, memory_id: str) -> Optional[MemoryDocument]:
        """Get memory by ID."""
        self._store._ensure_loaded()
        return self._store._state.documents.get(memory_id)

    async def get_memories(
        self,
        limit: Optional[int] = 100,
        offset: int = 0,
    ) -> List[MemoryDocument]:
        """Get all memories."""
        self._store._ensure_loaded()
        all_docs = list(self._store._state.documents.values())
        if limit is None:
            return all_docs[offset:]
        return all_docs[offset : offset + limit]

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update a memory document."""
        state = self._store._state
        if memory_id not in state.documents:
            return False

        doc = state.documents[memory_id]

        if content:
            doc.content = content
        if embedding:
            doc.embedding = embedding
        if metadata is not None:
            doc.metadata = metadata

        if embedding is not None:
            await self.upsert_memory(
                memory_id=memory_id,
                content=doc.content,
                embedding=doc.embedding,
                metadata=doc.metadata,
            )
            return True

        self._store._save_index()
        return True

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory."""
        state = self._store._state
        if memory_id not in state.documents:
            return False

        del state.documents[memory_id]

        idx = state.id_to_idx.pop(memory_id, None)
        if idx is not None:
            state.idx_to_id.pop(idx, None)
            if state.index is None:
                self._store._rebuild_index_from_documents(save=False)
            else:
                self._store._get_index().remove_ids(np.array([idx], dtype=np.int64))

        self._store._save_index()
        return True
