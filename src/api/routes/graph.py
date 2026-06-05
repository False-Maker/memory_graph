"""
API Routes - Graph
"""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.graph import (
    EntityResponse,
    RelationshipResponse,
    GraphStatsResponse,
    EntityListResponse,
    RelationshipListResponse,
    NeighborResponse
)
from src.core.graph_store import get_graph_store


router = APIRouter(prefix="/api/v1/graph", tags=["graph"])
_QA_FAIL_GRAPH_READS_ENV = "MEMORY_GRAPH_QA_FAIL_GRAPH_READS"


def _should_force_graph_failure(target: str) -> bool:
    raw = os.environ.get(_QA_FAIL_GRAPH_READS_ENV, "").strip()
    if not raw:
        return False
    enabled = {item.strip() for item in raw.split(",") if item.strip()}
    return target in enabled


@router.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats():
    """Get graph statistics"""
    try:
        if _should_force_graph_failure("stats"):
            raise RuntimeError("QA forced failure for graph stats")
        graph_store = get_graph_store()
        stats = await graph_store.get_stats()
        
        return GraphStatsResponse(
            total_entities=stats.total_entities,
            total_relationships=stats.total_relationships,
            entity_types=stats.entity_types,
            total_memories=stats.total_memories
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    entity_type: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500)
):
    """List all entities"""
    try:
        if _should_force_graph_failure("entities"):
            raise RuntimeError("QA forced failure for graph entities")
        graph_store = get_graph_store()
        entities = await graph_store.get_entities(entity_type=entity_type, limit=limit)
        
        entity_responses = [
            EntityResponse(
                id=e.id,
                name=e.name,
                type=e.type,
                properties=e.properties,
                source_text=e.source_text,
                confidence=e.confidence,
                created_at=e.created_at
            )
            for e in entities
        ]
        
        return EntityListResponse(
            entities=entity_responses,
            total=len(entity_responses)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str):
    """Get entity by ID"""
    try:
        graph_store = get_graph_store()
        entity = await graph_store.get_entity(entity_id)
        
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        
        return EntityResponse(
            id=entity.id,
            name=entity.name,
            type=entity.type,
            properties=entity.properties,
            source_text=entity.source_text,
            confidence=entity.confidence,
            created_at=entity.created_at
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entities/{entity_id}/neighbors")
async def get_entity_neighbors(entity_id: str, depth: int = Query(default=2, ge=1, le=5)):
    """Get entity neighbors"""
    try:
        graph_store = get_graph_store()
        neighbors = await graph_store.get_neighbors(entity_id, depth=depth)
        
        return {
            "entity_id": entity_id,
            "neighbors": [
                NeighborResponse(
                    nodes=n["nodes"],
                    distance=n["distance"]
                )
                for n in neighbors
            ]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationships", response_model=RelationshipListResponse)
async def list_relationships(
    entity_id: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500)
):
    """List all relationships"""
    try:
        if _should_force_graph_failure("relationships"):
            raise RuntimeError("QA forced failure for graph relationships")
        graph_store = get_graph_store()
        relationships = await graph_store.get_relationships(entity_id=entity_id, limit=limit)
        
        rel_responses = [
            RelationshipResponse(
                id=r.id,
                source_id=r.source_id,
                target_id=r.target_id,
                type=r.type,
                properties=r.properties,
                confidence=r.confidence
            )
            for r in relationships
        ]
        
        return RelationshipListResponse(
            relationships=rel_responses,
            total=len(rel_responses)
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
