import test from 'node:test'
import assert from 'node:assert/strict'

import {
  assertEvidenceFields,
  assertEvidencePathValues,
  buildDashboardCommunitiesStatsEvidenceAssertion,
  buildDashboardGraphStatsEvidenceAssertion,
  buildDashboardMemoriesStatsEvidenceAssertion,
  buildDeletedMemoryFailureAssertion,
  buildFocusedRealSmokeEvidenceAssertion,
  buildHighSignalCommunityDetailNavigationEvidenceAssertion,
  buildMissingMemoryIdCommunityFallbackAssertion,
  buildNormalizedCommunityDetailNavigationAssertion,
  buildNormalizedCommunityMissingDetailAssertion,
  buildNormalizedCommunitySummaryRefreshAssertion,
  buildNormalizedCommunityEvidenceAssertion,
  buildSuccessfulMemoryWriteLifecycleAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

test('assertEvidenceFields matches scalar, array, and object fields', () => {
  const normalized = {
    status: 'passed',
    counts: [1, 2, 3],
    meta: { kind: 'dashboard' },
  }

  assert.doesNotThrow(() => {
    assertEvidenceFields(normalized, {
      status: 'passed',
      counts: [1, 2, 3],
      meta: { kind: 'dashboard' },
    }, 'sample normalized')
  })
})

test('assertEvidenceFields throws with the mismatched field label', () => {
  assert.throws(
    () => {
      assertEvidenceFields({ status: 'failed' }, { status: 'passed' }, 'sample normalized')
    },
    /sample normalized\.status mismatch/
  )
})

test('assertEvidencePathValues resolves nested object, array index, and property paths', () => {
  const normalized = {
    detail_after_delete: { status_code: 404 },
    query_modes: {
      global: {
        sources: [{ memory_id: 'mem-123' }],
      },
    },
    recent_titles: ['a', 'b', 'c'],
  }

  assert.doesNotThrow(() => {
    assertEvidencePathValues(normalized, {
      'detail_after_delete.status_code': 404,
      'query_modes.global.sources.0.memory_id': 'mem-123',
      'recent_titles.length': 3,
    }, 'sample normalized')
  })
})

test('assertEvidencePathValues throws with the mismatched path label', () => {
  assert.throws(
    () => {
      assertEvidencePathValues({ nested: { count: 1 } }, { 'nested.count': 2 }, 'sample normalized')
    },
    /sample normalized\.nested\.count mismatch/
  )
})

test('buildFocusedRealSmokeEvidenceAssertion combines fields, paths, and custom assertions', () => {
  const assertion = buildFocusedRealSmokeEvidenceAssertion('task-demo', {
    label: 'task-demo normalized',
    fields: {
      status: 'passed',
      route: '/dashboard',
    },
    paths: {
      'detail.status_code': 404,
      'items.length': 2,
    },
    customAssert: (normalized) => {
      assert.equal(normalized.extra, true)
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      status: 'passed',
      route: '/dashboard',
      detail: { status_code: 404 },
      items: ['x', 'y'],
      extra: true,
    })
  })
})


test('buildSuccessfulMemoryWriteLifecycleAssertion applies lifecycle defaults and status paths', () => {
  const assertion = buildSuccessfulMemoryWriteLifecycleAssertion('task-write', {
    finalRoute: '/dashboard',
    contextStatusAfterDelete: 404,
    includeArchiveOutcomeFields: true,
    fieldAssertions: {
      active_before: 1,
      archived_before: 0,
      active_after_archive: 0,
      archived_after_archive: 1,
      active_after_unarchive: 1,
      archived_after_unarchive: 0,
      active_after_delete: 0,
      archived_after_delete: 0,
      total_after_delete: 0,
      navigation_surface: 'dashboard_recent_item',
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      active_before: 1,
      archived_before: 0,
      active_after_archive: 0,
      archived_after_archive: 1,
      active_after_unarchive: 1,
      archived_after_unarchive: 0,
      active_after_delete: 0,
      archived_after_delete: 0,
      total_after_delete: 0,
      navigation_surface: 'dashboard_recent_item',
      archive_success: true,
      unarchive_success: true,
      delete_success: true,
      delete_message: 'Memory deleted',
      detail_status_after_delete: 404,
      context_status_after_delete: 404,
      final_route: '/dashboard',
      detail_after_delete: { status_code: 404 },
      context_after_delete: { status_code: 404 },
    })
  })
})

