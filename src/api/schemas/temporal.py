"""API schemas for temporal knowledge graph endpoints."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class TemporalTripleCreateRequest(BaseModel):
    """Create or update one temporal triple."""

    id: Optional[str] = None
    entity_id: str
    relation_type: str
    target_entity_id: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    confidence: float = 1.0
    source: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalTripleResponse(BaseModel):
    """Serialized temporal triple."""

    id: str
    entity_id: str
    relation_type: str
    target_entity_id: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    confidence: float = 1.0
    source: Optional[str] = None
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalTimelineResponse(BaseModel):
    """Timeline view for one entity."""

    entity_id: str
    total: int
    triples: list[TemporalTripleResponse]


class TemporalEntityStateResponse(BaseModel):
    """Entity state resolved at one point in time."""

    entity_id: str
    as_of: str
    total: int
    triples: list[TemporalTripleResponse]


class TemporalDeleteResponse(BaseModel):
    """Delete response for one temporal triple."""

    success: bool
    triple_id: str


class TemporalStatsResponse(BaseModel):
    """Temporal store statistics."""

    total_triples: int
    entities_with_temporal_data: int
    open_intervals: int
    bounded_intervals: int
