"""Tests for CommunitySummarizer compatibility helpers."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.community_summarizer import CommunitySummarizer, SummaryResult


class TestCommunitySummarizerCompatibility:
    """Compatibility coverage for summary helpers used outside the class."""

    @pytest.mark.asyncio
    async def test_generate_summary_returns_summary_text(self):
        summarizer = CommunitySummarizer(
            graph_store=MagicMock(),
            llm_manager=MagicMock(),
        )
        summarizer.summarize_community = AsyncMock(
            return_value=SummaryResult(
                community_id="comm-1",
                summary="Fresh summary",
                token_count=2,
                style=CommunitySummarizer.STYLE_DETAILED,
            )
        )

        result = await summarizer.generate_summary("comm-1", max_tokens=128)

        assert result == "Fresh summary"
        summarizer.summarize_community.assert_awaited_once_with(
            community_id="comm-1",
            style=CommunitySummarizer.STYLE_DETAILED,
            max_tokens=128,
            force_regenerate=False,
        )

    @pytest.mark.asyncio
    async def test_generate_summary_raises_when_generation_failed(self):
        summarizer = CommunitySummarizer(
            graph_store=MagicMock(),
            llm_manager=MagicMock(),
        )
        summarizer.summarize_community = AsyncMock(
            return_value=SummaryResult(
                community_id="comm-1",
                summary="",
                token_count=0,
                style=CommunitySummarizer.STYLE_DETAILED,
                success=False,
                error_message="model unavailable",
            )
        )

        with pytest.raises(RuntimeError, match="model unavailable"):
            await summarizer.generate_summary("comm-1")
