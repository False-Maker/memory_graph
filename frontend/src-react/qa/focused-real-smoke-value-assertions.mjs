import { assertFocusedRealSmokeValueCase } from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSuccessfulCommunitySummaryRefreshValueCase,
} from './focused-real-smoke-community-summary-refresh-contract-helpers.mjs'
import {
  buildCommunityDetailNavigationValueCase,
} from './focused-real-smoke-community-detail-navigation-contract-helpers.mjs'
import {
  buildSingleMemoryContextValueCase,
} from './focused-real-smoke-single-memory-context-contract-helpers.mjs'
import {
  buildHighSignalCommunityDataFailureValueCase,
  buildHighSignalCommunityMissingDetailValueCase,
  buildHighSignalCommunitySummaryRefreshValueCase,
} from './focused-real-smoke-high-signal-search-community-contract-helpers.mjs'

export const VALUE_CONTRACT_CASES_BY_TASK_ID = Object.freeze({
  'task-24': buildSingleMemoryContextValueCase({
    memoryIdPattern: /memory_id:\s*seedPayload\.memory_id/,
    contextCountPattern: /context_community_count:\s*httpEvidence\.memoryContext\.json\?\.total_communities/,
    patterns: [
      /query_modes_tested:\s*Object\.keys\(httpEvidence\.queryModes\)/,
      /browser_modes_tested:\s*browserEvidence\.browserModesTested/,
      /source_detail_loaded:\s*browserEvidence\.sourceDetailLoaded/,
      /query_source_memory_id:\s*httpEvidence\.queryModes\.global\.json\?\.\s*sources\?\.\[0\]\?\.\s*memory_id/,
      /query_source_community_id:\s*httpEvidence\.queryModes\.global\.json\?\.\s*sources\?\.\[0\]\?\.\s*community_id/,
      /community_link_surfaces_tested:\s*\['source', 'result'\]/,
      /query_answer_excerpt:\s*String\(httpEvidence\.queryModes\.hybrid\.json\?\.answer\s*\|\|\s*''\)\.slice\(0,\s*120\)/,
      /fake_ollama_embedding_requests:\s*httpEvidence\.fakeOllamaCounts\.embeddingRequests/,
      /fake_ollama_generate_requests:\s*httpEvidence\.fakeOllamaCounts\.generateRequests/,
      /query_modes:\s*\{\s*global:\s*httpEvidence\.queryModes\.global\.json,\s*local:\s*httpEvidence\.queryModes\.local\.json,\s*hybrid:\s*httpEvidence\.queryModes\.hybrid\.json,\s*\}/s,
    ],
  }),
  'task-25': buildCommunityDetailNavigationValueCase({
    patterns: [
      /memory_id:\s*seedPayload\.memory_id/,
      /memory_context_entities:\s*httpEvidence\.memoryContext\.json\?\.total_entities/,
      /community_relationship_type:\s*httpEvidence\.communityRelationships\.json\?\.\s*relationships\?\.\[0\]\?\.\s*type/,
    ],
  }),
  'task-27': buildSuccessfulCommunitySummaryRefreshValueCase({
    patterns: [
      /const\s+REFRESHED_SUMMARY\s*=\s*'This small community contains 2 entities: Alice, Launch Checklist\.'/,
      /regenerate\.json\?\.summary\s*===\s*REFRESHED_SUMMARY/,
      /afterSummary\.json\?\.summary\s*===\s*REFRESHED_SUMMARY/,
      /fake_ollama_generate_requests:\s*ollamaCounts\.generateRequests/,
    ],
  }),
  'task-28': buildSingleMemoryContextValueCase({
    memoryIdPattern: /recent_memory_id:\s*seedPayload\.memory_id/,
    contextCountPattern: /detail_context_communities:\s*httpEvidence\.memoryContext\.json\?\.total_communities/,
    patterns: [
      /total_entities:\s*httpEvidence\.stats\.json\?\.total_entities/,
      /total_relationships:\s*httpEvidence\.stats\.json\?\.total_relationships/,
      /total_memories:\s*httpEvidence\.stats\.json\?\.total_memories/,
      /total_communities:\s*httpEvidence\.communities\.json\?\.total/,
      /recent_memories_total:\s*httpEvidence\.memories\.json\?\.total/,
      /recent_item_navigation:\s*'memory_detail'/,
      /memory_detail:\s*httpEvidence\.memoryDetail\.json/,
    ],
  }),
  'task-39': buildHighSignalCommunityMissingDetailValueCase({
    linkSurface: 'source',
    includeQuerySourceCommunityId: true,
    includeQueryHitCommunityId: true,
  }),
  'task-42': buildHighSignalCommunityDataFailureValueCase({
    linkSurface: 'result',
    includeQueryCommunityIds: true,
    includeAncestorDescendantStatusPatterns: true,
    includeRelationshipsPattern: true,
  }),
  'task-44': buildHighSignalCommunitySummaryRefreshValueCase({
    linkSurface: 'result',
    includeQueryCommunityIds: true,
    includeEntityRelationshipStatusPatterns: true,
  }),
  'task-58': buildHighSignalCommunitySummaryRefreshValueCase({
    linkSurface: 'source',
    includeQuerySourceCommunityId: true,
  }),
  'task-59': buildHighSignalCommunityMissingDetailValueCase({
    linkSurface: 'result',
    includeQueryHitCommunityId: true,
  }),
  'task-60': buildHighSignalCommunityDataFailureValueCase({
    linkSurface: 'source',
    includeQuerySourceCommunityId: true,
    includeCommunityTitle: true,
    includeCommunityDetailPattern: true,
  }),
})

export function assertFocusedRealSmokeValueContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeValueCase(taskId, qaScriptFile, source, VALUE_CONTRACT_CASES_BY_TASK_ID)
}
