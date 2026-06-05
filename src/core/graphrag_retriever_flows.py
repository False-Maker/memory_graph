"""Retrieval flows for the GraphRAG retriever facade."""

from __future__ import annotations

from typing import Dict, List, Set

from src.core.graphrag_retriever_helpers import (
    build_processing_time_ms,
    merge_hybrid_results,
    score_similarity,
)


async def run_local_retrieval(retriever, query: str, top_k: int, start_time: float):
    """Run entity-driven local retrieval."""
    from src.core.graphrag_retriever import GraphRAGRetrievalResult

    extractor = retriever._create_entity_extractor()
    extraction = await extractor.extract(query)

    query_entities = [entity.name for entity in extraction.entities]
    entity_communities: Dict[str, Set[str]] = {}
    community_contexts = {}

    for entity in extraction.entities:
        resolved_entity_ids = await retriever._resolve_query_entity_ids(entity)
        for resolved_entity_id in resolved_entity_ids:
            communities = await retriever._get_entity_communities(resolved_entity_id)
            if resolved_entity_id not in entity_communities:
                entity_communities[resolved_entity_id] = set()
            entity_communities[resolved_entity_id].update(communities)

            for community_id in communities:
                if community_id in community_contexts:
                    continue
                community = await retriever._get_community_from_store(community_id)
                if community:
                    community_contexts[community_id] = retriever._build_community_context(community)

    expanded_communities = await retriever._expand_communities(entity_communities, top_k)
    sources = await retriever._build_sources_from_communities(expanded_communities, query, top_k)
    communities = [
        community_contexts[community_id]
        for community_id in expanded_communities
        if community_id in community_contexts
    ]

    return GraphRAGRetrievalResult(
        sources=sources,
        entities=query_entities,
        communities=list(communities),
        strategy_used="local",
        processing_time_ms=build_processing_time_ms(start_time),
        query_entities=query_entities,
    )


async def run_global_retrieval(retriever, query: str, top_k: int, start_time: float):
    """Run community-summary global retrieval."""
    from src.core.graphrag_retriever import GraphRAGRetrievalResult

    query_embedding = (await retriever.llm.embed([query]))[0]
    matching_communities = await retriever._search_community_summaries(query_embedding, top_k * 2)

    communities = []
    for community_id, relevance in matching_communities:
        community = await retriever._get_community_from_store(community_id)
        if not community or not community.summary:
            continue
        context = retriever._build_community_context(community)
        context.relevance = relevance
        communities.append(context)

    communities.sort(key=lambda item: item.relevance, reverse=True)
    communities = communities[:top_k]
    sources = await retriever._build_sources_from_communities(
        [community.community_id for community in communities],
        query,
        top_k,
    )

    return GraphRAGRetrievalResult(
        sources=sources,
        entities=[],
        communities=communities,
        strategy_used="global",
        processing_time_ms=build_processing_time_ms(start_time),
    )


async def run_hybrid_retrieval(retriever, query: str, top_k: int, start_time: float):
    """Run hybrid retrieval by combining local and global flows."""
    local_result = await retriever._local_retrieval(query, top_k * 2, start_time)
    global_result = await retriever._global_retrieval(query, top_k * 2, start_time)
    return merge_hybrid_results(
        local_result=local_result,
        global_result=global_result,
        top_k=top_k,
        processing_time_ms=build_processing_time_ms(start_time),
    )


async def expand_communities_flow(retriever, entity_communities: Dict[str, Set[str]], top_k: int) -> List[str]:
    """Expand direct communities with neighboring communities and rank them."""
    all_communities: Set[str] = set()
    for community_set in entity_communities.values():
        all_communities.update(community_set)

    for community_id in list(all_communities):
        neighbors = await retriever._get_community_neighbors(community_id)
        all_communities.update(neighbors)

    community_scores: List[tuple[str, float]] = []
    for community_id in all_communities:
        score = 0.0
        for community_set in entity_communities.values():
            if community_id in community_set:
                score += 1.0

        community = await retriever._get_community_from_store(community_id)
        if community:
            size_factor = min(1.0, 10.0 / max(len(community.entity_ids), 1))
            score *= size_factor
        community_scores.append((community_id, score))

    community_scores.sort(key=lambda item: item[1], reverse=True)
    return [community_id for community_id, _ in community_scores[:top_k]]


async def search_community_summaries_flow(retriever, query_embedding: List[float], top_k: int) -> List[tuple[str, float]]:
    """Search over stored community summaries."""
    communities = await retriever.graph_store.list_communities(require_summary=True, limit=None)
    if not communities:
        return []

    summaries = [community["summary"] for community in communities]
    summary_embeddings = await retriever.llm.embed(summaries)
    results = score_similarity(
        query_embedding=query_embedding,
        candidates=[
            (community["id"], embedding)
            for community, embedding in zip(communities, summary_embeddings)
        ],
    )
    results.sort(key=lambda item: item[1], reverse=True)
    return results[:top_k]


async def build_sources_from_communities_flow(
    retriever,
    community_ids: List[str],
    query: str,
    top_k: int,
):
    """Build and rerank source passages from community entities."""
    from src.core.graphrag_retriever import GraphRAGSource

    sources: List[GraphRAGSource] = []
    source_keys: List[str] = []
    seen_source_keys: Set[str] = set()

    for community_id in community_ids:
        community = await retriever._get_community_from_store(community_id)
        if not community:
            continue

        entities = await retriever.graph_store.get_community_entities(community_id, limit=5)
        for entity in entities:
            if not entity.source_text:
                continue
            memory_ids = await retriever.graph_store.get_entity_memory_ids(entity.id, limit=1)
            resolved_memory_id = memory_ids[0] if memory_ids else None
            source_key = resolved_memory_id or f"entity:{entity.id}"
            if source_key in seen_source_keys:
                continue

            source_content = entity.source_text
            if resolved_memory_id:
                memory_doc = await retriever.vector_store.get_memory(resolved_memory_id)
                if memory_doc and getattr(memory_doc, "content", None):
                    source_content = memory_doc.content

            seen_source_keys.add(source_key)
            sources.append(
                GraphRAGSource(
                    memory_id=resolved_memory_id,
                    content=source_content,
                    relevance=community.rank,
                    entities=[entity.name],
                    community_id=community.id,
                    community_summary=community.summary,
                )
            )
            source_keys.append(source_key)

    if not sources:
        return []

    embeddings = await retriever.llm.embed([query] + [source.content[:500] for source in sources])
    similarity_scores = score_similarity(
        query_embedding=embeddings[0],
        candidates=[
            (source_key, embedding)
            for source_key, embedding in zip(source_keys, embeddings[1:])
        ],
    )
    score_by_source_key = {source_key: relevance for source_key, relevance in similarity_scores}
    for source, source_key in zip(sources, source_keys):
        if source_key in score_by_source_key:
            source.relevance = score_by_source_key[source_key]

    sources.sort(key=lambda item: item.relevance, reverse=True)
    return sources[:top_k]
