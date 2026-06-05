"""
API Schemas - Memory
"""
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

from src.api.schemas.diagnostics import CollectionDiagnostics


class MemoryMetadata(BaseModel):
    """Memory metadata"""
    source: Optional[str] = None
    workspace_id: Optional[str] = None
    external_id: Optional[str] = None
    source_path: Optional[str] = None
    record_type: Optional[str] = None
    title: Optional[str] = None
    tags: List[str] = []
    timestamp: Optional[datetime] = None
    content_checksum: Optional[str] = None
    external_revision: Optional[str] = None
    external_updated_at: Optional[datetime] = None
    platform: Optional[str] = None
    conversation_id: Optional[str] = None
    archived: Optional[bool] = None
    archived_at: Optional[datetime] = None
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
    expires_at: Optional[datetime] = None


class MemoryCreate(BaseModel):
    """Memory create request"""
    content: str = Field(..., description="Memory content")
    metadata: Optional[MemoryMetadata] = None


class MemoryProvenance(BaseModel):
    """Structured provenance summary for one memory."""
    type: Optional[str] = None
    time: Optional[str] = None
    imported_from: Optional[str] = None


class MemoryResponse(BaseModel):
    """Memory response"""
    id: str
    content: str
    summary: Optional[str] = None
    metadata: Optional[MemoryMetadata] = None
    provenance: MemoryProvenance = Field(default_factory=MemoryProvenance)
    created_at: datetime


class MemoryCreateResponse(BaseModel):
    """Memory create response"""
    memory_id: str
    entities_count: int
    relationships_count: int
    processing_time_ms: int


class MemoryListResponse(BaseModel):
    """Memory list response"""
    memories: List[MemoryResponse]
    total: int
    limit: int
    offset: int
    next_cursor: Optional[str] = None
    diagnostics: CollectionDiagnostics = Field(default_factory=CollectionDiagnostics)


# Conversation import schemas

class ConversationImportRequest(BaseModel):
    """Request to import a conversation"""
    content: str = Field(..., description="Conversation content (JSON format)")
    format: Optional[str] = Field(None, description="Format hint: chatgpt, claude, deepseek, auto")
    output_format: str = Field("markdown", description="Output format: markdown, plain_text")


class ConversationParseResult(BaseModel):
    """Result of parsing a single conversation"""
    conversation_id: str
    title: str
    platform: str
    message_count: int
    created_at: Optional[datetime] = None
    preview: str = Field(..., description="First 200 chars preview")


class ConversationImportResponse(BaseModel):
    """Response for conversation import"""
    success: bool
    parsed_conversations: List[ConversationParseResult]
    imported_memories: int
    failed_count: int = 0
    platform: str
    processing_time_ms: int
