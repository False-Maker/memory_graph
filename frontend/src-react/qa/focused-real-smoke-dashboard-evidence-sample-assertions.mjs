import {
  assertFocusedRealSmokeEvidenceSampleCase,
  getFocusedRealSmokeTaskGroupTaskIds,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildDashboardCommunitiesStatsEvidenceAssertion,
  buildDashboardGraphStatsEvidenceAssertion,
  buildDashboardMemoriesStatsEvidenceAssertion,
  buildDeletedMemoryFailureAssertion,
  buildNormalizedCommunityDetailNavigationAssertion,
  buildSuccessfulMemoryWriteLifecycleAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

export const DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID = Object.freeze({
  'task-45': buildDeletedMemoryFailureAssertion('task-45', {
    finalRoute: '/dashboard',
    detailStatusPath: 'deleted_detail.status_code',
    contextStatus: 404,
    contextStatusPath: 'deleted_context.status_code',
    fieldAssertions: {
      navigation_surface: 'dashboard_recent_item',
      stale_memory_matches_delete: true,
      recent_total_before_delete: 1,
      recent_total_after_delete: 0,
      refreshed_dashboard_empty: true,
      seeded_detail_title: 'Launch ownership note',
      recent_memory_titles_before_delete: ['Launch ownership note'],
      recent_memory_ids_after_delete: [],
    },
  }),
  'task-46': buildSuccessfulMemoryWriteLifecycleAssertion('task-46', {
    finalRoute: '/dashboard',
    contextStatusAfterDelete: 404,
    fieldAssertions: {
      navigation_surface: 'dashboard_recent_item',
      recent_memory_matches_detail: true,
      active_before: 1,
      archived_before: 0,
      active_after_archive: 0,
      archived_after_archive: 1,
      active_after_unarchive: 1,
      archived_after_unarchive: 0,
      active_after_delete: 0,
      archived_after_delete: 0,
      total_after_delete: 0,
      detail_archived_after_archive: true,
      detail_archived_after_unarchive: false,
      delete_memory_id_matches_summary: true,
      refreshed_dashboard_empty: true,
    },
  }),
  'task-47': buildNormalizedCommunityDetailNavigationAssertion('task-47', {
    communityId: 'comm-launch-owners',
    communityTitle: 'Launch Owners',
    communitySummary: 'Alice owns the launch checklist and release coordination.',
    memoryContextEntityNames: ['Alice', 'Launch Checklist'],
    communityEntityNames: ['Alice', 'Launch Checklist'],
    communityRelationships: [{ source: 'Alice', target: 'Launch Checklist', type: 'owns' }],
    memoryContextCommunities: 1,
    communityEntitiesTotal: 2,
    communityRelationshipsTotal: 1,
    ancestorsTotal: 0,
    descendantsTotal: 0,
    fieldAssertions: {
      navigation_path: 'dashboard_recent_item,memory_detail,community_detail',
      recent_memory_matches_detail: true,
      memory_detail_title: 'Launch ownership note',
    },
  }),
  'task-48': buildDashboardMemoriesStatsEvidenceAssertion('task-48', {
    navigationSurface: 'dashboard_view_all',
    includeTotalMemories: false,
    includeEntityTypes: false,
    includeCommunitiesTotal: false,
    fieldAssertions: {
      profile: 'memories_list',
      recent_memories_total: 19,
      recent_memories_visible: 10,
      active_list_total: 19,
      active_list_visible: 19,
      first_recent_memory_title: 'List memory 21',
      first_active_memory_title: 'List memory 21',
    },
    pathAssertions: {
      'recent_titles_visible.length': 10,
      'active_titles_visible.length': 19,
    },
  }),
  'task-49': buildDashboardGraphStatsEvidenceAssertion('task-49', {
    navigationSurfaces: [
      'entities->graph',
      'relationships->graph',
      'memories->memories',
      'communities->communities',
    ],
    finalRoute: '/communities',
    includeTotalCommunities: true,
    includeRecentMemoriesTotal: false,
    includeCommunitiesTotal: false,
    fieldAssertions: {
      total_entities: 2,
      total_relationships: 1,
      total_memories: 1,
      total_communities: 1,
      graph_entity_count: 2,
      graph_relationship_count: 1,
      graph_relationship_total: 1,
      memories_list_total: 1,
      entity_types: { document: 1, person: 1 },
      graph_entity_names: ['Launch Checklist', 'Alice'],
      graph_relationship_types: ['owns'],
      memories_titles: ['Launch ownership note'],
      communities_titles: ['Launch Owners'],
    },
  }),
  'task-50': buildDashboardGraphStatsEvidenceAssertion('task-50', {
    navigationSurfaces: ['entities->graph_empty', 'relationships->graph_empty'],
    includeTotalCommunities: true,
    fieldAssertions: {
      graph_entity_count: 0,
      graph_relationship_count: 0,
    },
  }),
  'task-51': buildDashboardCommunitiesStatsEvidenceAssertion('task-51', {
    navigationSurface: 'communities->communities_empty',
    includeTotalCommunities: true,
    fieldAssertions: {
      hierarchy_total: 0,
      communities_titles: [],
      hierarchy_roots: [],
      hierarchy_levels: 0,
    },
  }),
  'task-52': buildDashboardMemoriesStatsEvidenceAssertion('task-52', {
    navigationSurface: 'memories->memories_empty',
    includeEntityRelationshipTotals: true,
    includeTotalCommunities: true,
    fieldAssertions: {
      recent_memories_total: 0,
      active_list_total: 0,
      recent_titles: [],
      active_titles: [],
    },
  }),
  'task-53': buildDashboardMemoriesStatsEvidenceAssertion('task-53', {
    navigationSurface: 'memories->memories_failure',
    fieldAssertions: {
      recent_memories_status: 500,
      active_list_status: 500,
      error_detail: 'QA forced failure for memories list',
    },
    pathAssertions: {
      'recent_memories.status_code': 500,
      'recent_memories.detail': 'QA forced failure for memories list',
      'memories_list.status_code': 500,
      'memories_list.detail': 'QA forced failure for memories list',
    },
  }),
  'task-54': buildDashboardCommunitiesStatsEvidenceAssertion('task-54', {
    navigationSurface: 'communities->communities_failure',
    fieldAssertions: {
      communities_list_status: 500,
      hierarchy_status: 500,
      list_error_detail: 'Failed to list communities: QA forced failure for communities list',
      hierarchy_error_detail: 'Failed to get hierarchy: QA forced failure for communities hierarchy',
    },
    pathAssertions: {
      'communities.status_code': 500,
      'communities.detail': 'Failed to list communities: QA forced failure for communities list',
      'hierarchy.status_code': 500,
      'hierarchy.detail': 'Failed to get hierarchy: QA forced failure for communities hierarchy',
    },
  }),
  'task-55': buildDashboardGraphStatsEvidenceAssertion('task-55', {
    navigationSurfaces: ['entities->graph_failure', 'relationships->graph_failure'],
    fieldAssertions: {
      graph_entities_status: 500,
      graph_relationships_status: 500,
      entities_error_detail: 'QA forced failure for graph entities',
      relationships_error_detail: 'QA forced failure for graph relationships',
    },
    pathAssertions: {
      'graph_entities.status_code': 500,
      'graph_entities.detail': 'QA forced failure for graph entities',
      'graph_relationships.status_code': 500,
      'graph_relationships.detail': 'QA forced failure for graph relationships',
    },
  }),
})

export const DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS = Object.freeze(
  getFocusedRealSmokeTaskGroupTaskIds('dashboard-adjacent')
)

export function assertDashboardAdjacentEvidenceSample(taskId, normalized) {
  assertFocusedRealSmokeEvidenceSampleCase(
    taskId,
    normalized,
    DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    'dashboard-adjacent evidence sample assertion'
  )
}
