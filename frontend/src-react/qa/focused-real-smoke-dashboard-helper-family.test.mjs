import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDashboardCommunitiesStatsNormalizer,
  buildDashboardGraphStatsNormalizer,
  buildDashboardMemoriesStatsNormalizer,
  buildDashboardRecentMemoryDeleteFailureNormalizer,
  buildDashboardRecentMemoryWriteNormalizer,
} from './focused-real-smoke-compare-cases/helpers.mjs'

test('buildDashboardGraphStatsNormalizer supports graph empty variants with shared dashboard stats fields', () => {
  const normalize = buildDashboardGraphStatsNormalizer({
    includeTotalCommunities: true,
    customNormalize: ({ summary }) => ({
      graph_entity_count: summary.graph_entity_count ?? null,
      graph_relationship_count: summary.graph_relationship_count ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-50',
      status: 'passed',
      navigation_surfaces: ['entities->graph_empty', 'relationships->graph_empty'],
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      total_communities: 0,
      graph_entity_count: 0,
      graph_relationship_count: 0,
      final_url: '/graph',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: {} },
      recent_memories: { total: 0 },
      communities: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-50',
    status: 'passed',
    navigation_surfaces: ['entities->graph_empty', 'relationships->graph_empty'],
    total_entities: 0,
    total_relationships: 0,
    total_memories: 0,
    total_communities: 0,
    final_route: '/graph',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: {},
    recent_memories_total: 0,
    communities_total: 0,
    graph_entity_count: 0,
    graph_relationship_count: 0,
  })
})

test('buildDashboardGraphStatsNormalizer supports graph failure variants', () => {
  const normalize = buildDashboardGraphStatsNormalizer({
    customNormalize: ({ summary, http }) => ({
      graph_entities_status: summary.graph_entities_status ?? null,
      graph_relationships_status: summary.graph_relationships_status ?? null,
      entities_error_detail: summary.entities_error_detail ?? null,
      relationships_error_detail: summary.relationships_error_detail ?? null,
      graph_entities: {
        status_code: http.graph_entities?.status_code ?? null,
        detail: http.graph_entities?.body?.detail ?? null,
      },
      graph_relationships: {
        status_code: http.graph_relationships?.status_code ?? null,
        detail: http.graph_relationships?.body?.detail ?? null,
      },
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-55',
      status: 'passed',
      navigation_surfaces: ['entities->graph_failure', 'relationships->graph_failure'],
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      graph_entities_status: 500,
      graph_relationships_status: 500,
      entities_error_detail: 'graph entities failed',
      relationships_error_detail: 'graph relationships failed',
      final_url: '/graph',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: {} },
      graph_entities: { status_code: 500, body: { detail: 'graph entities failed' } },
      graph_relationships: { status_code: 500, body: { detail: 'graph relationships failed' } },
      recent_memories: { total: 0 },
      communities: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-55',
    status: 'passed',
    navigation_surfaces: ['entities->graph_failure', 'relationships->graph_failure'],
    total_entities: 0,
    total_relationships: 0,
    total_memories: 0,
    final_route: '/graph',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: {},
    recent_memories_total: 0,
    communities_total: 0,
    graph_entities_status: 500,
    graph_relationships_status: 500,
    entities_error_detail: 'graph entities failed',
    relationships_error_detail: 'graph relationships failed',
    graph_entities: {
      status_code: 500,
      detail: 'graph entities failed',
    },
    graph_relationships: {
      status_code: 500,
      detail: 'graph relationships failed',
    },
  })
})

test('buildDashboardGraphStatsNormalizer supports dashboard stats navigation variants without recent-memory totals', () => {
  const normalize = buildDashboardGraphStatsNormalizer({
    includeTotalCommunities: true,
    includeRecentMemoriesTotal: false,
    includeCommunitiesTotal: false,
    customNormalize: ({ summary, http }) => ({
      graph_entity_count: summary.graph_entity_count ?? null,
      graph_relationship_count: summary.graph_relationship_count ?? null,
      memories_list_total: summary.memories_list_total ?? null,
      graph_entity_names: (http.graph_entities?.entities ?? []).map((entity) => entity?.name).filter(Boolean),
      graph_relationship_types: (http.graph_relationships?.relationships ?? []).map((relationship) => relationship?.type).filter(Boolean),
      graph_relationship_total: http.graph_relationships?.total ?? null,
      memories_titles: (http.memories?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
      communities_titles: (http.communities?.communities ?? []).map((community) => community?.title).filter(Boolean),
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-49',
      status: 'passed',
      navigation_surfaces: ['entities->graph', 'relationships->graph', 'memories->memories', 'communities->communities'],
      total_entities: 2,
      total_relationships: 1,
      total_memories: 1,
      total_communities: 1,
      graph_entity_count: 2,
      graph_relationship_count: 1,
      memories_list_total: 1,
      final_url: '/communities',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: { document: 1, person: 1 } },
      graph_entities: { entities: [{ name: 'Launch Checklist' }, { name: 'Alice' }] },
      graph_relationships: { relationships: [{ type: 'owns' }], total: 1 },
      memories: { memories: [{ metadata: { title: 'Launch ownership note' } }] },
      communities: { communities: [{ title: 'Launch Owners' }] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-49',
    status: 'passed',
    navigation_surfaces: ['entities->graph', 'relationships->graph', 'memories->memories', 'communities->communities'],
    total_entities: 2,
    total_relationships: 1,
    total_memories: 1,
    total_communities: 1,
    final_route: '/communities',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: { document: 1, person: 1 },
    graph_entity_count: 2,
    graph_relationship_count: 1,
    memories_list_total: 1,
    graph_entity_names: ['Launch Checklist', 'Alice'],
    graph_relationship_types: ['owns'],
    graph_relationship_total: 1,
    memories_titles: ['Launch ownership note'],
    communities_titles: ['Launch Owners'],
  })
})

test('buildDashboardCommunitiesStatsNormalizer supports communities empty variants', () => {
  const normalize = buildDashboardCommunitiesStatsNormalizer({
    includeTotalCommunities: true,
    customNormalize: ({ summary, http }) => ({
      hierarchy_total: summary.hierarchy_total ?? null,
      communities_titles: (http.communities?.communities ?? []).map((community) => community?.title).filter(Boolean),
      hierarchy_roots: (http.hierarchy?.roots ?? []).map((root) => root?.title).filter(Boolean),
      hierarchy_levels: http.hierarchy?.levels ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-51',
      status: 'passed',
      navigation_surface: 'communities->communities_empty',
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      total_communities: 0,
      hierarchy_total: 0,
      final_url: '/communities',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: {} },
      communities: { communities: [] },
      hierarchy: { roots: [], levels: 0 },
      recent_memories: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-51',
    status: 'passed',
    navigation_surface: 'communities->communities_empty',
    total_entities: 0,
    total_relationships: 0,
    total_memories: 0,
    total_communities: 0,
    final_route: '/communities',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: {},
    recent_memories_total: 0,
    hierarchy_total: 0,
    communities_titles: [],
    hierarchy_roots: [],
    hierarchy_levels: 0,
  })
})

test('buildDashboardCommunitiesStatsNormalizer supports communities failure variants', () => {
  const normalize = buildDashboardCommunitiesStatsNormalizer({
    customNormalize: ({ summary, http }) => ({
      communities_list_status: summary.communities_list_status ?? null,
      hierarchy_status: summary.hierarchy_status ?? null,
      list_error_detail: summary.list_error_detail ?? null,
      hierarchy_error_detail: summary.hierarchy_error_detail ?? null,
      communities: {
        status_code: http.communities?.status_code ?? null,
        detail: http.communities?.body?.detail ?? null,
      },
      hierarchy: {
        status_code: http.hierarchy?.status_code ?? null,
        detail: http.hierarchy?.body?.detail ?? null,
      },
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-54',
      status: 'passed',
      navigation_surface: 'communities->communities_failure',
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      communities_list_status: 500,
      hierarchy_status: 500,
      list_error_detail: 'communities failed',
      hierarchy_error_detail: 'hierarchy failed',
      final_url: '/communities',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: {} },
      communities: { status_code: 500, body: { detail: 'communities failed' } },
      hierarchy: { status_code: 500, body: { detail: 'hierarchy failed' } },
      recent_memories: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-54',
    status: 'passed',
    navigation_surface: 'communities->communities_failure',
    total_entities: 0,
    total_relationships: 0,
    total_memories: 0,
    final_route: '/communities',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: {},
    recent_memories_total: 0,
    communities_list_status: 500,
    hierarchy_status: 500,
    list_error_detail: 'communities failed',
    hierarchy_error_detail: 'hierarchy failed',
    communities: {
      status_code: 500,
      detail: 'communities failed',
    },
    hierarchy: {
      status_code: 500,
      detail: 'hierarchy failed',
    },
  })
})

test('buildDashboardMemoriesStatsNormalizer supports memories empty variants', () => {
  const normalize = buildDashboardMemoriesStatsNormalizer({
    includeEntityRelationshipTotals: true,
    includeTotalCommunities: true,
    customNormalize: ({ summary, http }) => ({
      recent_memories_total: summary.recent_memories_total ?? null,
      active_list_total: summary.active_list_total ?? null,
      recent_titles: (http.recent_memories?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
      active_titles: (http.memories_list?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-52',
      status: 'passed',
      navigation_surface: 'memories->memories_empty',
      total_entities: 0,
      total_relationships: 0,
      total_memories: 0,
      recent_memories_total: 0,
      active_list_total: 0,
      total_communities: 0,
      final_url: '/memories',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: {} },
      recent_memories: { memories: [] },
      memories_list: { memories: [] },
      communities: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-52',
    status: 'passed',
    navigation_surface: 'memories->memories_empty',
    total_entities: 0,
    total_relationships: 0,
    total_memories: 0,
    total_communities: 0,
    final_route: '/memories',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: {},
    communities_total: 0,
    recent_memories_total: 0,
    active_list_total: 0,
    recent_titles: [],
    active_titles: [],
  })
})

test('buildDashboardMemoriesStatsNormalizer supports memories failure variants', () => {
  const normalize = buildDashboardMemoriesStatsNormalizer({
    customNormalize: ({ summary, http }) => ({
      recent_memories_status: summary.recent_memories_status ?? null,
      active_list_status: summary.active_list_status ?? null,
      error_detail: summary.error_detail ?? null,
      recent_memories: {
        status_code: http.recent_memories?.status_code ?? null,
        detail: http.recent_memories?.body?.detail ?? null,
      },
      memories_list: {
        status_code: http.memories_list?.status_code ?? null,
        detail: http.memories_list?.body?.detail ?? null,
      },
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-53',
      status: 'passed',
      navigation_surface: 'memories->memories_failure',
      total_memories: 0,
      recent_memories_status: 500,
      active_list_status: 500,
      error_detail: 'memories failed',
      final_url: '/memories',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: {} },
      recent_memories: { status_code: 500, body: { detail: 'memories failed' } },
      memories_list: { status_code: 500, body: { detail: 'memories failed' } },
      communities: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-53',
    status: 'passed',
    navigation_surface: 'memories->memories_failure',
    total_memories: 0,
    final_route: '/memories',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    entity_types: {},
    communities_total: 0,
    recent_memories_status: 500,
    active_list_status: 500,
    error_detail: 'memories failed',
    recent_memories: {
      status_code: 500,
      detail: 'memories failed',
    },
    memories_list: {
      status_code: 500,
      detail: 'memories failed',
    },
  })
})

test('buildDashboardMemoriesStatsNormalizer supports dashboard view-all navigation variants without stats-only fields', () => {
  const normalize = buildDashboardMemoriesStatsNormalizer({
    includeTotalMemories: false,
    includeEntityTypes: false,
    includeCommunitiesTotal: false,
    customNormalize: ({ summary, http }) => ({
      profile: summary.profile ?? null,
      recent_memories_total: summary.recent_memories_total ?? null,
      recent_memories_visible: summary.recent_memories_visible ?? null,
      active_list_total: summary.active_list_total ?? null,
      active_list_visible: summary.active_list_visible ?? null,
      recent_titles_visible: (http.recent_memories?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
      active_titles_visible: (http.memories_list?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
      first_recent_memory_title: http.recent_memories?.memories?.[0]?.metadata?.title ?? null,
      first_active_memory_title: http.memories_list?.memories?.[0]?.metadata?.title ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-48',
      status: 'passed',
      profile: 'memories_list',
      navigation_surface: 'dashboard_view_all',
      recent_memories_total: 19,
      recent_memories_visible: 10,
      active_list_total: 19,
      active_list_visible: 19,
      final_url: '/memories',
    },
    http: {
      health: { status: 'healthy' },
      recent_memories: { memories: [{ metadata: { title: 'List memory 21' } }, { metadata: { title: 'List memory 20' } }] },
      memories_list: { memories: [{ metadata: { title: 'List memory 21' } }, { metadata: { title: 'List memory 20' } }] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-48',
    status: 'passed',
    navigation_surface: 'dashboard_view_all',
    final_route: '/memories',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    profile: 'memories_list',
    recent_memories_total: 19,
    recent_memories_visible: 10,
    active_list_total: 19,
    active_list_visible: 19,
    recent_titles_visible: ['List memory 21', 'List memory 20'],
    active_titles_visible: ['List memory 21', 'List memory 20'],
    first_recent_memory_title: 'List memory 21',
    first_active_memory_title: 'List memory 21',
  })
})

test('buildDashboardRecentMemoryDeleteFailureNormalizer supports dashboard stale recent-memory failure variants', () => {
  const normalize = buildDashboardRecentMemoryDeleteFailureNormalizer()

  const result = normalize({
    summary: {
      command: 'node task-45',
      status: 'passed',
      navigation_surface: 'dashboard_recent_item',
      stale_recent_memory_id: 'mem-launch',
      delete_status: 200,
      deleted_detail_status: 404,
      deleted_context_status: 404,
      recent_total_before_delete: 1,
      recent_total_after_delete: 0,
      refreshed_dashboard_empty: true,
      final_url: '/dashboard',
    },
    http: {
      health: { status: 'healthy' },
      recent_before_delete: { memories: [{ metadata: { title: 'Launch ownership note' } }] },
      seeded_detail: { metadata: { title: 'Launch ownership note' } },
      delete: { body: { memory_id: 'mem-launch', success: true, message: 'Memory deleted' } },
      deleted_detail: { status_code: 404, body: { detail: 'missing' } },
      deleted_context: { status_code: 404, body: { detail: 'missing' } },
      recent_after_delete: { memories: [] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-45',
    status: 'passed',
    navigation_surface: 'dashboard_recent_item',
    delete_status: 200,
    deleted_detail_status: 404,
    deleted_context_status: 404,
    recent_total_before_delete: 1,
    recent_total_after_delete: 0,
    refreshed_dashboard_empty: true,
    final_route: '/dashboard',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    stale_memory_matches_delete: true,
    recent_memory_titles_before_delete: ['Launch ownership note'],
    seeded_detail_title: 'Launch ownership note',
    delete_success: true,
    delete_message: 'Memory deleted',
    deleted_detail: {
      status_code: 404,
      detail: 'missing',
    },
    deleted_context: {
      status_code: 404,
      detail: 'missing',
    },
    recent_memory_ids_after_delete: [],
  })
})

test('buildDashboardRecentMemoryWriteNormalizer supports dashboard recent-memory write-path variants', () => {
  const normalize = buildDashboardRecentMemoryWriteNormalizer()

  const result = normalize({
    summary: {
      command: 'node task-46',
      status: 'passed',
      navigation_surface: 'dashboard_recent_item',
      recent_memory_id: 'mem-launch',
      active_before: 1,
      archived_before: 0,
      active_after_archive: 0,
      archived_after_archive: 1,
      active_after_unarchive: 1,
      archived_after_unarchive: 0,
      active_after_delete: 0,
      archived_after_delete: 0,
      total_after_delete: 0,
      detail_status_after_delete: 404,
      context_status_after_delete: 404,
      refreshed_dashboard_empty: true,
      final_url: '/dashboard',
    },
    http: {
      health: { status: 'healthy' },
      recent_memories: { memories: [{ id: 'mem-launch', metadata: { title: 'Launch ownership note' } }] },
      detail_before: { id: 'mem-launch', metadata: { title: 'Launch ownership note' } },
      active_before: { memories: [{ metadata: { title: 'Launch ownership note' } }] },
      archived_before: { memories: [] },
      detail_after_archive: { metadata: { archived: true } },
      detail_after_unarchive: { metadata: { archived: false } },
      delete: { memory_id: 'mem-launch', success: true, message: 'Memory deleted' },
      detail_after_delete: { status_code: 404, body: { detail: 'missing' } },
      context_after_delete: { status_code: 404, body: { detail: 'missing' } },
      active_after_delete: { memories: [] },
      archived_after_delete: { memories: [] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-46',
    status: 'passed',
    navigation_surface: 'dashboard_recent_item',
    active_before: 1,
    archived_before: 0,
    active_after_archive: 0,
    archived_after_archive: 1,
    active_after_unarchive: 1,
    archived_after_unarchive: 0,
    active_after_delete: 0,
    archived_after_delete: 0,
    total_after_delete: 0,
    detail_status_after_delete: 404,
    context_status_after_delete: 404,
    refreshed_dashboard_empty: true,
    final_route: '/dashboard',
    health: {
      status: 'healthy',
      service: null,
      version: null,
      config_ok: null,
      provider: null,
      sqlite_ok: null,
      vector_store_ok: null,
      vector_dimension_mismatch: null,
      vector_stored_documents: null,
    },
    recent_memory_matches_detail: true,
    recent_titles: ['Launch ownership note'],
    active_titles_before: ['Launch ownership note'],
    archived_titles_before: [],
    detail_before_title: 'Launch ownership note',
    detail_archived_after_archive: true,
    detail_archived_after_unarchive: false,
    delete_success: true,
    delete_message: 'Memory deleted',
    delete_memory_id_matches_summary: true,
    detail_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
    context_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
    active_titles_after_delete: [],
    archived_titles_after_delete: [],
  })
})
