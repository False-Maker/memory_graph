"""
Community API Schemas
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

# Request Schemas


class CommunityRequest(BaseModel):
    """Request to create/update community"""

    title: str
    level: int
    parent_id: Optional[str] = None
    entity_ids: List[str] = Field(default_factory=list)
    summary: str = ""
    rank: float = 0.5


class SummaryRequest(BaseModel):
    """Request to regenerate summary"""

    regenerate: bool = False
    max_tokens: int = 500


class GraphRAGQueryRequest(BaseModel):
    """GraphRAG query request"""

    question: str
    mode: str = Field(default="hybrid", pattern="local|global|hybrid")
    top_k: int = Field(default=5, ge=1, le=20)
    include_sources: bool = True


# Response Schemas


class CommunityResponse(BaseModel):
    """Community response"""

    id: str
    level: int
    parent_id: Optional[str]
    title: str
    summary: str
    entity_count: int
    rank: float
    created_at: datetime


class CommunityListResponse(BaseModel):
    """Community list response"""

    communities: List[CommunityResponse]
    total: int


class HierarchyNode(BaseModel):
    """Hierarchy tree node"""

    id: str
    title: str
    level: int
    entity_count: int
    children: List["HierarchyNode"] = Field(default_factory=list)


class HierarchyResponse(BaseModel):
    """Hierarchy response"""

    roots: List[HierarchyNode]
    levels: int
    total_communities: int


class SummaryResponse(BaseModel):
    """Summary generation response"""

    community_id: str
    summary: str
    generated_at: datetime
    token_count: int


class GraphRAGSource(BaseModel):
    """GraphRAG source with community context"""

    memory_id: Optional[str] = None
    content: str
    relevance: float
    entities: List[str] = Field(default_factory=list)
    community_id: Optional[str] = None
    community_summary: Optional[str] = None


class GraphRAGQueryResponse(BaseModel):
    """GraphRAG query response"""

    answer: str
    sources: List[GraphRAGSource]
    communities: List[str] = Field(default_factory=list)  # Referenced community IDs
    strategy_used: str  # local | global | hybrid
    processing_time_ms: int


class CommunityStatusResponse(BaseModel):
    """Community rebuild status."""

    dirty: bool
    last_reason: Optional[str] = None
    last_marked_at: Optional[datetime] = None
    last_rebuild_at: Optional[datetime] = None
    last_rebuild_job_id: Optional[str] = None


# Resolve forward references
HierarchyNode.model_rebuild()
