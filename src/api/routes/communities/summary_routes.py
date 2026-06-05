"""Summary routes for communities."""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from src.api.routes.communities.deps import (
    create_community_summarizer,
    create_hierarchy_builder,
)
from src.api.routes.communities_helpers import find_tree_community
from src.api.schemas.community import SummaryRequest, SummaryResponse

router = APIRouter(prefix="/api/v1/communities", tags=["communities"])


@router.post("/{community_id}/summarize", response_model=SummaryResponse)
async def regenerate_summary(community_id: str, request: SummaryRequest):
    """
    Regenerate a community's summary using the LLM.

    Parameters:
    - community_id: Community to summarize
    - regenerate: Force regeneration even if summary exists
    - max_tokens: Maximum tokens for generated summary
    """
    try:
        tree = await create_hierarchy_builder().get_hierarchy_tree()
        community = find_tree_community(tree, community_id)
        if not community:
            raise HTTPException(
                status_code=404,
                detail=f"Community {community_id} not found",
            )

        existing_summary = community.get("summary", "")
        if not request.regenerate and existing_summary:
            return SummaryResponse(
                community_id=community_id,
                summary=existing_summary,
                generated_at=community.get("created_at", datetime.now()),
                token_count=len(existing_summary.split()),
            )

        summarizer = create_community_summarizer()
        summary = await summarizer.generate_summary(
            community_id,
            max_tokens=request.max_tokens,
            force_regenerate=request.regenerate,
        )
        return SummaryResponse(
            community_id=community_id,
            summary=summary,
            generated_at=datetime.now(),
            token_count=len(summary.split()),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate summary: {str(exc)}",
        ) from exc