test('buildNormalizedCommunityEvidenceAssertion applies community defaults and custom paths', () => {
  const assertion = buildNormalizedCommunityEvidenceAssertion('task-community', {
    communityId: 'comm-release-readiness',
    communityTitle: 'Release Readiness',
    fieldAssertions: {
      entities_status: 500,
      relationships_status: 500,
    },
    pathAssertions: {
      'entities.detail': 'forced entities failure',
      'relationships.detail': 'forced relationships failure',
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      target_community_id: 'comm-release-readiness',
      community_title: 'Release Readiness',
      final_route: '/communities#comm-release-readiness',
      entities_status: 500,
      relationships_status: 500,
      entities: { detail: 'forced entities failure' },
      relationships: { detail: 'forced relationships failure' },
    })
  })
})

test('buildHighSignalCommunityDetailNavigationEvidenceAssertion applies memory-to-community detail defaults', () => {
  const assertion = buildHighSignalCommunityDetailNavigationEvidenceAssertion('task-community-detail', {
    fieldAssertions: {
      community_relationship_type: 'owns',
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        memory_id: 'mem-launch',
        community_id: 'comm-launch-owners',
        memory_context_entities: 2,
        memory_context_communities: 1,
        community_entities_total: 2,
        community_relationships_total: 1,
        community_relationship_type: 'owns',
        ancestors_total: 0,
        descendants_total: 0,
        final_url: '/communities#comm-launch-owners',
      },
      http: {
        memory_detail: { id: 'mem-launch' },
        memory_context: { total_entities: 2, total_communities: 1 },
        community_detail: { id: 'comm-launch-owners' },
        community_entities: { total: 2 },
        community_relationships: { total: 1, relationships: [{ type: 'owns' }] },
        community_ancestors: { total: 0 },
        community_descendants: { total: 0 },
      },
    })
  })
})


test('buildNormalizedCommunityDetailNavigationAssertion applies normalized community-detail defaults', () => {
  const assertion = buildNormalizedCommunityDetailNavigationAssertion('task-community-detail-normalized', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      community_id: 'comm-launch-owners',
      memory_context_communities: 1,
      community_entities_total: 2,
      community_relationships_total: 1,
      ancestors_total: 0,
      descendants_total: 0,
      community_id_matches_detail: true,
      community_title: 'Launch Owners',
      community_summary: 'Alice owns the launch checklist and release coordination.',
      memory_context_entity_names: ['Alice', 'Launch Checklist'],
      community_entity_names: ['Alice', 'Launch Checklist'],
      community_relationships: [{ source: 'Alice', target: 'Launch Checklist', type: 'owns' }],
      ancestor_titles: [],
      descendant_titles: [],
      navigation_path: 'dashboard_recent_item,memory_detail,community_detail',
      recent_memory_matches_detail: true,
      memory_detail_title: 'Launch ownership note',
      final_route: '/communities#comm-launch-owners',
    })
  })
})

test('buildNormalizedCommunityMissingDetailAssertion applies missing detail defaults and route', () => {
  const assertion = buildNormalizedCommunityMissingDetailAssertion('task-community-missing', {
    missingCommunityId: 'comm-missing-detail-real-smoke',
    fieldAssertions: {
      existing_community_id: 'comm-release-readiness',
      total_communities: 3,
    },
    pathAssertions: {
      'missing_detail.detail': 'Community comm-missing-detail-real-smoke not found',
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      existing_community_id: 'comm-release-readiness',
      missing_community_id: 'comm-missing-detail-real-smoke',
      missing_detail_status: 404,
      total_communities: 3,
      final_route: '/communities#comm-missing-detail-real-smoke',
      missing_detail: {
        status_code: 404,
        detail: 'Community comm-missing-detail-real-smoke not found',
      },
    })
  })
})

test('buildDeletedMemoryFailureAssertion applies delete outcome defaults and configurable status fields', () => {
  const assertion = buildDeletedMemoryFailureAssertion('task-delete', {
    finalRoute: '/dashboard',
    deleteStatusField: 'delete_status',
    detailStatusField: 'deleted_detail_status',
    detailStatusPath: 'deleted_detail.status_code',
    contextStatusField: 'deleted_context_status',
    contextStatus: 404,
    contextStatusPath: 'deleted_context.status_code',
    fieldAssertions: {
      stale_memory_matches_delete: true,
      recent_total_after_delete: 0,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      delete_success: true,
      delete_message: 'Memory deleted',
      delete_status: 200,
      deleted_detail_status: 404,
      deleted_context_status: 404,
      stale_memory_matches_delete: true,
      recent_total_after_delete: 0,
      final_route: '/dashboard',
      deleted_detail: { status_code: 404 },
      deleted_context: { status_code: 404 },
    })
  })
})

