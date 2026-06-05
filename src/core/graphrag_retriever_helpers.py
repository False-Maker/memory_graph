"""Helper utilities for GraphRAG retrieval flows."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Iterable, List, Optional, Sequence

import numpy as np

from src.core.models.community import Community


def build_processing_time_ms(start_time: float) -> int:
    """Return a positive processing duration in milliseconds."""
    return max(1, int((time.time() - start_time) * 1000))


def community_record_to_model(record: Optional[dict[str, Any]]) -> Optional[Community]:
    """Convert a stored community mapping into a Community model."""
    if not record:
        return None

    return Community(
        id=record.get("id"),
        level=record.get("level", 0),
        parent_id=record.get("parent_id"),
        entity_ids=record.get("entity_ids", []),
        summary=record.get("summary", ""),
        title=record.get("title", ""),
        rank=record.get("rank", 0.0),
    )


def build_community_context(community: Community, relevance: float = 0.8):
    """Build a CommunityContext from a Community model."""
    from src.core.graphrag_retriever import CommunityContext

    return CommunityContext(
        community_id=community.id,
        title=community.title,
        summary=community.summary,
        level=community.level,
        entities=community.entity_ids.copy(),
        relevance=relevance,
    )


def score_similarity(
    query_embedding: List[float],
    candidates: Sequence[tuple[str, List[float]]],
) -> List[tuple[str, float]]:
    """Compute cosine similarity scores for the supplied embeddings."""
    query_vec = np.array(query_embedding, dtype=float)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []
    query_vec = query_vec / query_norm

    results: List[tuple[str, float]] = []
    for candidate_id, embedding in candidates:
        candidate_vec = np.array(embedding, dtype=float)
        candidate_norm = np.linalg.norm(candidate_vec)
        if candidate_norm == 0:
            continue
        candidate_vec = candidate_vec / candidate_norm
        results.append((candidate_id, float(np.dot(query_vec, candidate_vec))))

    return results


def build_source_identity(source: Any) -> str:
    """Build a stable source identity for dedupe across retrieval modes."""
    memory_id = getattr(source, "memory_id", None)
    if isinstance(memory_id, str) and memory_id:
        return f"memory:{memory_id}"

    community_id = getattr(source, "community_id", None) or "-"
    content = getattr(source, "content", None) or ""
    return f"community:{community_id}:content:{str(content)[:160]}"


def merge_hybrid_results(local_result, global_result, top_k: int, processing_time_ms: int):
    """Merge local and global retrieval results without changing the public contract."""
    from src.core.graphrag_retriever import GraphRAGRetrievalResult

    seen_communities: set[str] = set()
    combined_communities = []

    for context in local_result.communities:
        if context.community_id in seen_communities:
            continue
        seen_communities.add(context.community_id)
        combined_communities.append(replace(context, relevance=context.relevance * 1.2))

    for context in global_result.communities:
        if context.community_id not in seen_communities:
            seen_communities.add(context.community_id)
            combined_communities.append(context)
            continue

        for existing in combined_communities:
            if existing.community_id == context.community_id:
                existing.relevance = max(existing.relevance, context.relevance)
                break

    combined_communities.sort(key=lambda item: item.relevance, reverse=True)
    combined_communities = combined_communities[:top_k]

    seen_sources: set[str] = set()
    combined_sources = []
    for source in list(local_result.sources) + list(global_result.sources):
        source_identity = build_source_identity(source)
        if source_identity in seen_sources:
            continue
        seen_sources.add(source_identity)
        combined_sources.append(source)
        if len(combined_sources) >= top_k:
            break

    combined_entities = list(set(local_result.entities + global_result.entities))

    return GraphRAGRetrievalResult(
        sources=combined_sources,
        entities=combined_entities,
        communities=combined_communities,
        strategy_used="hybrid",
        processing_time_ms=processing_time_ms,
        query_entities=local_result.query_entities,
    )


def build_answer_context(retrieval_result) -> str:
    """Build the answer-generation context text from retrieval results."""
    context_parts: List[str] = []

    if retrieval_result.communities:
        context_parts.append("## Community Context")
        for community in retrieval_result.communities[:3]:
            context_parts.append(f"### Community: {community.title}\n{community.summary}")

    if retrieval_result.sources:
        context_parts.append("\n## Relevant Information")
        for index, source in enumerate(retrieval_result.sources[:5], start=1):
            community_note = (
                f" (from: {source.community_summary[:50]}...)"
                if source.community_summary
                else ""
            )
            context_parts.append(
                f"### Source {index}{community_note}\n{source.content[:1000]}"
            )

    return "\n\n".join(context_parts)
