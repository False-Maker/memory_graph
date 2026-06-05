"""Shared data models for VectorStore."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional


class MemoryDocument:
    """Memory document stored in the vector index."""

    def __init__(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.content = content
        self.metadata = metadata
        self.embedding = embedding


class SearchResult:
    """Search result returned from vector similarity queries."""

    def __init__(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any],
        distance: float,
    ):
        self.id = id
        self.content = content
        self.metadata = metadata
        self.distance = distance

    @property
    def relevance(self) -> float:
        """Convert distance to a relevance score in [0, 1]."""
        return 1.0 - self.distance