test('buildDeletedMemoryFailureAssertion supports delete-only status variants without outcome fields or nested paths', () => {
  const assertion = buildDeletedMemoryFailureAssertion('task-delete-lite', {
    finalRoute: '/search',
    includeDeleteOutcomeFields: false,
    deleteStatusField: 'delete_status',
    detailStatusField: 'detail_status_after_delete',
    fieldAssertions: {
      query_answer: 'Alice owns the launch checklist and coordinates the release.',
      query_source_titles: ['Launch ownership note'],
      query_source_community_ids: ['comm-launch-owners'],
      delete_status_http: 200,
      detail_after_delete_status_http: 404,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      delete_status: 200,
      detail_status_after_delete: 404,
      query_answer: 'Alice owns the launch checklist and coordinates the release.',
      query_source_titles: ['Launch ownership note'],
      query_source_community_ids: ['comm-launch-owners'],
      delete_status_http: 200,
      detail_after_delete_status_http: 404,
      final_route: '/search',
    })
  })
})

test('buildDashboardGraphStatsEvidenceAssertion supports empty dashboard graph stats variants', () => {
  const assertion = buildDashboardGraphStatsEvidenceAssertion('task-dashboard-graph-empty', {
    navigationSurfaces: ['entities->graph_empty', 'relationships->graph_empty'],
    includeTotalCommunities: true,
    fieldAssertions: {
      graph_entity_count: 0,
      graph_relationship_count: 0,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surfaces: ['entities->graph_empty', 'relationships->graph_empty'],
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      total_communities: 0,
      graph_entity_count: 0,
      graph_relationship_count: 0,
      entity_types: {},
      recent_memories_total: 0,
      communities_total: 0,
      final_route: '/graph',
    })
  })
})

test('buildDashboardGraphStatsEvidenceAssertion supports failure dashboard graph stats variants', () => {
  const assertion = buildDashboardGraphStatsEvidenceAssertion('task-dashboard-graph-failure', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surfaces: ['entities->graph_failure', 'relationships->graph_failure'],
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      graph_entities_status: 500,
      graph_relationships_status: 500,
      entities_error_detail: 'QA forced failure for graph entities',
      relationships_error_detail: 'QA forced failure for graph relationships',
      entity_types: {},
      recent_memories_total: 0,
      communities_total: 0,
      final_route: '/graph',
      graph_entities: {
        status_code: 500,
        detail: 'QA forced failure for graph entities',
      },
      graph_relationships: {
        status_code: 500,
        detail: 'QA forced failure for graph relationships',
      },
    })
  })
})

test('buildDashboardGraphStatsEvidenceAssertion supports stats-navigation variants without aggregate totals from sibling cards', () => {
  const assertion = buildDashboardGraphStatsEvidenceAssertion('task-dashboard-stats-navigation', {
    navigationSurfaces: ['entities->graph', 'relationships->graph', 'memories->memories', 'communities->communities'],
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
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surfaces: ['entities->graph', 'relationships->graph', 'memories->memories', 'communities->communities'],
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
      final_route: '/communities',
    })
  })
})

test('buildDashboardCommunitiesStatsEvidenceAssertion supports empty dashboard communities variants', () => {
  const assertion = buildDashboardCommunitiesStatsEvidenceAssertion('task-dashboard-communities-empty', {
    navigationSurface: 'communities->communities_empty',
    includeTotalCommunities: true,
    fieldAssertions: {
      hierarchy_total: 0,
      communities_titles: [],
      hierarchy_roots: [],
      hierarchy_levels: 0,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surface: 'communities->communities_empty',
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      total_communities: 0,
      hierarchy_total: 0,
      entity_types: {},
      communities_titles: [],
      hierarchy_roots: [],
      hierarchy_levels: 0,
      recent_memories_total: 0,
      final_route: '/communities',
    })
  })
})

test('buildDashboardCommunitiesStatsEvidenceAssertion supports failure dashboard communities variants', () => {
  const assertion = buildDashboardCommunitiesStatsEvidenceAssertion('task-dashboard-communities-failure', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surface: 'communities->communities_failure',
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      communities_list_status: 500,
      hierarchy_status: 500,
      list_error_detail: 'Failed to list communities: QA forced failure for communities list',
      hierarchy_error_detail: 'Failed to get hierarchy: QA forced failure for communities hierarchy',
      entity_types: {},
      recent_memories_total: 0,
      final_route: '/communities',
      communities: {
        status_code: 500,
        detail: 'Failed to list communities: QA forced failure for communities list',
      },
      hierarchy: {
        status_code: 500,
        detail: 'Failed to get hierarchy: QA forced failure for communities hierarchy',
      },
    })
  })
})

