import {
  assertFocusedRealSmokeSchemaCase,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSuccessfulCommunitySummaryRefreshSchemaCase,
} from './focused-real-smoke-community-summary-refresh-contract-helpers.mjs'
import {
  buildCommunityDetailNavigationSchemaCase,
} from './focused-real-smoke-community-detail-navigation-contract-helpers.mjs'
import {
  buildSingleMemoryContextSchemaCase,
} from './focused-real-smoke-single-memory-context-contract-helpers.mjs'
import {
  buildHighSignalCommunityDataFailureSchemaCase,
  buildHighSignalCommunityMissingDetailSchemaCase,
  buildHighSignalCommunitySummaryRefreshSchemaCase,
} from './focused-real-smoke-high-signal-search-community-contract-helpers.mjs'

export const SCHEMA_CASES_BY_TASK_ID = Object.freeze({
  'task-24': buildSingleMemoryContextSchemaCase({
    summaryMemoryIdKey: 'memory_id',
    summaryContextCountKey: 'context_community_count',
    includeCommunityId: true,
    extraSummaryKeys: [
      'query_modes_tested',
      'browser_modes_tested',
      'source_detail_loaded',
      'query_source_memory_id',
      'query_source_community_id',
      'community_link_surfaces_tested',
      'fake_ollama_embedding_requests',
      'fake_ollama_generate_requests',
    ],
    httpKeys: ['memories', 'query_modes'],
  }),
  'task-25': buildCommunityDetailNavigationSchemaCase({
    summaryKeys: ['memory_id', 'memory_context_entities', 'community_relationship_type'],
  }),
  'task-27': buildSuccessfulCommunitySummaryRefreshSchemaCase(),
  'task-28': buildSingleMemoryContextSchemaCase({
    summaryMemoryIdKey: 'recent_memory_id',
    summaryContextCountKey: 'detail_context_communities',
    extraSummaryKeys: [
      'total_entities',
      'total_relationships',
      'total_memories',
      'total_communities',
      'recent_memories_total',
      'recent_item_navigation',
    ],
    httpKeys: ['stats', 'memories', 'memory_detail'],
  }),
  'task-39': buildHighSignalCommunityMissingDetailSchemaCase({
    includeQuerySourceCommunityId: true,
    includeQueryHitCommunityId: true,
  }),
  'task-42': buildHighSignalCommunityDataFailureSchemaCase({
    includeQueryCommunityIds: true,
  }),
  'task-44': buildHighSignalCommunitySummaryRefreshSchemaCase({
    includeQueryCommunityIds: true,
  }),
  'task-58': buildHighSignalCommunitySummaryRefreshSchemaCase({
    includeQuerySourceCommunityId: true,
  }),
  'task-59': buildHighSignalCommunityMissingDetailSchemaCase({
    includeQueryHitCommunityId: true,
  }),
  'task-60': buildHighSignalCommunityDataFailureSchemaCase({
    includeQuerySourceCommunityId: true,
    includeCommunityTitle: true,
  }),
})

export function assertFocusedRealSmokeSchemaContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeSchemaCase(taskId, qaScriptFile, source, SCHEMA_CASES_BY_TASK_ID, 'schema contract case')
}
