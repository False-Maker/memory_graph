"""Runtime state container for VectorStore internals."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import faiss

from src.core.vector_store_models import MemoryDocument


@dataclass
class VectorStoreState:
    """Mutable runtime state shared by the VectorStore facade and helper ops."""

    index: Optional[faiss.Index] = None
    documents: Dict[str, MemoryDocument] = field(default_factory=dict)
    id_to_idx: Dict[str, int] = field(default_factory=dict)
    idx_to_id: Dict[int, str] = field(default_factory=dict)
    next_vector_id: int = 1
    index_path: Optional[Path] = None
    docs_path: Optional[Path] = None
    index_dimension_mismatch: bool = False
    loaded_index_dimension: Optional[int] = None

    def is_unloaded(self) -> bool:
        """Return whether no persisted runtime state has been loaded yet."""
        return (
            self.index is None
            and not self.documents
            and not self.id_to_idx
            and not self.idx_to_id
        )

    def apply_loaded_state(self, payload: Dict[str, Any]) -> None:
        """Copy a persistence payload into the runtime state."""
        self.index = payload["index"]
        self.loaded_index_dimension = payload["loaded_index_dimension"]
        self.documents = payload["documents"]
        self.id_to_idx = payload["id_to_idx"]
        self.idx_to_id = payload["idx_to_id"]
        self.next_vector_id = payload["next_vector_id"]

    def assign_rebuilt_index(
        self,
        *,
        index: faiss.Index,
        id_to_idx: Dict[str, int],
        idx_to_id: Dict[int, str],
        next_vector_id: int,
    ) -> None:
        """Replace the active index runtime with rebuilt metadata."""
        self.index = index
        self.id_to_idx = id_to_idx
        self.idx_to_id = idx_to_id
        self.next_vector_id = next_vector_id
