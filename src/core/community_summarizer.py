"""
Community Summarizer Module
Generates natural language summaries for communities using LLM
"""

import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from src.core.config import get_settings
from src.core.graph_store import GraphStore
from src.core.llm_manager import LLMManager

logger = logging.getLogger(__name__)

# ============================================
# Summary Result
# ============================================


@dataclass
class SummaryResult:
    """Result of community summarization"""

    community_id: str
    summary: str
    token_count: int
    style: str
    created_at: str = field(default_factory=lambda: None)
    success: bool = True
    error_message: Optional[str] = None


from src.core.community_summarizer_helpers import (
    build_prompt,
    clean_summary,
    empty_summary_result,
    fetch_communities,
    fetch_community_context,
    format_context,
    generate_simple_summary,
    get_existing_summary,
    store_summary,
)
from src.core.community_summarizer_templates import SummaryTemplates


# ============================================
# Community Summarizer
# ============================================


class CommunitySummarizer:
    """
    Generates natural language summaries for communities.

    Process:
    1. Fetch community entities and relationships from GraphStore
    2. Build LLM prompt with community context
    3. Generate summary (200-500 tokens)
    4. Store summary in Community.summary field
    """

    # Summary styles
    STYLE_CONCISE = "concise"
    STYLE_DETAILED = "detailed"
    STYLE_THEMATIC = "thematic"
    STYLE_HIERARCHICAL = "hierarchical"

    def __init__(
        self,
        graph_store: Optional[GraphStore] = None,
        llm_manager: Optional[LLMManager] = None,
    ):
        """Initialize community summarizer"""
        self.graph_store = graph_store or GraphStore()
        self.llm_manager = llm_manager or LLMManager()
        self.settings = get_settings()

    async def summarize_community(
        self,
        community_id: str,
        style: str = STYLE_DETAILED,
        max_tokens: int = 500,
        force_regenerate: bool = False,
    ) -> SummaryResult:
        """
        Generate summary for a single community.

        Args:
            community_id: ID of community to summarize
            style: Summary style (concise, detailed, thematic, hierarchical)
            max_tokens: Maximum tokens for summary
            force_regenerate: Regenerate even if summary exists

        Returns:
            SummaryResult with generated summary and metadata
        """
        logger.info(f"Summarizing community {community_id} with style '{style}'")

        # Check if summary already exists
        if not force_regenerate:
            existing = await self._get_existing_summary(community_id)
            if existing and len(existing) > 50:
                logger.info(f"Using existing summary for community {community_id}")
                return SummaryResult(
                    community_id=community_id,
                    summary=existing,
                    token_count=len(existing.split()),
                    style=style,
                )

        # Fetch community context
        context = await self._fetch_community_context(community_id)

        if not context or context.get("entity_count", 0) == 0:
            logger.warning(f"Community {community_id} has no entities")
            return self._empty_summary_result(community_id, style)

        # Handle small communities
        if context.get("entity_count", 0) < 3:
            logger.info(
                f"Community {community_id} has < 3 entities, using simple summary"
            )
            return await self._generate_simple_summary(community_id, context, style)

        # Build prompt with context
        prompt = self._build_prompt(context, style)

        # Generate summary using LLM
        try:
            summary = await self.llm_manager.generate(
                prompt, temperature=0.5, max_tokens=max_tokens
            )

            # Clean up the summary
            summary = self._clean_summary(summary)

            # Store summary back to GraphStore
            await self._store_summary(community_id, summary)

            token_count = len(summary.split())

            logger.info(
                f"Generated summary for community {community_id}: {token_count} tokens"
            )

            return SummaryResult(
                community_id=community_id,
                summary=summary,
                token_count=token_count,
                style=style,
            )

        except Exception as e:
            logger.error(
                f"Failed to generate summary for community {community_id}: {e}"
            )
            return SummaryResult(
                community_id=community_id,
                summary="",
                token_count=0,
                style=style,
                success=False,
                error_message=str(e),
            )

    async def generate_summary(
        self,
        community_id: str,
        max_tokens: int = 500,
        style: str = STYLE_DETAILED,
        force_regenerate: bool = False,
    ) -> str:
        """Compatibility helper used by community summary routes."""
        result = await self.summarize_community(
            community_id=community_id,
            style=style,
            max_tokens=max_tokens,
            force_regenerate=force_regenerate,
        )
        if not result.success:
            raise RuntimeError(result.error_message or "Failed to generate summary")
        return result.summary

    async def summarize_all_communities(
        self,
        level: Optional[int] = None,
        style: str = STYLE_DETAILED,
        batch_size: int = 10,
        force_regenerate: bool = False,
    ) -> List[SummaryResult]:
        """
        Generate summaries for all communities.

        Args:
            level: Filter by level (None = all levels)
            style: Summary style
            batch_size: Number of communities to process in parallel
            force_regenerate: Regenerate existing summaries

        Returns:
            List of SummaryResult for all processed communities
        """
        logger.info(f"Summarizing all communities at level {level or 'all'}")

        # Fetch communities to summarize
        communities = await self._fetch_communities(level)

        if not communities:
            logger.warning("No communities found to summarize")
            return []

        logger.info(f"Found {len(communities)} communities to summarize")

        results = []

        # Process in batches
        for i in range(0, len(communities), batch_size):
            batch = communities[i : i + batch_size]
            logger.info(
                f"Processing batch {i // batch_size + 1}: {len(batch)} communities"
            )

            for comm in batch:
                result = await self.summarize_community(
                    comm["id"], style=style, force_regenerate=force_regenerate
                )
                results.append(result)

        # Log statistics
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful
        total_tokens = sum(r.token_count for r in results)

        logger.info(
            f"Summarization complete: {successful} successful, {failed} failed, "
            f"{total_tokens} total tokens"
        )

        return results

    async def _get_existing_summary(self, community_id: str) -> Optional[str]:
        """Get existing summary from GraphStore."""
        return await get_existing_summary(self, community_id)

    async def _fetch_community_context(self, community_id: str) -> Dict[str, Any]:
        """
        Fetch community context from GraphStore.

        Returns dict with entities, relationships, and key facts.
        """
        return await fetch_community_context(self, community_id)

    def _build_prompt(self, context: Dict[str, Any], style: str) -> str:
        """Build LLM prompt with community context"""
        return build_prompt(context, self._get_template(style))

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format community context for LLM prompt"""
        return format_context(context)

    def _get_template(self, style: str) -> str:
        """Get prompt template for style"""
        templates = {
            self.STYLE_CONCISE: SummaryTemplates.concise_template(),
            self.STYLE_DETAILED: SummaryTemplates.detailed_template(),
            self.STYLE_THEMATIC: SummaryTemplates.thematic_template(),
            self.STYLE_HIERARCHICAL: SummaryTemplates.hierarchical_template(),
        }
        return templates.get(style, SummaryTemplates.detailed_template())

    def _clean_summary(self, summary: str) -> str:
        """Clean up generated summary"""
        return clean_summary(summary)

    async def _store_summary(self, community_id: str, summary: str) -> None:
        """Store summary on the community record in GraphStore."""
        await store_summary(self, community_id, summary)

    def _empty_summary_result(self, community_id: str, style: str) -> SummaryResult:
        """Return result for empty community"""
        return empty_summary_result(community_id, style)

    async def _generate_simple_summary(
        self, community_id: str, context: Dict[str, Any], style: str
    ) -> SummaryResult:
        """Generate simple summary for small community"""
        return await generate_simple_summary(self, community_id, context, style)

    async def _fetch_communities(
        self, level: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch communities to summarize"""
        return await fetch_communities(self, level)


# ============================================
# Utility Functions
# ============================================


async def summarize_community(
    community_id: str,
    style: str = CommunitySummarizer.STYLE_DETAILED,
    force_regenerate: bool = False,
) -> SummaryResult:
    """
    Convenience function to summarize a single community.

    Args:
        community_id: ID of community to summarize
        style: Summary style
        force_regenerate: Regenerate even if summary exists

    Returns:
        SummaryResult with generated summary
    """
    summarizer = CommunitySummarizer()
    return await summarizer.summarize_community(
        community_id, style=style, force_regenerate=force_regenerate
    )


async def summarize_all_communities(
    level: Optional[int] = None,
    style: str = CommunitySummarizer.STYLE_DETAILED,
    batch_size: int = 10,
    force_regenerate: bool = False,
) -> List[SummaryResult]:
    """
    Convenience function to summarize all communities.

    Args:
        level: Filter by level
        style: Summary style
        batch_size: Batch processing size
        force_regenerate: Regenerate existing summaries

    Returns:
        List of SummaryResult for all communities
    """
    summarizer = CommunitySummarizer()
    return await summarizer.summarize_all_communities(
        level=level,
        style=style,
        batch_size=batch_size,
        force_regenerate=force_regenerate,
    )
