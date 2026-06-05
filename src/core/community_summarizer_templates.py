"""Prompt templates for community summarization."""


class SummaryTemplates:
    """Prompt templates for different summary styles."""

    @staticmethod
    def concise_template() -> str:
        return """You are an expert at creating concise community summaries.

Generate a 2-3 sentence summary that captures the essence of this community.

## Output Format:
Provide ONLY a 2-3 sentence summary. No additional text or explanations.

## Community Context:
{context}

Summary:"""

    @staticmethod
    def detailed_template() -> str:
        return """You are an expert at creating detailed community summaries.

Generate a 4-6 sentence summary that captures the main themes, key entities,
and important relationships within this community.

## Output Format:
Provide a 4-6 sentence summary covering:
1. Primary theme/topic of the community
2. Key entities involved
3. Important relationships or patterns
4. Notable characteristics

No additional text or explanations beyond the summary.

## Community Context:
{context}

Summary:"""

    @staticmethod
    def thematic_template() -> str:
        return """You are an expert at analyzing community themes.

Generate a thematic summary with the main themes organized as bullet points.

## Output Format:
Provide a summary in this format:
Main Topic: [One sentence overview]

Key Themes:
- Theme 1: [description]
- Theme 2: [description]
- Theme 3: [description]

No additional text beyond this format.

## Community Context:
{context}

Summary:"""

    @staticmethod
    def hierarchical_template() -> str:
        return """You are an expert at creating hierarchical summaries.

Generate a summary for a parent community that contains multiple sub-communities.
Focus on the common themes and relationships between the sub-communities.

## Output Format:
Provide a 3-4 sentence summary that:
1. Describes what type of communities are grouped together
2. Identifies common themes across sub-communities
3. Explains how they are related

No additional text or explanations beyond the summary.

## Community Context:
{context}

Summary:"""
