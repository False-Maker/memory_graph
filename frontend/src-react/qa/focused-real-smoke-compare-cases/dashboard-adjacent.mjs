import {
  buildCommunityDetailNavigationNormalizer,
  buildDashboardCommunitiesStatsNormalizer,
  buildDashboardGraphStatsNormalizer,
  buildDashboardMemoriesStatsNormalizer,
  buildDashboardRecentMemoryDeleteFailureNormalizer,
  buildDashboardRecentMemoryWriteNormalizer,
  createTaskCase,
  entityNames,
  itemTitles,
  memoryTitles,
  normalizeHealth,
  normalizeList,
  normalizeMissingDetail,
  normalizeUrlPathAndHash,
  relationshipTriples,
} from './helpers.mjs'

export const DASHBOARD_ADJACENT_TASK_CASES = {
  'task-45': createTaskCase('task-45', {
    normalize: buildDashboardRecentMemoryDeleteFailureNormalizer(),
  }),
  'task-46': createTaskCase('task-46', {
    normalize: buildDashboardRecentMemoryWriteNormalizer(),
  }),
  'task-47': createTaskCase('task-47', {
    normalize: buildCommunityDetailNavigationNormalizer({
      customNormalize: ({ summary, http }) => ({
        navigation_path: summary.navigation_path ?? null,
        recent_memory_matches_detail:
          summary.recent_memory_id === http.recent_memories?.memories?.[0]?.id
          && summary.recent_memory_id === http.memory_detail?.id,
        community_id_matches_detail:
          summary.community_id === http.memory_context?.communities?.[0]?.id
          && summary.community_id === http.community_detail?.id,
        recent_titles: memoryTitles(http.recent_memories?.memories),
        memory_detail_title: http.memory_detail?.metadata?.title ?? null,
      }),
    }),
  }),
  'task-48': createTaskCase('task-48', {
    normalize: buildDashboardMemoriesStatsNormalizer({
      includeTotalMemories: false,
      includeEntityTypes: false,
      includeCommunitiesTotal: false,
      customNormalize: ({ summary, http }) => ({
        profile: summary.profile ?? null,
        recent_memories_total: summary.recent_memories_total ?? null,
        recent_memories_visible: summary.recent_memories_visible ?? null,
        active_list_total: summary.active_list_total ?? null,
        active_list_visible: summary.active_list_visible ?? null,
        recent_titles_visible: memoryTitles(http.recent_memories?.memories),
        active_titles_visible: memoryTitles(http.memories_list?.memories),
        first_recent_memory_title: http.recent_memories?.memories?.[0]?.metadata?.title ?? null,
        first_active_memory_title: http.memories_list?.memories?.[0]?.metadata?.title ?? null,
      }),
    }),
  }),
  'task-49': createTaskCase('task-49', {
    normalize: buildDashboardGraphStatsNormalizer({
      includeTotalCommunities: true,
      includeRecentMemoriesTotal: false,
      includeCommunitiesTotal: false,
      customNormalize: ({ summary, http }) => ({
        graph_entity_count: summary.graph_entity_count ?? null,
        graph_relationship_count: summary.graph_relationship_count ?? null,
        memories_list_total: summary.memories_list_total ?? null,
        graph_entity_names: entityNames(http.graph_entities?.entities),
        graph_relationship_types: normalizeList(http.graph_relationships?.relationships, (item) => item?.type).filter(Boolean),
        graph_relationship_total: http.graph_relationships?.total ?? null,
        memories_titles: memoryTitles(http.memories?.memories),
        communities_titles: itemTitles(http.communities?.communities),
      }),
    }),
  }),
  'task-50': createTaskCase('task-50', {
    normalize: buildDashboardGraphStatsNormalizer({
      includeTotalCommunities: true,
      customNormalize: ({ summary }) => ({
        graph_entity_count: summary.graph_entity_count ?? null,
        graph_relationship_count: summary.graph_relationship_count ?? null,
      }),
    }),
  }),
  'task-51': createTaskCase('task-51', {
    normalize: buildDashboardCommunitiesStatsNormalizer({
      includeTotalCommunities: true,
      customNormalize: ({ summary, http }) => ({
        hierarchy_total: summary.hierarchy_total ?? null,
        communities_titles: itemTitles(http.communities?.communities),
        hierarchy_roots: itemTitles(http.hierarchy?.roots),
        hierarchy_levels: http.hierarchy?.levels ?? null,
      }),
    }),
  }),
  'task-52': createTaskCase('task-52', {
    normalize: buildDashboardMemoriesStatsNormalizer({
      includeEntityRelationshipTotals: true,
      includeTotalCommunities: true,
      customNormalize: ({ summary, http }) => ({
        recent_memories_total: summary.recent_memories_total ?? null,
        active_list_total: summary.active_list_total ?? null,
        recent_titles: memoryTitles(http.recent_memories?.memories),
        active_titles: memoryTitles(http.memories_list?.memories),
      }),
    }),
  }),
  'task-53': createTaskCase('task-53', {
    normalize: buildDashboardMemoriesStatsNormalizer({
      customNormalize: ({ summary, http }) => ({
        recent_memories_status: summary.recent_memories_status ?? null,
        active_list_status: summary.active_list_status ?? null,
        error_detail: summary.error_detail ?? null,
        recent_memories: normalizeMissingDetail(http.recent_memories),
        memories_list: normalizeMissingDetail(http.memories_list),
      }),
    }),
  }),
  'task-54': createTaskCase('task-54', {
    normalize: buildDashboardCommunitiesStatsNormalizer({
      customNormalize: ({ summary, http }) => ({
        communities_list_status: summary.communities_list_status ?? null,
        hierarchy_status: summary.hierarchy_status ?? null,
        list_error_detail: summary.list_error_detail ?? null,
        hierarchy_error_detail: summary.hierarchy_error_detail ?? null,
        communities: normalizeMissingDetail(http.communities),
        hierarchy: normalizeMissingDetail(http.hierarchy),
      }),
    }),
  }),
  'task-55': createTaskCase('task-55', {
    normalize: buildDashboardGraphStatsNormalizer({
      customNormalize: ({ summary, http }) => ({
        graph_entities_status: summary.graph_entities_status ?? null,
        graph_relationships_status: summary.graph_relationships_status ?? null,
        entities_error_detail: summary.entities_error_detail ?? null,
        relationships_error_detail: summary.relationships_error_detail ?? null,
        graph_entities: normalizeMissingDetail(http.graph_entities),
        graph_relationships: normalizeMissingDetail(http.graph_relationships),
      }),
    }),
  }),
}
