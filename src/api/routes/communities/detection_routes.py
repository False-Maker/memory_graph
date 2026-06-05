"""Detection and status routes for communities."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from src.api.routes.communities.deps import (
    create_community_detector,
    get_graph_store,
    get_uuid_module,
)
from src.api.schemas.community import CommunityStatusResponse

router = APIRouter(prefix="/api/v1/communities", tags=["communities"])


@router.post("/detect", response_model=dict)
async def detect_communities(
    algorithm: str = Query(
        default="leiden", pattern="leiden|louvain|label_propagation"
    ),
    resolution: float = Query(default=1.0, ge=0.1, le=5.0),
):
    """
    Trigger community detection on the graph.

    Parameters:
    - algorithm: Detection algorithm (leiden, louvain, label_propagation)
    - resolution: Resolution parameter for modularity (higher = more communities)

    Returns:
    - Detection job ID and status
    """
    try:
        detector = create_community_detector()
        graph_store = get_graph_store()
        job_id = f"community_rebuild_{get_uuid_module().uuid4().hex[:12]}"

        result = await detector.detect_communities(
            algorithm=algorithm,
            resolution=resolution,
        )
        actual_algorithm = algorithm if algorithm == "leiden" else "leiden"
        await graph_store.mark_community_clean(
            rebuild_at=datetime.now().isoformat(),
            job_id=job_id,
        )

        return {
            "job_id": job_id,
            "status": "completed",
            "algorithm": actual_algorithm,
            "resolution": resolution,
            "num_communities": result.num_communities,
            "modularity": result.modularity,
            "message": "Community detection completed.",
        }
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Community detection failed: {str(exc)}",
        ) from exc


@router.get("/status", response_model=CommunityStatusResponse)
async def get_community_status():
    """Get whether community derivations are dirty and need rebuild."""
    try:
        state = await get_graph_store().get_community_state()
        return CommunityStatusResponse(**state)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get community status: {str(exc)}",
        ) from exc
