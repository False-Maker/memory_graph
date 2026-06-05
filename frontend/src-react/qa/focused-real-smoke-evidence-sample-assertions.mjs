import assert from 'node:assert/strict'
import { assertFocusedRealSmokeEvidenceSampleCase } from './focused-real-smoke-contract-helpers.mjs'
import {
  buildHighSignalCommunityDetailNavigationEvidenceAssertion,
  buildHighSignalCommunityDataFailureEvidenceAssertion,
  buildHighSignalCommunityMissingDetailEvidenceAssertion,
  buildHighSignalSingleMemoryContextEvidenceAssertion,
  buildHighSignalCommunitySummaryRefreshEvidenceAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

export const EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID = Object.freeze({
  'task-24': buildHighSignalSingleMemoryContextEvidenceAssertion('task-24', {
    summaryMemoryIdField: 'memory_id',
    memoryIdHttpPath: 'query_modes.global.sources.0.memory_id',
    memoryIdMirrorSummaryFields: ['query_source_memory_id'],
    contextCountField: 'context_community_count',
    summaryCommunityIdField: 'community_id',
    communityIdHttpPath: 'query_modes.global.sources.0.community_id',
    communityIdMirrorSummaryFields: ['query_source_community_id'],
    fieldAssertions: {
      query_modes_tested: ['global', 'local', 'hybrid'],
      browser_modes_tested: ['global', 'local', 'hybrid'],
      community_link_surfaces_tested: ['source', 'result'],
      source_detail_loaded: true,
    },
    customAssert: ({ summary }) => {
      assert.ok(summary.fake_ollama_embedding_requests >= 1)
      assert.ok(summary.fake_ollama_generate_requests >= 1)
    },
  }),
  'task-25': buildHighSignalCommunityDetailNavigationEvidenceAssertion('task-25', {
    fieldAssertions: {
      community_relationship_type: 'owns',
    },
  }),
  'task-27': buildHighSignalCommunitySummaryRefreshEvidenceAssertion('task-27', {
    beforeSummaryField: 'initial_summary',
    communityIdField: 'community_id',
    communityIdHttpPath: 'before_summary.id',
    refreshedSummaryMirrorHttpPath: 'regenerate.summary',
    finalUrlCommunityField: 'community_id',
  }),
  'task-28': buildHighSignalSingleMemoryContextEvidenceAssertion('task-28', {
    summaryMemoryIdField: 'recent_memory_id',
    memoryIdHttpPath: 'memory_detail.id',
    additionalMemoryIdHttpPaths: ['memories.memories.0.id'],
    contextCountField: 'detail_context_communities',
    fieldAssertions: {
      total_entities: 2,
      total_relationships: 1,
      total_memories: 1,
      total_communities: 1,
      recent_memories_total: 1,
      recent_item_navigation: 'memory_detail',
    },
  }),
  'task-39': buildHighSignalCommunityMissingDetailEvidenceAssertion('task-39', {
    linkSurface: 'source',
    matchingSummaryFields: ['query_source_community_id', 'query_hit_community_id'],
  }),
  'task-42': buildHighSignalCommunityDataFailureEvidenceAssertion('task-42', {
    linkSurface: 'result',
    includeQueryCommunityMembership: true,
  }),
  'task-44': buildHighSignalCommunitySummaryRefreshEvidenceAssertion('task-44', {
    linkSurface: 'result',
    includeQueryCommunityMembership: true,
    includeEntityRelationshipStatuses: true,
  }),
  'task-58': buildHighSignalCommunitySummaryRefreshEvidenceAssertion('task-58', {
    linkSurface: 'source',
    matchingSummaryField: 'query_source_community_id',
  }),
  'task-59': buildHighSignalCommunityMissingDetailEvidenceAssertion('task-59', {
    linkSurface: 'result',
    matchingSummaryFields: ['query_hit_community_id'],
  }),
  'task-60': buildHighSignalCommunityDataFailureEvidenceAssertion('task-60', {
    linkSurface: 'source',
    matchingSummaryField: 'query_source_community_id',
    includeCommunityTitle: true,
  }),
})

export function assertFocusedRealSmokeEvidenceSample(taskId, evidence) {
  assertFocusedRealSmokeEvidenceSampleCase(taskId, evidence, EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID, 'evidence sample assertion')
}
