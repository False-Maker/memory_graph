import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDashboardCommunitiesStatsEvidenceAssertion,
  buildDashboardGraphStatsEvidenceAssertion,
  buildDashboardMemoriesStatsEvidenceAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

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
