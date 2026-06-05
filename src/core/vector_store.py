"""
Vector Store Module
FAISS vector database for semantic search
"""
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

import numpy as np
import faiss

from src.core.config import get_settings
from src.core.vector_store_document_ops import VectorStoreDocumentOps
from src.core.vector_store_models import MemoryDocument, SearchResult
from src.core.vector_store_persistence import (
    fsync_directory,
    fsync_file,
    get_paths,
    get_vector_persist_directory,
    load_persisted_state,
    save_documents_payload,
    save_index_state,
)
from src.core.vector_store_query_ops import VectorStoreQueryOps
from src.core.vector_store_runtime import (
    can_index_document,
    create_index,
    index_metadata_is_consistent,
    rebuild_index_state,
)
from src.core.vector_store_state import VectorStoreState


logger = logging.getLogger(__name__)


def _normalize_embedding_preference(value: Any, default: str = "local_first") -> str:
    if not isinstance(value, str):
        return default

    normalized = value.strip().lower()
    return normalized or default


def _safe_int(value: Any, default: Optional[int]) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


class VectorStore:
    """
    Vector Store
    Manage memory embeddings using FAISS
    """
    
    def __init__(self, dimension: Optional[int] = None):
        self.settings = get_settings()
        embedding_settings = getattr(self.settings, "embedding", None)
        configured_dimension = _safe_int(getattr(embedding_settings, "dimensions", None), None)
        provider_preference = _normalize_embedding_preference(
            getattr(embedding_settings, "provider_preference", "local_first")
        )
        cloud_dimensions = _safe_int(getattr(embedding_settings, "cloud_dimensions", None), None)
        if provider_preference in {"remote_first", "remote_only"} and cloud_dimensions is not None:
            configured_dimension = cloud_dimensions
        explicit_dimension = _safe_int(dimension, None)
        self.dimension = explicit_dimension or configured_dimension or 768
        self._state = VectorStoreState()
        self._document_ops = VectorStoreDocumentOps(self)
        self._query_ops = VectorStoreQueryOps(self)

    # Compatibility proxies: existing tests and helper modules still touch these names.
    @property
    def _index(self) -> Optional[faiss.Index]:
        return self._state.index

    @_index.setter
    def _index(self, value: Optional[faiss.Index]) -> None:
        self._state.index = value

    @property
    def _documents(self) -> Dict[str, MemoryDocument]:
        return self._state.documents

    @_documents.setter
    def _documents(self, value: Dict[str, MemoryDocument]) -> None:
        self._state.documents = value

    @property
    def _id_to_idx(self) -> Dict[str, int]:
        return self._state.id_to_idx

    @_id_to_idx.setter
    def _id_to_idx(self, value: Dict[str, int]) -> None:
        self._state.id_to_idx = value

    @property
    def _idx_to_id(self) -> Dict[int, str]:
        return self._state.idx_to_id

    @_idx_to_id.setter
    def _idx_to_id(self, value: Dict[int, str]) -> None:
        self._state.idx_to_id = value

    @property
    def _next_vector_id(self) -> int:
        return self._state.next_vector_id

    @_next_vector_id.setter
    def _next_vector_id(self, value: int) -> None:
        self._state.next_vector_id = value

    @property
    def _index_path(self) -> Optional[Path]:
        return self._state.index_path

    @_index_path.setter
    def _index_path(self, value: Optional[Path]) -> None:
        self._state.index_path = value

    @property
    def _docs_path(self) -> Optional[Path]:
        return self._state.docs_path

    @_docs_path.setter
    def _docs_path(self, value: Optional[Path]) -> None:
        self._state.docs_path = value

    @property
    def _index_dimension_mismatch(self) -> bool:
        return self._state.index_dimension_mismatch

    @_index_dimension_mismatch.setter
    def _index_dimension_mismatch(self, value: bool) -> None:
        self._state.index_dimension_mismatch = value

    @property
    def _loaded_index_dimension(self) -> Optional[int]:
        return self._state.loaded_index_dimension

    @_loaded_index_dimension.setter
    def _loaded_index_dimension(self, value: Optional[int]) -> None:
        self._state.loaded_index_dimension = value

    def _get_vector_persist_directory(self) -> str:
        """Get FAISS persist directory from either dict or Pydantic settings."""
        return get_vector_persist_directory(self.settings)

    def _create_index(self) -> faiss.Index:
        """Create a mutable FAISS index with stable vector IDs."""
        return create_index(self.dimension)

    def _ensure_loaded(self):
        """Ensure persisted documents/index metadata have been loaded."""
        if self._state.is_unloaded():
            self._get_index()
    
    def _get_paths(self) -> tuple[Path, Path]:
        """Get storage paths"""
        return get_paths(self.settings)

    def _rebuild_index_from_documents(self, save: bool = True):
        """Rebuild the FAISS index from persisted documents."""
        index, id_to_idx, idx_to_id, next_vector_id = rebuild_index_state(
            self._state.documents,
            self.dimension,
        )
        self._state.assign_rebuilt_index(
            index=index,
            id_to_idx=id_to_idx,
            idx_to_id=idx_to_id,
            next_vector_id=next_vector_id,
        )

        if save:
            self._save_index()

    def _can_index_document(self, doc: MemoryDocument) -> bool:
        """Return whether a document has an embedding compatible with the active index."""
        return can_index_document(doc, self.dimension)

    def _index_metadata_is_consistent(self) -> bool:
        """Check whether the loaded FAISS index and document metadata describe the same state."""
        return index_metadata_is_consistent(
            self._state.index,
            self._state.documents,
            self._state.id_to_idx,
            self._state.idx_to_id,
            self.dimension,
        )

    def _repair_inconsistent_index(self, reason: str, persist: bool = False) -> None:
        """Rebuild an inconsistent FAISS index from persisted documents."""
        logger.warning(
            "Vector store index metadata mismatch detected (%s); rebuilding index from persisted documents.",
            reason,
        )
        self._rebuild_index_from_documents(save=False)
        if not persist:
            return

        try:
            self._save_index()
        except Exception as exc:
            logger.warning(
                "Failed to persist repaired vector store state to %s: %s",
                self._state.index_path,
                exc,
            )
    
    def _load_index(self):
        """Load existing index"""
        self._state.index_path, self._state.docs_path = self._get_paths()
        state = load_persisted_state(
            faiss_module=faiss,
            index_path=self._state.index_path,
            docs_path=self._state.docs_path,
            logger=logger,
        )
        self._state.apply_loaded_state(state)
        documents_load_failed = state["documents_load_failed"]

        if self._state.index is None and self._state.documents:
            self._rebuild_index_from_documents(save=False)

        if self._state.index is not None and getattr(self._state.index, "d", None) != self.dimension:
            self._state.index_dimension_mismatch = True
            self._rebuild_index_from_documents(save=False)

        if self._state.index is not None and "IndexIDMap" not in type(self._state.index).__name__:
            self._rebuild_index_from_documents(save=False)

        if self._state.index is not None and not self._index_metadata_is_consistent():
            self._repair_inconsistent_index(
                reason="faiss index and persisted document metadata are out of sync",
                persist=not documents_load_failed,
            )
    
    def _fsync_file(self, path: Path) -> None:
        """Flush file contents to disk when possible."""
        fsync_file(path)

    def _fsync_directory(self, path: Path) -> None:
        """Flush directory metadata so completed atomic replacements survive crashes."""
        fsync_directory(path)

    def _save_documents_payload(self, path: Path) -> None:
        """Persist document metadata to a temporary file."""
        save_documents_payload(
            path,
            documents=self._state.documents,
            id_to_idx=self._state.id_to_idx,
            idx_to_id=self._state.idx_to_id,
            next_vector_id=self._state.next_vector_id,
        )

    def _save_index(self):
        """Save index to disk using atomic file replacement."""
        if self._state.index is None:
            return

        if self._state.index_path is None or self._state.docs_path is None:
            self._state.index_path, self._state.docs_path = self._get_paths()

        save_index_state(
            faiss_module=faiss,
            index=self._state.index,
            index_path=self._state.index_path,
            docs_path=self._state.docs_path,
            documents=self._state.documents,
            id_to_idx=self._state.id_to_idx,
            idx_to_id=self._state.idx_to_id,
            next_vector_id=self._state.next_vector_id,
            save_documents_payload_fn=self._save_documents_payload,
            fsync_file_fn=self._fsync_file,
            fsync_directory_fn=self._fsync_directory,
        )
    
    def _get_index(self) -> faiss.Index:
        """Get or create FAISS index"""
        if self._state.index is None:
            self._load_index()
            
            if self._state.index is None or self._state.index.ntotal == 0:
                self._state.index = self._create_index()
        
        return self._state.index
    
    # ========================================
    # Document Operations
    # ========================================
    
    async def add_memory(
        self,
        memory_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a memory document"""
        return await self._document_ops.add_memory(memory_id, content, embedding, metadata)

    async def upsert_memory(
        self,
        memory_id: str,
        content: str,
        embedding: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create or replace a memory document and its vector."""
        return await self._document_ops.upsert_memory(memory_id, content, embedding, metadata)
    
    async def get_memory(self, memory_id: str) -> Optional[MemoryDocument]:
        """Get memory by ID"""
        return await self._document_ops.get_memory(memory_id)
    
    async def get_memories(
        self,
        limit: Optional[int] = 100,
        offset: int = 0
    ) -> List[MemoryDocument]:
        """Get all memories"""
        return await self._document_ops.get_memories(limit=limit, offset=offset)
    
    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update a memory document"""
        return await self._document_ops.update_memory(
            memory_id=memory_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
        )
    
    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory"""
        return await self._document_ops.delete_memory(memory_id)
    
    # ========================================
    # Search Operations
    # ========================================
    
    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Vector similarity search"""
        return await self._query_ops.search(
            query_embedding=query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata,
        )
    
    async def search_by_text(
        self,
        query_text: str,
        query_embedding: List[float],
        top_k: int = 5
    ) -> List[SearchResult]:
        """Search by text"""
        return await self._query_ops.search_by_text(query_text, query_embedding, top_k)
    
    # ========================================
    # Statistics
    # ========================================
    
    async def get_count(self) -> int:
        """Get total memory count"""
        return await self._query_ops.get_count()
    
    async def clear_all(self) -> bool:
        """Clear all memories"""
        return await self._query_ops.clear_all()

    async def rebuild_index(self) -> int:
        """Rebuild the FAISS index from persisted documents."""
        return await self._query_ops.rebuild_index()

    async def reembed_all(
        self,
        embed_texts,
        batch_size: int = 32,
    ) -> Dict[str, int]:
        """Regenerate embeddings for all documents and rebuild the index."""
        return await self._query_ops.reembed_all(embed_texts, batch_size=batch_size)

    async def get_index_state(self) -> Dict[str, Any]:
        """Return runtime information about the current index state."""
        return await self._query_ops.get_index_state()
    
    # ========================================
    # Utility Methods
    # ========================================
    
    async def close(self):
        """Close and save"""
        await self._query_ops.close()
    
    async def test_connection(self) -> bool:
        """Test connection"""
        return await self._query_ops.test_connection()


# ============================================
# Global Instance
# ============================================

_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get Vector Store singleton"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


def reset_vector_store() -> None:
    """Reset the cached vector store singleton."""
    global _vector_store
    _vector_store = None
