"""
Community data models for GraphRAG
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Community:
    """Community node in hierarchy"""

    id: str
    level: int  # 0=leaf, N=root
    parent_id: Optional[str]  # Parent community
    entity_ids: List[str]  # Contained entities
    summary: str  # Generated summary
    title: str  # Community title
    rank: float  # Importance ranking
    created_at: datetime = field(default_factory=datetime.now)
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CommunityHierarchy:
    """Hierarchical tree structure"""

    communities: Dict[str, Community] = field(default_factory=dict)
    adjacency: Dict[str, List[str]] = field(default_factory=dict)  # parent -> children

    def get_ancestors(self, community_id: str) -> List[str]:
        """Get all ancestors of a community"""
        ancestors = []
        current = community_id
        while True:
            comm = self.communities.get(current)
            if not comm or not comm.parent_id:
                break
            ancestors.append(comm.parent_id)
            current = comm.parent_id
        return ancestors

    def get_descendants(self, community_id: str) -> List[str]:
        """Get all descendants of a community"""
        descendants = []
        stack = [community_id]
        while stack:
            current = stack.pop()
            children = self.adjacency.get(current, [])
            descendants.extend(children)
            stack.extend(children)
        return descendants

    def get_level(self, community_id: str) -> int:
        """Get level of community (0=leaf)"""
        comm = self.communities.get(community_id)
        return comm.level if comm else -1
