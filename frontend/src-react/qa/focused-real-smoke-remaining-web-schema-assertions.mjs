import {
  assertFocusedRealSmokeSchemaCase,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSuccessfulCommunitySummaryRefreshSchemaCase,
} from './focused-real-smoke-community-summary-refresh-contract-helpers.mjs'

function buildRemainingWebMemoryWriteSchemaCase({
  summaryKeys = [],
  includeArchiveMutationPayloads = true,
  includeArchiveDetailHttp = false,
  includeContextAfterDeleteHttp = false,
  httpKeys = [],
} = {}) {
  return {
    summaryKeys: [
      'active_before',
      'archived_before',
      'active_after_archive',
      'archived_after_archive',
      'active_after_unarchive',
      'archived_after_unarchive',
      'active_after_delete',
      'archived_after_delete',
      'total_after_delete',
      'detail_status_after_delete',
      ...summaryKeys,
    ],
    httpKeys: [
      'health',
      'active_before',
      'archived_before',
      ...(includeArchiveMutationPayloads ? ['archive'] : []),
      ...(includeArchiveDetailHttp ? ['detail_after_archive'] : []),
      'active_after_archive',
      'archived_after_archive',
      ...(includeArchiveMutationPayloads ? ['unarchive'] : []),
      ...(includeArchiveDetailHttp ? ['detail_after_unarchive'] : []),
      'active_after_unarchive',
      'archived_after_unarchive',
      'delete',
      'detail_after_delete',
      ...(includeContextAfterDeleteHttp ? ['context_after_delete'] : []),
      'active_after_delete',
      'archived_after_delete',
      'all_after_delete',
      ...httpKeys,
    ],
  }
}

function buildRemainingWebMemoryDeleteFailureSchemaCase({
  summaryKeys = [],
  includeAfterDeleteStatusFields = true,
  detailHttpKey = 'detail_after_delete',
  contextHttpKey = 'context_after_delete',
  httpKeys = [],
} = {}) {
  return {
    summaryKeys: [
      'delete_status',
      ...(includeAfterDeleteStatusFields ? ['detail_status_after_delete', 'context_status_after_delete'] : []),
      'total_after_delete',
      ...summaryKeys,
    ],
    httpKeys: [
      'health',
      'delete',
      detailHttpKey,
      contextHttpKey,
      'all_after_delete',
      ...httpKeys,
    ],
  }
}

function buildRemainingWebCommunityFailureSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'community_detail', 'ancestors', 'descendants', 'entities', 'relationships'],
} = {}) {
  return {
    summaryKeys: [
      'target_community_id',
      'ancestors_status',
      'descendants_status',
      'entities_status',
      'relationships_status',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

function buildRemainingWebCommunitySummaryRefreshSchemaCase({
  summaryKeys = [],
  httpKeys = ['health', 'before_summary', 'entities', 'relationships', 'ancestors', 'descendants', 'after_summary'],
} = {}) {
  return {
    summaryKeys: [
      'target_community_id',
      'before_summary',
      'refreshed_summary',
      'entities_status',
      'relationships_status',
      'ancestors_status',
      'descendants_status',
      ...summaryKeys,
    ],
    httpKeys,
  }
}

export const REMAINING_WEB_SCHEMA_CASES_BY_TASK_ID = Object.freeze({
  'task-26': {
    summaryKeys: ['total_entities', 'total_relationships', 'total_memories', 'browser_node_count'],
    httpKeys: ['health', 'stats', 'entities', 'relationships'],
  },
  'task-29': buildSuccessfulCommunitySummaryRefreshSchemaCase({
    summaryKeys: ['profile', 'entity_count'],
  }),
  'task-30': {
    summaryKeys: [
      'profile',
      'memory_ids',
      'community_ids',
      'total_entities',
      'total_relationships',
      'total_memories',
      'total_communities',
      'hierarchy_root_id',
      'ancestor_total',
      'returned_memory_ids',
      'recent_memory_id',
      'recent_item_navigation',
      'recent_memory_context_communities',
      'community_link_surface',
      'browser_memory_source_count',
      'browser_community_source_count',
    ],
    httpKeys: ['health', 'stats', 'communities', 'memories', 'memory_detail', 'memory_context', 'query'],
  },
  'task-31': {
    summaryKeys: ['profile', 'total_memories', 'active_total', 'archived_total', 'page1_count', 'page2_count'],
    httpKeys: ['health', 'active', 'archived', 'all_page_1', 'all_page_2'],
  },
  'task-32': {
    summaryKeys: ['total_communities', 'hierarchy_total', 'root_id', 'ancestors_total', 'descendants_total'],
    httpKeys: ['health', 'communities', 'hierarchy', 'subtree', 'ancestors', 'descendants'],
  },
  'task-33': {
    summaryKeys: ['memory_id', 'delete_status', 'detail_status_after_delete'],
    httpKeys: ['health', 'query', 'deleted', 'detail_after_delete'],
  },
  'task-34': buildRemainingWebMemoryWriteSchemaCase({
    summaryKeys: ['profile', 'archive_target_id', 'delete_target_id'],
  }),
  'task-35': buildRemainingWebMemoryWriteSchemaCase({
    summaryKeys: ['memory_id', 'community_id', 'context_status_after_delete'],
    includeArchiveDetailHttp: true,
    includeContextAfterDeleteHttp: true,
    httpKeys: ['memory_detail_before', 'memory_context_before', 'all_before'],
  }),
  'task-36': {
    summaryKeys: [
      'community_id',
      'query_modes_tested',
      'global_query_source_memory_id',
      'local_query_source_memory_id',
      'hybrid_query_source_memory_id',
      'link_surface',
      'memory_detail_requests',
      'memory_link_count',
    ],
    httpKeys: ['health', 'communities', 'memories', 'query_global', 'query_local', 'query_hybrid', 'community_detail', 'fake_ollama_counts'],
  },
  'task-37': buildRemainingWebMemoryDeleteFailureSchemaCase({
    includeAfterDeleteStatusFields: false,
    detailHttpKey: 'deleted_detail',
    contextHttpKey: 'deleted_context',
    summaryKeys: [
      'seeded_memory_id',
      'missing_memory_id',
      'missing_detail_status',
      'missing_context_status',
      'deleted_detail_status',
      'deleted_context_status',
      'total_before_delete',
    ],
    httpKeys: ['seeded_detail', 'missing_detail', 'missing_context', 'all_before_delete'],
  }),
  'task-38': {
    summaryKeys: ['existing_community_id', 'missing_community_id', 'missing_detail_status', 'total_communities'],
    httpKeys: ['health', 'communities', 'missing_detail'],
  },
  'task-40': buildRemainingWebCommunityFailureSchemaCase(),
  'task-41': buildRemainingWebCommunityFailureSchemaCase(),
  'task-43': buildRemainingWebCommunitySummaryRefreshSchemaCase(),
  'task-56': buildRemainingWebMemoryWriteSchemaCase({
    summaryKeys: ['recent_memory_id', 'navigation_surface', 'query_source_memory_id', 'context_status_after_delete'],
    includeArchiveMutationPayloads: false,
    includeArchiveDetailHttp: true,
    includeContextAfterDeleteHttp: true,
    httpKeys: ['query', 'memory_detail', 'memory_context'],
  }),
  'task-57': buildRemainingWebMemoryDeleteFailureSchemaCase({
    summaryKeys: ['recent_memory_id', 'navigation_surface', 'query_source_memory_id'],
    httpKeys: ['query'],
  }),
})

export function assertFocusedRealSmokeRemainingWebSchemaContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeSchemaCase(
    taskId,
    qaScriptFile,
    source,
    REMAINING_WEB_SCHEMA_CASES_BY_TASK_ID,
    'remaining-web schema contract case'
  )
}
