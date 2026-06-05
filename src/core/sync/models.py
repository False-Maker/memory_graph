"""Internal models for the generic sync service."""

from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.core.graph_store_models import GraphEntity, GraphRelationship


@dataclass
class CanonicalGraphPayload:
    """Canonical graph rows derived from one memory document."""

    entities: List[GraphEntity] = field(default_factory=list)
    mentions: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[GraphRelationship] = field(default_factory=list)
    relationship_evidence: List[Dict[str, Any]] = field(default_factory=list)
