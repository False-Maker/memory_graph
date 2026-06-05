"""
API Schemas - Graph
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel


class EntityResponse(BaseModel):
    """Entity response"""
    id: str
    name: str
    type: str
    properties: Dict[str, Any] = {}
    source_text: str = ""
    confidence: float = 1.0
    created_at: datetime


class RelationshipResponse(BaseModel):
    """Relationship response"""
    id: str
    source_id: str
    target_id: str
    type: str
    properties: Dict[str, Any] = {}
    confidence: float = 1.0


class GraphStatsResponse(BaseModel):
    """Graph statistics response"""
    total_entities: int
    total_relationships: int
    entity_types: Dict[str, int] = {}
    total_memories: int


class EntityListResponse(BaseModel):
    """Entity list response"""
    entities: List[EntityResponse]
    total: int


class RelationshipListResponse(BaseModel):
    """Relationship list response"""
    relationships: List[RelationshipResponse]
    total: int


class NeighborResponse(BaseModel):
    """Neighbor response"""
    nodes: List[Dict[str, Any]]
    distance: int
