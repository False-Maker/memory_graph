import {
  buildCommunityDetailNavigationNormalizer,
  buildSingleMemoryContextReadNormalizer,
  buildSuccessfulCommunitySummaryRefreshNormalizer,
  createTaskCase,
  entityNames,
  itemTitles,
  normalizeHealth,
  normalizeList,
  normalizeQueryModeMap,
  normalizeRouteWithIdPlaceholder,
  normalizeUrlPathAndHash,
  queryCommunityIds,
  querySourceCommunityIds,
  relationshipTriples,
} from './helpers.mjs'

export const MAINLINE_CORE_TASK_CASES = {
  'task-24': createTaskCase('task-24', {
    normalize: buildSingleMemoryContextReadNormalizer({
      getMemoryContent: (http) => http.memories?.memories?.[0]?.content ?? null,
      customNormalize: ({ summary, http }) => ({
        community_id: summary.community_id ?? null,
        query_modes_tested: normalizeList(summary.query_modes_tested),
        browser_modes_tested: normalizeList(summary.browser_modes_tested),
        source_detail_loaded: summary.source_detail_loaded ?? null,
        community_link_surfaces_tested: normalizeList(summary.community_link_surfaces_tested),
        local_query_entities: normalizeList(summary.local_query_entities),
        hybrid_query_entities: normalizeList(summary.hybrid_query_entities),
        query_answer_excerpt: summary.query_answer_excerpt ?? null,
        context_community_count: summary.context_community_count ?? null,
        fake_ollama_embedding_requests_positive: Number(summary.fake_ollama_embedding_requests) >= 1,
        fake_ollama_generate_requests_positive: Number(summary.fake_ollama_generate_requests) >= 1,
        query_source_memory_matches_summary: summary.query_source_memory_id === summary.memory_id,
        query_source_community_matches_summary: summary.query_source_community_id === summary.community_id,
        memory_total: http.memories?.total ?? null,
        community_total: http.communities?.total ?? null,
        community_summary: http.communities?.communities?.[0]?.summary ?? null,
        query_answers: normalizeQueryModeMap(http.query_modes, (query) => query?.answer ?? null),
        query_community_ids: normalizeQueryModeMap(http.query_modes, (query) => queryCommunityIds(query)),
        query_source_community_ids: normalizeQueryModeMap(http.query_modes, (query) => querySourceCommunityIds(query)),
        local_entities: normalizeList(http.query_modes?.local?.entities),
        hybrid_entities: normalizeList(http.query_modes?.hybrid?.entities),
      }),
    }),
  }),
  'task-25': createTaskCase('task-25', {
    normalize: buildCommunityDetailNavigationNormalizer({
      customNormalize: ({ summary, http }) => ({
        memory_context_entities: summary.memory_context_entities ?? null,
        community_relationship_type: summary.community_relationship_type ?? null,
        memory_id_matches_detail: summary.memory_id === http.memory_detail?.id,
        memory_content: http.memory_detail?.content ?? null,
        memory_title: http.memory_detail?.metadata?.title ?? null,
      }),
    }),
  }),
  'task-27': createTaskCase('task-27', {
    normalize: buildSuccessfulCommunitySummaryRefreshNormalizer({
      customNormalize: ({ summary }) => ({
        fake_ollama_generate_requests_zero: Number(summary.fake_ollama_generate_requests) === 0,
      }),
    }),
  }),
  'task-28': createTaskCase('task-28', {
    normalize: buildSingleMemoryContextReadNormalizer({
      finalRouteResolver: (summary) => normalizeRouteWithIdPlaceholder(summary.final_url, summary.recent_memory_id),
      getMemoryContent: (http) => http.memory_detail?.content ?? null,
      customNormalize: ({ summary, http }) => ({
        total_entities: summary.total_entities ?? null,
        total_relationships: summary.total_relationships ?? null,
        total_memories: summary.total_memories ?? null,
        total_communities: summary.total_communities ?? null,
        recent_memories_total: summary.recent_memories_total ?? null,
        recent_item_navigation: summary.recent_item_navigation ?? null,
        detail_context_communities: summary.detail_context_communities ?? null,
        recent_memory_consistent:
          summary.recent_memory_id === http.memories?.memories?.[0]?.id
          && summary.recent_memory_id === http.memory_detail?.id,
        entity_types: http.stats?.entity_types ?? {},
        memory_title: http.memory_detail?.metadata?.title ?? null,
      }),
    }),
  }),
}