test('buildDashboardMemoriesStatsEvidenceAssertion supports empty dashboard memories variants', () => {
  const assertion = buildDashboardMemoriesStatsEvidenceAssertion('task-dashboard-memories-empty', {
    navigationSurface: 'memories->memories_empty',
    includeEntityRelationshipTotals: true,
    includeTotalCommunities: true,
    fieldAssertions: {
      recent_memories_total: 0,
      active_list_total: 0,
      recent_titles: [],
      active_titles: [],
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surface: 'memories->memories_empty',
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      total_communities: 0,
      recent_memories_total: 0,
      active_list_total: 0,
      entity_types: {},
      recent_titles: [],
      active_titles: [],
      communities_total: 0,
      final_route: '/memories',
    })
  })
})

test('buildDashboardMemoriesStatsEvidenceAssertion supports failure dashboard memories variants', () => {
  const assertion = buildDashboardMemoriesStatsEvidenceAssertion('task-dashboard-memories-failure', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surface: 'memories->memories_failure',
      total_memories: 0,
      recent_memories_status: 500,
      active_list_status: 500,
      error_detail: 'QA forced failure for memories list',
      entity_types: {},
      communities_total: 0,
      final_route: '/memories',
      recent_memories: {
        status_code: 500,
        detail: 'QA forced failure for memories list',
      },
      memories_list: {
        status_code: 500,
        detail: 'QA forced failure for memories list',
      },
    })
  })
})

test('buildDashboardMemoriesStatsEvidenceAssertion supports dashboard view-all variants without stats-only defaults', () => {
  const assertion = buildDashboardMemoriesStatsEvidenceAssertion('task-dashboard-view-all', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      navigation_surface: 'dashboard_view_all',
      profile: 'memories_list',
      recent_memories_total: 19,
      recent_memories_visible: 10,
      active_list_total: 19,
      active_list_visible: 19,
      recent_titles_visible: Array.from({ length: 10 }, (_, index) => `List memory ${index + 1}`),
      active_titles_visible: Array.from({ length: 19 }, (_, index) => `List memory ${index + 1}`),
      first_recent_memory_title: 'List memory 21',
      first_active_memory_title: 'List memory 21',
      final_route: '/memories',
    })
  })
})

test('buildMissingMemoryIdCommunityFallbackAssertion applies query-mode fallback defaults', () => {
  const assertion = buildMissingMemoryIdCommunityFallbackAssertion('task-missing-memory-id', {
    communityId: 'comm-missing-memory-id',
    communityTitle: 'Launch Owners Without Memory',
    queryAnswer: 'Alice owns the launch checklist and coordinates the release.',
    fakeOllamaCounts: {
      tagRequests: 0,
      embeddingRequests: 16,
      generateRequests: 5,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      community_id: 'comm-missing-memory-id',
      query_modes_tested: ['global', 'local', 'hybrid'],
      global_query_source_memory_id: null,
      local_query_source_memory_id: null,
      hybrid_query_source_memory_id: null,
      link_surface: 'source',
      memory_detail_requests: 0,
      memory_link_count: 0,
      memories_total: 0,
      communities_total: 1,
      community_title: 'Launch Owners Without Memory',
      query_answers: {
        global: 'Alice owns the launch checklist and coordinates the release.',
        local: 'Alice owns the launch checklist and coordinates the release.',
        hybrid: 'Alice owns the launch checklist and coordinates the release.',
      },
      query_community_ids: {
        global: ['comm-missing-memory-id'],
        local: ['comm-missing-memory-id'],
        hybrid: ['comm-missing-memory-id'],
      },
      fake_ollama_counts: {
        tagRequests: 0,
        embeddingRequests: 16,
        generateRequests: 5,
      },
      final_route: '/communities#comm-missing-memory-id',
    })
  })
})


test('buildNormalizedCommunitySummaryRefreshAssertion applies summary refresh defaults and field mirroring', () => {
  const assertion = buildNormalizedCommunitySummaryRefreshAssertion('task-community-refresh-normalized', {
    communityId: 'comm-launch-owners',
    initialSummaryField: 'initial_summary',
    initialSummaryValue: 'stale summary',
    refreshedSummaryValue: 'fresh summary',
    matchRefreshedFields: ['regenerate_summary', 'after_summary'],
    fieldAssertions: {
      before_title: 'Launch Owners',
      fake_ollama_generate_requests: 1,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      community_id: 'comm-launch-owners',
      initial_summary: 'stale summary',
      refreshed_summary: 'fresh summary',
      regenerate_summary: 'fresh summary',
      after_summary: 'fresh summary',
      summary_changed: true,
      before_title: 'Launch Owners',
      fake_ollama_generate_requests: 1,
      final_route: '/communities#comm-launch-owners',
    })
  })
})
