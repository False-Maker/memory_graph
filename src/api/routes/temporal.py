"""Temporal knowledge graph routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas.temporal import (
    TemporalDeleteResponse,
    TemporalEntityStateResponse,
    TemporalStatsResponse,
    TemporalTimelineResponse,
    TemporalTripleCreateRequest,
    TemporalTripleResponse,
)
from src.core.temporal_kg import TemporalTriple, get_temporal_kg


router = APIRouter(prefix="/api/v1/temporal", tags=["temporal"])


def _serialize_temporal_triple(triple: TemporalTriple) -> TemporalTripleResponse:
    return TemporalTripleResponse(
        id=triple.id,
        entity_id=triple.entity_id,
        relation_type=triple.relation_type,
        target_entity_id=triple.target_entity_id,
        valid_from=triple.valid_from,
        valid_to=triple.valid_to,
        confidence=triple.confidence,
        source=triple.source,
        created_at=triple.created_at,
        metadata=triple.metadata,
    )


@router.post("/triples", response_model=TemporalTripleResponse)
async def create_temporal_triple(request: TemporalTripleCreateRequest):
    """Create or update one temporal triple."""
    try:
        triple = await get_temporal_kg().upsert_triple(
            triple_id=request.id,
            entity_id=request.entity_id,
            relation_type=request.relation_type,
            target_entity_id=request.target_entity_id,
            valid_from=request.valid_from,
            valid_to=request.valid_to,
            confidence=request.confidence,
            source=request.source,
            metadata=request.metadata,
        )
        return _serialize_temporal_triple(triple)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/entities/{entity_id}/timeline", response_model=TemporalTimelineResponse)
async def get_entity_timeline(entity_id: str):
    """Return the full temporal timeline for one entity."""
    try:
        triples = await get_temporal_kg().get_entity_timeline(entity_id)
        return TemporalTimelineResponse(
            entity_id=entity_id,
            total=len(triples),
            triples=[_serialize_temporal_triple(item) for item in triples],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/entities/{entity_id}", response_model=TemporalEntityStateResponse)
async def get_entity_state_as_of(entity_id: str, as_of: str | None = Query(default=None)):
    """Return the temporal state for one entity as of a specific timestamp."""
    if not as_of:
        raise HTTPException(status_code=400, detail="as_of query parameter is required")

    try:
        triples = await get_temporal_kg().get_entity_state_as_of(entity_id, as_of)
        return TemporalEntityStateResponse(
            entity_id=entity_id,
            as_of=as_of,
            total=len(triples),
            triples=[_serialize_temporal_triple(item) for item in triples],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/triples/{triple_id}", response_model=TemporalDeleteResponse)
async def delete_temporal_triple(triple_id: str):
    """Delete one temporal triple by id."""
    try:
        deleted = await get_temporal_kg().delete_triple(triple_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Temporal triple not found")
        return TemporalDeleteResponse(success=True, triple_id=triple_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stats", response_model=TemporalStatsResponse)
async def get_temporal_stats():
    """Return aggregate temporal triple statistics."""
    try:
        stats = await get_temporal_kg().get_stats()
        return TemporalStatsResponse(
            total_triples=stats.total_triples,
            entities_with_temporal_data=stats.entities_with_temporal_data,
            open_intervals=stats.open_intervals,
            bounded_intervals=stats.bounded_intervals,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
