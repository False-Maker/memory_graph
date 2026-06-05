"""Shared data models for GraphStore."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict


@dataclass
class GraphEntity:
    """Graph entity."""

    id: str
    name: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    source_text: str = ""
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GraphRelationship:
    """Graph relationship."""

    id: str
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class GraphStats:
    """Graph statistics."""

    total_entities: int = 0
    total_relationships: int = 0
    entity_types: Dict[str, int] = field(default_factory=dict)
    total_memories: int = 0
