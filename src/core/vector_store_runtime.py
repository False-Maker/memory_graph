"""Runtime/index helpers for VectorStore."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import faiss
import numpy as np

from src.core.vector_store_models import MemoryDocument, SearchResult


def create_index(dimension: int) -> faiss.Index:
    """Create a mutable FAISS index with stable vector IDs."""
    return faiss.IndexIDMap2(faiss.IndexFlatIP(dimension))


def can_index_document(doc: MemoryDocument, dimension: int) -> bool:
    """Return whether a document has an embedding compatible with the active index."""
    return doc.embedding is not None and len(doc.embedding) == dimension


def rebuild_index_state(
    documents: Dict[str, MemoryDocument],
    dimension: int,
) -> tuple[faiss.Index, Dict[str, int], Dict[int, str], int]:
    """Rebuild the FAISS index and ID maps from persisted documents."""
    index = create_index(dimension)
    id_to_idx: Dict[str, int] = {}
    idx_to_id: Dict[int, str] = {}
    next_vector_id = 1

    vectors: List[List[float]] = []
    vector_ids: List[int] = []

    for memory_id, doc in documents.items():
        if not can_index_document(doc, dimension):
            continue

        vector_id = next_vector_id
        next_vector_id += 1

        id_to_idx[memory_id] = vector_id
        idx_to_id[vector_id] = memory_id
        vectors.append(doc.embedding)
        vector_ids.append(vector_id)

    if vectors:
        matrix = np.array(vectors, dtype=np.float32)
        faiss.normalize_L2(matrix)
        index.add_with_ids(matrix, np.array(vector_ids, dtype=np.int64))

    return index, id_to_idx, idx_to_id, next_vector_id


def index_metadata_is_consistent(
    index: Optional[faiss.Index],
    documents: Dict[str, MemoryDocument],
    id_to_idx: Dict[str, int],
    idx_to_id: Dict[int, str],
    dimension: int,
) -> bool:
    """Check whether the FAISS index and document metadata describe the same state."""
    if index is None:
        return True

    if len(id_to_idx) != len(idx_to_id):
        return False

    vector_ids = list(id_to_idx.values())
    if len(vector_ids) != len(set(vector_ids)):
        return False

    if set(idx_to_id.keys()) != set(vector_ids):
        return False

    expected_indexed_documents = 0
    for memory_id, doc in documents.items():
        if not can_index_document(doc, dimension):
            continue

        expected_indexed_documents += 1
        vector_id = id_to_idx.get(memory_id)
        if vector_id is None:
            return False
        if idx_to_id.get(vector_id) != memory_id:
            return False

    if expected_indexed_documents != len(id_to_idx):
        return False

    return index.ntotal == expected_indexed_documents


def search_documents(
    *,
    index: faiss.Index,
    documents: Dict[str, MemoryDocument],
    idx_to_id: Dict[int, str],
    query_embedding: List[float],
    top_k: int,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[SearchResult]:
    """Search the FAISS index and map hits back to stored documents."""
    vec = np.array([query_embedding], dtype=np.float32)
    faiss.normalize_L2(vec)

    search_k = min(top_k * 2, index.ntotal)
    distances, indices = index.search(vec, search_k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx < 0:
            continue

        memory_id = idx_to_id.get(int(idx))
        if not memory_id:
            continue

        doc = documents.get(memory_id)
        if not doc:
            continue

        if filter_metadata:
            match = all(doc.metadata.get(key) == value for key, value in filter_metadata.items())
            if not match:
                continue

        results.append(
            SearchResult(
                id=doc.id,
                content=doc.content,
                metadata=doc.metadata,
                distance=float(dist),
            )
        )

        if len(results) >= top_k:
            break

    return results
