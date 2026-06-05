import assert from 'node:assert/strict'

import {
  assertFocusedRealSmokeEvidenceSampleCase,
  getFocusedRealSmokeTaskGroupTaskIds,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildDeletedMemoryFailureAssertion,
  assertEvidenceFields,
  assertEvidencePathValues,
  buildMissingMemoryIdCommunityFallbackAssertion,
  buildNormalizedCommunityEvidenceAssertion,
  buildNormalizedCommunityMissingDetailAssertion,
  buildNormalizedCommunitySummaryRefreshAssertion,
  buildSuccessfulMemoryWriteLifecycleAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

export const REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID = Object.freeze({
  'task-26': (normalized) => {
    assertEvidenceFields(normalized, {
      total_entities: 2,
      total_relationships: 1,
      total_memories: 1,
      browser_node_count: 2,
      entity_types: { document: 1, person: 1 },
      entity_names: ['Launch Checklist', 'Alice'],
      relationship_types: ['owns'],
      relationship_total: 1,
      final_route: '/graph',
    }, 'task-26 normalized')
  },
  'task-29': buildNormalizedCommunitySummaryRefreshAssertion('task-29', {
    communityId: 'comm-launch-owners',
    initialSummaryField: 'initial_summary',
    initialSummaryValue: 'stale large summary should be replaced',
    refreshedSummaryValue: 'Launch Owners is a refreshed summary covering Alice, the launch checklist, and release coordination.',
    matchRefreshedFields: ['regenerate_summary', 'after_summary'],
    fieldAssertions: {
      profile: 'large_summary',
      entity_count: 4,
      fake_ollama_generate_requests: 1,
      before_title: 'Launch Owners',
      community_id_consistent: true,
    },
  }),
  'task-30': (normalized) => {
    assertEvidenceFields(normalized, {
      profile: 'multi_aggregate',
      community_ids: ['comm-launch-owners', 'comm-release-readiness'],
      total_entities: 5,
      total_relationships: 2,
      total_memories: 3,
      total_communities: 3,
      hierarchy_root_id: 'community_level_2_ba5a85d8972a',
      ancestor_total: 1,
      returned_memory_count: 3,
      recent_item_navigation: 'memory_detail',
      recent_memory_context_communities: 2,
      community_link_surface: 'result',
      browser_memory_source_count: 3,
      browser_community_source_count: 2,
      recent_memory_matches_detail: true,
      entity_types: { document: 3, person: 1, project: 1 },
      communities_titles: ['Launch Owners', 'Release Readiness', 'Level 2 Cluster 1'],
      memories_titles: ['QA readiness note', 'Release runbook note', 'Launch ownership note'],
      recent_memory_title: 'QA readiness note',
      memory_context_community_titles: ['Launch Owners', 'Release Readiness'],
      query_source_titles: ['Launch ownership note', 'QA readiness note', 'Release runbook note'],
      query_community_titles: ['Launch Owners', 'Release Readiness'],
      final_route: '/communities#comm-release-readiness',
    }, 'task-30 normalized')
  },
  'task-31': (normalized) => {
    assertEvidenceFields(normalized, {
      profile: 'memories_list',
      total_memories: 23,
      active_total: 19,
      archived_total: 4,
      page1_count: 20,
      page2_count: 3,
      final_route: '/memories',
    }, 'task-31 normalized')
    assertEvidencePathValues(normalized, {
      'active_titles.length': 19,
      'archived_titles.length': 4,
      'all_page_1_titles.length': 20,
      'all_page_2_titles.length': 3,
    }, 'task-31 normalized')
    assert.equal(normalized.active_titles.at(-1), 'Launch ownership note')
    assert.equal(normalized.archived_titles[0], 'List memory 22')
  },
  'task-32': (normalized) => {
    assertEvidenceFields(normalized, {
      total_communities: 3,
      hierarchy_total: 3,
      root_id: 'community_level_2_ba5a85d8972a',
      ancestors_total: 1,
      descendants_total: 2,
      communities_titles: ['Launch Owners', 'Release Readiness', 'Level 2 Cluster 1'],
      hierarchy_root_titles: ['Level 2 Cluster 1'],
      hierarchy_root_child_titles: ['Launch Owners', 'Release Readiness'],
      subtree_title: 'Level 2 Cluster 1',
      ancestor_titles: ['Level 2 Cluster 1'],
      descendant_titles: ['Launch Owners', 'Release Readiness'],
      final_route: '/communities#comm-release-readiness',
    }, 'task-32 normalized')
  },
  'task-33': buildDeletedMemoryFailureAssertion('task-33', {
    finalRoute: '/search',
    includeDeleteOutcomeFields: false,
    deleteStatusField: 'delete_status',
    detailStatusField: 'detail_status_after_delete',
    fieldAssertions: {
      delete_status: 200,
      query_answer: 'Alice owns the launch checklist and coordinates the release.',
      query_source_titles: ['Launch ownership note'],
      query_source_community_ids: ['comm-launch-owners'],
      delete_status_http: 200,
      detail_after_delete_status_http: 404,
    },
  }),
  'task-34': buildSuccessfulMemoryWriteLifecycleAssertion('task-34', {
    includeArchiveOutcomeFields: true,
    fieldAssertions: {
      profile: 'memories_list',
      active_before: 19,
      archived_before: 4,
      active_after_archive: 18,
      archived_after_archive: 5,
      active_after_unarchive: 19,
      archived_after_unarchive: 4,
      active_after_delete: 18,
      archived_after_delete: 4,
      total_after_delete: 22,
    },
    pathAssertions: {
      'active_before_titles.length': 19,
      'archived_before_titles.length': 4,
      'active_after_delete_titles.length': 18,
      'archived_after_delete_titles.length': 4,
    },
  }),
  'task-35': buildSuccessfulMemoryWriteLifecycleAssertion('task-35', {
    contextStatusAfterDelete: 404,
    includeArchiveOutcomeFields: true,
    fieldAssertions: {
      community_id: 'comm-launch-owners',
      active_before: 1,
      archived_before: 0,
      active_after_archive: 0,
      archived_after_archive: 1,
      active_after_unarchive: 1,
      archived_after_unarchive: 0,
      active_after_delete: 0,
      archived_after_delete: 0,
      total_after_delete: 0,
      memory_id_matches_detail: true,
      community_id_matches_context: true,
      memory_detail_title_before: 'Launch ownership note',
      memory_context_entity_names: ['Alice', 'Launch Checklist'],
      memory_context_community_titles: ['Launch Owners'],
      detail_archived_after_archive: true,
      detail_archived_after_unarchive: false,
    },
  }),
  'task-36': buildMissingMemoryIdCommunityFallbackAssertion('task-36', {
    communityId: 'comm-missing-memory-id',
    communityTitle: 'Launch Owners Without Memory',
    queryAnswer: 'Alice owns the launch checklist and coordinates the release.',
    fakeOllamaCounts: {
      tagRequests: 0,
      embeddingRequests: 16,
      generateRequests: 5,
    },
  }),
  'task-37': buildDeletedMemoryFailureAssertion('task-37', {
    deleteStatusField: 'delete_status',
    detailStatusField: 'deleted_detail_status',
    detailStatusPath: 'deleted_detail.status_code',
    contextStatusField: 'deleted_context_status',
    contextStatus: 404,
    contextStatusPath: 'deleted_context.status_code',
    fieldAssertions: {
      missing_memory_id: 'mem-missing-detail-real-smoke',
      missing_detail_status: 404,
      missing_context_status: 404,
      total_before_delete: 1,
      total_after_delete: 0,
      seeded_memory_matches_delete: true,
      seeded_detail_title: 'Launch ownership note',
      all_before_titles: ['Launch ownership note'],
      all_after_titles: [],
    },
    pathAssertions: {
      'missing_detail.status_code': 404,
      'missing_context.status_code': 404,
    },
  }),
  'task-38': buildNormalizedCommunityMissingDetailAssertion('task-38', {
    missingCommunityId: 'comm-missing-detail-real-smoke',
    fieldAssertions: {
      existing_community_id: 'comm-release-readiness',
      total_communities: 3,
      communities_titles: ['Launch Owners', 'Release Readiness', 'Level 2 Cluster 1'],
      existing_community_present: true,
    },
    pathAssertions: {
      'missing_detail.detail': 'Community comm-missing-detail-real-smoke not found',
    },
  }),
  'task-40': buildNormalizedCommunityEvidenceAssertion('task-40', {
    communityId: 'comm-release-readiness',
    communityTitle: 'Release Readiness',
    fieldAssertions: {
      ancestors_status: 500,
      descendants_status: 500,
      entities_status: 200,
      relationships_status: 200,
      entity_names: ['Integration Tests', 'Release Runbook', 'Deployment Approval'],
      relationship_types: ['depends_on'],
      entity_total: 3,
      relationship_total: 1,
    },
    pathAssertions: {
      'ancestors.detail': 'Failed to get community ancestors: QA forced failure for community ancestors: comm-release-readiness',
      'descendants.detail': 'Failed to get community descendants: QA forced failure for community descendants: comm-release-readiness',
    },
  }),
  'task-41': buildNormalizedCommunityEvidenceAssertion('task-41', {
    communityId: 'comm-release-readiness',
    communityTitle: 'Release Readiness',
    fieldAssertions: {
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      ancestor_titles: ['Level 2 Cluster 1'],
      ancestor_total: 1,
      descendant_titles: [],
      descendant_total: 0,
    },
    pathAssertions: {
      'entities.detail': 'Failed to get community entities: QA forced failure for community entities: comm-release-readiness',
      'relationships.detail': 'Failed to get community relationships: QA forced failure for community relationships: comm-release-readiness',
    },
  }),
  'task-43': buildNormalizedCommunitySummaryRefreshAssertion('task-43', {
    initialSummaryValue: 'Runbook, approvals, and QA readiness artifacts.',
    refreshedSummaryValue: 'Launch Owners is a refreshed summary covering Alice, the launch checklist, and release coordination.',
    fieldAssertions: {
      target_community_id: 'comm-release-readiness',
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      before_title: 'Release Readiness',
      after_title: 'Release Readiness',
      ancestor_titles: ['Level 2 Cluster 1'],
      ancestor_total: 1,
      descendant_total: 0,
      final_route: '/communities#comm-release-readiness',
    },
    pathAssertions: {
      'entities.detail': 'Failed to get community entities: QA forced failure for community entities: comm-release-readiness',
      'relationships.detail': 'Failed to get community relationships: QA forced failure for community relationships: comm-release-readiness',
    },
  }),
  'task-56': buildSuccessfulMemoryWriteLifecycleAssertion('task-56', {
    contextStatusAfterDelete: 404,
    includeArchiveOutcomeFields: true,
    fieldAssertions: {
      navigation_surface: 'search_memory_link',
      query_source_matches_recent: true,
      active_before: 1,
      archived_before: 0,
      active_after_archive: 0,
      archived_after_archive: 1,
      active_after_unarchive: 1,
      archived_after_unarchive: 0,
      active_after_delete: 0,
      archived_after_delete: 0,
      total_after_delete: 0,
      query_answer: 'Alice owns the launch checklist and coordinates the release.',
      query_source_titles: ['Launch ownership note'],
      memory_detail_title: 'Launch ownership note',
      memory_context_entity_names: ['Alice', 'Launch Checklist'],
      delete_memory_matches_recent: true,
    },
  }),
  'task-57': buildDeletedMemoryFailureAssertion('task-57', {
    deleteStatusField: 'delete_status',
    detailStatusField: 'detail_status_after_delete',
    detailStatusPath: 'detail_after_delete.status_code',
    contextStatusField: 'context_status_after_delete',
    contextStatus: 404,
    contextStatusPath: 'context_after_delete.status_code',
    fieldAssertions: {
      navigation_surface: 'search_memory_link',
      query_source_matches_recent: true,
      total_after_delete: 0,
      query_answer: 'Alice owns the launch checklist and coordinates the release.',
      query_source_titles: ['Launch ownership note'],
      delete_memory_matches_recent: true,
      all_after_titles: [],
    },
  }),
})

export const REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS = Object.freeze(
  getFocusedRealSmokeTaskGroupTaskIds('remaining-web-focused')
)

export function assertRemainingWebFocusedEvidenceSample(taskId, normalized) {
  assertFocusedRealSmokeEvidenceSampleCase(
    taskId,
    normalized,
    REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    'remaining-web-focused evidence sample assertion'
  )
}
