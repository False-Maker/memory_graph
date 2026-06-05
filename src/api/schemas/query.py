"""
API Schemas - Query
"""

from typing import Optional, List
from pydantic import BaseModel, Field

from src.api.schemas.diagnostics import CollectionDiagnostics


class QueryRequest(BaseModel):
    """Query request"""

    question: str = Field(..., description="Question to ask")
    strategy: str = Field(
        default="hybrid",
        description="Search strategy: vector, graph, hybrid, or graphrag",
    )
    retrieval_mode: Optional[str] = Field(
        default="hybrid", description="For graphrag: local, global, or hybrid"
    )
    top_k: int = Field(default=5, description="Number of results")
    include_sources: bool = Field(default=True, description="Include source documents")
    session_id: Optional[str] = Field(
        default=None,
        description="Optional session identifier used for query trace correlation and scoped filtering",
    )
    scopes: List[str] = Field(default_factory=list, description="Optional scope filters")
    scope_ids: List[str] = Field(default_factory=list, description="Optional scope ID filters")
    types: List[str] = Field(default_factory=list, description="Optional record_type filters")
    visibility: Optional[str] = Field(default=None, description="Optional visibility filter")
    tags: List[str] = Field(default_factory=list, description="Optional tag filters")
    workspace_id: Optional[str] = Field(default=None, description="Optional workspace filter")
    task_id: Optional[str] = Field(default=None, description="Optional task filter")
    thread_id: Optional[str] = Field(default=None, description="Optional thread filter")
    user_id: Optional[str] = Field(default=None, description="Optional owner filter")
    cursor: Optional[str] = Field(default=None, description="Optional opaque pagination cursor")
    include_expired: bool = Field(default=False, description="Whether expired memories should be included")
    layer: Optional[str] = Field(default="auto", description="Memory layer: auto, l0, l1, l2, or l3")
    layer_budget_override: Optional[int] = Field(default=None, description="Optional token budget override for the selected layer")


class SourceProvenance(BaseModel):
    """Normalized source provenance summary."""

    type: Optional[str] = None
    time: Optional[str] = None
    imported_from: Optional[str] = None


class Source(BaseModel):
    """Source document"""

    memory_id: Optional[str] = None
    content: str
    relevance: float
    entities: List[str] = []
    source: Optional[str] = None
    workspace_id: Optional[str] = None
    external_id: Optional[str] = None
    source_path: Optional[str] = None
    record_type: Optional[str] = None
    title: Optional[str] = None
    tags: List[str] = []
    timestamp: Optional[str] = None
    scope: Optional[str] = None
    scope_id: Optional[str] = None
    visibility: Optional[str] = None
    owner: Optional[str] = None
    session_id: Optional[str] = None
    thread_id: Optional[str] = None
    task_id: Optional[str] = None
    artifact_id: Optional[str] = None
    summary: Optional[str] = None
    confidence: Optional[float] = None
    freshness: Optional[float] = None
    pinned: Optional[bool] = None
    expires_at: Optional[str] = None
    provenance: SourceProvenance = Field(default_factory=SourceProvenance)
    community_id: Optional[str] = None
    community_summary: Optional[str] = None


class CommunityContext(BaseModel):
    """Community context in response"""

    community_id: str
    title: str
    summary: str
    level: int
    entities: List[str] = []
    relevance: float = 0.0


class QueryResponse(BaseModel):
    """Query response"""

    answer: str
    sources: List[Source] = []
    entities: List[str] = []
    communities: List[CommunityContext] = []
    processing_time_ms: int
    next_cursor: Optional[str] = None
    diagnostics: CollectionDiagnostics = Field(default_factory=CollectionDiagnostics)
    layer_used: Optional[str] = None
    layer_fallback_chain: List[str] = []
    context_token_estimate: Optional[int] = None


class QueryRunTraceSummary(BaseModel):
    """Compact summary for one query run trace."""

    run_id: str
    session_id: Optional[str] = None
    question: str
    strategy: str
    retrieval_mode: Optional[str] = None
    status: str
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_duration_ms: Optional[int] = None
    processing_time_ms: Optional[int] = None
    layer_requested: Optional[str] = None
    layer_used: Optional[str] = None
    layer_fallback_chain: List[str] = []
    context_token_estimate: int = 0
    layer_build_duration_ms: int = 0
    source_count: int = 0
    community_count: int = 0
    started_at: str
    completed_at: Optional[str] = None
    failure_reason: Optional[str] = None


class QueryRunTraceResponse(QueryRunTraceSummary):
    """Detailed query run trace payload."""

    top_k: int
    include_sources: bool
    entities_count: int = 0


class QueryRunTraceListResponse(BaseModel):
    """Recent query run trace collection."""

    runs: List[QueryRunTraceSummary] = []
    total: int
