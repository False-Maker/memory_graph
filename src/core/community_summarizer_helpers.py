"""Helper utilities for the community summarizer facade."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_prompt(context: Dict[str, Any], template: str) -> str:
    """Build an LLM prompt from formatted context."""
    return template.replace("{context}", format_context(context))


def format_context(context: Dict[str, Any]) -> str:
    """Format community context for LLM prompts."""
    lines = [
        f"**Community:** {context.get('title', 'Unknown')}",
        f"**Level:** {context.get('level', 0)}",
        f"**Entity Count:** {context.get('entity_count', 0)}",
        "",
    ]

    entities = context.get("entities", [])
    if entities:
        lines.append("**Key Entities:**")
        for index, entity in enumerate(entities[:20], start=1):
            name = entity.get("name", "Unknown")
            entity_type = entity.get("type", "Unknown")
            lines.append(f"  {index}. {name} ({entity_type})")
        lines.append("")

    relationships = context.get("relationships", [])
    if relationships:
        lines.append("**Key Relationships:**")
        for index, relationship in enumerate(relationships[:20], start=1):
            source = relationship.get("source", "Unknown")
            target = relationship.get("target", "Unknown")
            relationship_type = relationship.get("type", "RELATES")
            lines.append(f"  {index}. {source} -[{relationship_type}]-> {target}")
        lines.append("")

    return "\n".join(lines)


def clean_summary(summary: str) -> str:
    """Normalize the generated summary text."""
    if not summary:
        return ""

    prefixes = ["Summary:", "The summary is:", "Here is the summary:"]
    for prefix in prefixes:
        if summary.startswith(prefix):
            summary = summary[len(prefix) :].strip()

    if summary.startswith('"') and summary.endswith('"'):
        summary = summary[1:-1]
    elif summary.startswith("'") and summary.endswith("'"):
        summary = summary[1:-1]

    return summary.strip()


async def get_existing_summary(summarizer, community_id: str) -> Optional[str]:
    """Fetch an existing summary from GraphStore."""
    community = await summarizer.graph_store.get_community(community_id)
    return community.get("summary") if community else None


async def fetch_community_context(summarizer, community_id: str) -> Dict[str, Any]:
    """Fetch the entities and relationships needed for summary generation."""
    context: Dict[str, Any] = {"community_id": community_id}
    community = await summarizer.graph_store.get_community(
        community_id,
        include_entity_ids=True,
    )
    if community:
        context["title"] = community.get("title", "")
        context["level"] = community.get("level", 0)
        context["entity_count"] = community.get("entity_count", 0)

    entities = await summarizer.graph_store.get_community_entities(community_id, limit=50)
    context["entities"] = [
        {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "properties": entity.properties,
            "source_text": entity.source_text,
        }
        for entity in entities
    ]

    relationships = await summarizer.graph_store.get_community_relationships(
        community_id,
        limit=50,
    )
    context["relationships"] = [
        {
            "source": relationship["source"],
            "target": relationship["target"],
            "type": relationship["type"],
        }
        for relationship in relationships
    ]

    return context


async def store_summary(summarizer, community_id: str, summary: str) -> None:
    """Persist a summary to GraphStore."""
    await summarizer.graph_store.update_community_summary(community_id, summary)


def empty_summary_result(community_id: str, style: str):
    """Build the standard empty-community result."""
    from src.core.community_summarizer import SummaryResult

    return SummaryResult(
        community_id=community_id,
        summary="This community has no entities or relationships to summarize.",
        token_count=12,
        style=style,
    )


async def generate_simple_summary(summarizer, community_id: str, context: Dict[str, Any], style: str):
    """Build the deterministic fallback summary for very small communities."""
    from src.core.community_summarizer import SummaryResult

    entity_names = [entity.get("name", "Unknown") for entity in context.get("entities", [])[:5]]
    if len(entity_names) == 1:
        summary = f"This community contains a single entity: {entity_names[0]}."
    else:
        joined = ", ".join(entity_names)
        summary = f"This small community contains {len(entity_names)} entities: {joined}."

    await store_summary(summarizer, community_id, summary)
    return SummaryResult(
        community_id=community_id,
        summary=summary,
        token_count=len(summary.split()),
        style=style,
    )


async def fetch_communities(summarizer, level: Optional[int] = None) -> List[Dict[str, Any]]:
    """Fetch communities eligible for summarization."""
    return await summarizer.graph_store.list_communities(
        level=level,
        limit=None,
        include_entity_ids=True,
        order_by="level_rank",
    )
