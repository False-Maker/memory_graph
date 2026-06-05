"""
GraphRAG index combining hierarchy and summaries
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from src.core.models.community import CommunityHierarchy


@dataclass
class GraphRAGIndex:
    """GraphRAG retrieval index"""

    hierarchy: CommunityHierarchy
    community_summaries: Dict[str, str] = field(default_factory=dict)
    entity_to_community: Dict[str, str] = field(default_factory=dict)
    vector_index: Optional[object] = None  # Will be set later

    def get_community(self, entity_id: str) -> Optional[str]:
        """Get community ID for an entity"""
        return self.entity_to_community.get(entity_id)
