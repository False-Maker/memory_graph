import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCommunityDetailNavigationNormalizer,
  buildDashboardCommunitiesStatsNormalizer,
  buildDashboardGraphStatsNormalizer,
  buildDashboardMemoriesStatsNormalizer,
  buildDashboardRecentMemoryDeleteFailureNormalizer,
  buildDashboardRecentMemoryWriteNormalizer,
  buildRemainingWebCommunityFailureNormalizer,
  buildRemainingWebCommunitySummaryRefreshNormalizer,
  buildRemainingWebMemoryDeleteFailureNormalizer,
  buildRemainingWebMemoryWriteNormalizer,
  buildSuccessfulCommunitySummaryRefreshNormalizer,
  normalizeQueryModeMap,
  queryCommunityIds,
} from './focused-real-smoke-compare-cases/helpers.mjs'

test('normalizeQueryModeMap preserves global-local-hybrid order and exposes mode ids to the mapper', () => {
  const result = normalizeQueryModeMap({
    global: { answer: 'global answer' },
    hybrid: { answer: 'hybrid answer' },
  }, (query, modeId) => `${modeId}:${query?.answer ?? 'missing'}`)

  assert.deepEqual(result, {
    global: 'global:global answer',
    local: 'local:missing',
    hybrid: 'hybrid:hybrid answer',
  })
})

test('normalizeQueryModeMap supports ad hoc query-mode records used by remaining-web task cases', () => {
  const result = normalizeQueryModeMap({
    global: { communities: [{ community_id: 'comm-launch-owners' }] },
    local: { communities: [{ community_id: 'comm-release-readiness' }] },
    hybrid: {},
  }, (query) => queryCommunityIds(query))

  assert.deepEqual(result, {
    global: ['comm-launch-owners'],
    local: ['comm-release-readiness'],
    hybrid: [],
  })
})


test('buildSuccessfulCommunitySummaryRefreshNormalizer supports small community refresh variants', () => {
  const normalize = buildSuccessfulCommunitySummaryRefreshNormalizer({
    customNormalize: ({ summary }) => ({
      fake_ollama_generate_requests_zero: Number(summary.fake_ollama_generate_requests) === 0,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-27',
      status: 'passed',
      community_id: 'comm-launch-owners',
      initial_summary: 'stale summary',
      refreshed_summary: 'fresh summary',
      fake_ollama_generate_requests: 0,
      final_url: '/communities#comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      before_summary: { id: 'comm-launch-owners', title: 'Launch Owners' },
      regenerate: { community_id: 'comm-launch-owners', summary: 'fresh summary', token_count: 16 },
      after_summary: { id: 'comm-launch-owners', summary: 'fresh summary' },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-27',
    status: 'passed',
    community_id: 'comm-launch-owners',
    initial_summary: 'stale summary',
    refreshed_summary: 'fresh summary',
    summary_changed: true,
    final_route: '/communities#comm-launch-owners',
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
    before_title: 'Launch Owners',
    regenerate_summary: 'fresh summary',
    regenerate_token_count: 16,
    after_summary: 'fresh summary',
    community_id_consistent: true,
    fake_ollama_generate_requests_zero: true,
  })
})

test('buildSuccessfulCommunitySummaryRefreshNormalizer supports large community refresh variants', () => {
  const normalize = buildSuccessfulCommunitySummaryRefreshNormalizer({
    includeProfile: true,
    includeEntityCount: true,
    customNormalize: ({ summary }) => ({
      fake_ollama_generate_requests: summary.fake_ollama_generate_requests ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-29',
      status: 'passed',
      profile: 'large_summary',
      community_id: 'comm-launch-owners',
      initial_summary: 'stale large summary should be replaced',
      refreshed_summary: 'fresh summary',
      entity_count: 4,
      fake_ollama_generate_requests: 1,
      final_url: '/communities#comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      before_summary: { id: 'comm-launch-owners', title: 'Launch Owners' },
      regenerate: { community_id: 'comm-launch-owners', summary: 'fresh summary', token_count: 64 },
      after_summary: { id: 'comm-launch-owners', summary: 'fresh summary' },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-29',
    status: 'passed',
    profile: 'large_summary',
    community_id: 'comm-launch-owners',
    initial_summary: 'stale large summary should be replaced',
    refreshed_summary: 'fresh summary',
    summary_changed: true,
    entity_count: 4,
    final_route: '/communities#comm-launch-owners',
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
    before_title: 'Launch Owners',
    regenerate_summary: 'fresh summary',
    regenerate_token_count: 64,
    after_summary: 'fresh summary',
    community_id_consistent: true,
    fake_ollama_generate_requests: 1,
  })
})


test('buildCommunityDetailNavigationNormalizer supports memory-detail to community-detail variants', () => {
  const normalize = buildCommunityDetailNavigationNormalizer({
    customNormalize: ({ summary, http }) => ({
      memory_context_entities: summary.memory_context_entities ?? null,
      community_relationship_type: summary.community_relationship_type ?? null,
      memory_id_matches_detail: summary.memory_id === http.memory_detail?.id,
      memory_content: http.memory_detail?.content ?? null,
      memory_title: http.memory_detail?.metadata?.title ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-25',
      status: 'passed',
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
      health: { status: 'healthy' },
      memory_detail: { id: 'mem-launch', content: 'Alice owns the launch checklist.', metadata: { title: 'Launch ownership note' } },
      memory_context: { entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }] },
      community_detail: { id: 'comm-launch-owners', title: 'Launch Owners', summary: 'Alice owns the launch checklist and release coordination.' },
      community_entities: { entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }] },
      community_relationships: { relationships: [{ source: 'Alice', target: 'Launch Checklist', type: 'owns' }] },
      community_ancestors: { ancestors: [] },
      community_descendants: { descendants: [] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-25',
    status: 'passed',
    community_id: 'comm-launch-owners',
    memory_context_entities: 2,
    memory_context_communities: 1,
    community_entities_total: 2,
    community_relationships_total: 1,
    ancestors_total: 0,
    descendants_total: 0,
    final_route: '/communities#comm-launch-owners',
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
    community_id_matches_detail: true,
    memory_context_entity_names: ['Alice', 'Launch Checklist'],
    community_title: 'Launch Owners',
    community_summary: 'Alice owns the launch checklist and release coordination.',
    community_entity_names: ['Alice', 'Launch Checklist'],
    community_relationships: [{ source: 'Alice', target: 'Launch Checklist', type: 'owns' }],
    ancestor_titles: [],
    descendant_titles: [],
    community_relationship_type: 'owns',
    memory_id_matches_detail: true,
    memory_content: 'Alice owns the launch checklist.',
    memory_title: 'Launch ownership note',
  })
})

test('buildCommunityDetailNavigationNormalizer supports dashboard-recent to community-detail variants', () => {
  const normalize = buildCommunityDetailNavigationNormalizer({
    customNormalize: ({ summary, http }) => ({
      navigation_path: summary.navigation_path ?? null,
      recent_memory_matches_detail:
        summary.recent_memory_id === http.recent_memories?.memories?.[0]?.id
        && summary.recent_memory_id === http.memory_detail?.id,
      community_id_matches_detail:
        summary.community_id === http.memory_context?.communities?.[0]?.id
        && summary.community_id === http.community_detail?.id,
      recent_titles: (http.recent_memories?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
      memory_detail_title: http.memory_detail?.metadata?.title ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-47',
      status: 'passed',
      recent_memory_id: 'mem-launch',
      community_id: 'comm-launch-owners',
      navigation_path: 'dashboard_recent_item,memory_detail,community_detail',
      memory_context_communities: 1,
      community_entities_total: 2,
      community_relationships_total: 1,
      ancestors_total: 0,
      descendants_total: 0,
      final_url: '/communities#comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      recent_memories: { memories: [{ id: 'mem-launch', metadata: { title: 'Launch ownership note' } }] },
      memory_detail: { id: 'mem-launch', metadata: { title: 'Launch ownership note' } },
      memory_context: {
        communities: [{ id: 'comm-launch-owners' }],
        entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }],
      },
      community_detail: { id: 'comm-launch-owners', title: 'Launch Owners', summary: 'Alice owns the launch checklist and release coordination.' },
      community_entities: { entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }] },
      community_relationships: { relationships: [{ source: 'Alice', target: 'Launch Checklist', type: 'owns' }] },
      community_ancestors: { ancestors: [] },
      community_descendants: { descendants: [] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-47',
    status: 'passed',
    community_id: 'comm-launch-owners',
    memory_context_communities: 1,
    community_entities_total: 2,
    community_relationships_total: 1,
    ancestors_total: 0,
    descendants_total: 0,
    final_route: '/communities#comm-launch-owners',
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
    community_id_matches_detail: true,
    memory_context_entity_names: ['Alice', 'Launch Checklist'],
    community_title: 'Launch Owners',
    community_summary: 'Alice owns the launch checklist and release coordination.',
    community_entity_names: ['Alice', 'Launch Checklist'],
    community_relationships: [{ source: 'Alice', target: 'Launch Checklist', type: 'owns' }],
    ancestor_titles: [],
    descendant_titles: [],
    navigation_path: 'dashboard_recent_item,memory_detail,community_detail',
    recent_memory_matches_detail: true,
    recent_titles: ['Launch ownership note'],
    memory_detail_title: 'Launch ownership note',
  })
})

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

test('buildRemainingWebMemoryWriteNormalizer supports list-based memory write variants', () => {
  const normalize = buildRemainingWebMemoryWriteNormalizer({
    includeProfile: true,
    customNormalize: ({ http }) => ({
      archive_target_id: http.archiveTargetId ?? null,
      delete_target_id: http.deleteTargetId ?? null,
      active_before_titles: (http.active_before?.memories ?? []).map((memory) => memory?.metadata?.title).filter(Boolean),
      archived_before_titles: (http.archived_before?.memories ?? []).map((memory) => memory?.metadata?.title).filter(Boolean),
      archive_success: http.archive?.success ?? null,
      archive_message: http.archive?.message ?? null,
      unarchive_success: http.unarchive?.success ?? null,
      unarchive_message: http.unarchive?.message ?? null,
      active_after_delete_titles: (http.active_after_delete?.memories ?? []).map((memory) => memory?.metadata?.title).filter(Boolean),
      archived_after_delete_titles: (http.archived_after_delete?.memories ?? []).map((memory) => memory?.metadata?.title).filter(Boolean),
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-34',
      status: 'passed',
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
      detail_status_after_delete: 404,
      final_url: '/memories',
    },
    http: {
      health: { status: 'healthy' },
      archiveTargetId: 'mem-archive',
      deleteTargetId: 'mem-delete',
      active_before: { memories: [{ metadata: { title: 'Launch ownership note' } }] },
      archived_before: { memories: [{ metadata: { title: 'Archived note' } }] },
      archive: { success: true, message: 'archived' },
      unarchive: { success: true, message: 'unarchived' },
      delete: { success: true, message: 'deleted' },
      active_after_delete: { memories: [{ metadata: { title: 'Remaining note' } }] },
      archived_after_delete: { memories: [{ metadata: { title: 'Archived note' } }] },
      detail_after_delete: { status_code: 404, body: { detail: 'missing' } },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-34',
    status: 'passed',
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
    detail_status_after_delete: 404,
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
    delete_success: true,
    delete_message: 'deleted',
    detail_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
    archive_target_id: 'mem-archive',
    delete_target_id: 'mem-delete',
    active_before_titles: ['Launch ownership note'],
    archived_before_titles: ['Archived note'],
    archive_success: true,
    archive_message: 'archived',
    unarchive_success: true,
    unarchive_message: 'unarchived',
    active_after_delete_titles: ['Remaining note'],
    archived_after_delete_titles: ['Archived note'],
  })
})

test('buildRemainingWebMemoryWriteNormalizer supports search-linked memory write variants', () => {
  const normalize = buildRemainingWebMemoryWriteNormalizer({
    includeNavigationSurface: true,
    includeContextStatusAfterDelete: true,
    customNormalize: ({ summary, http }) => ({
      query_source_matches_recent: summary.recent_memory_id === summary.query_source_memory_id,
      query_answer: http.query?.answer ?? null,
      query_source_titles: (http.query?.sources ?? []).map((source) => source?.metadata?.title ?? source?.title).filter(Boolean),
      memory_detail_title: http.memory_detail?.metadata?.title ?? null,
      memory_context_entity_names: (http.memory_context?.entities ?? []).map((entity) => entity?.name).filter(Boolean),
      archive_success: http.detail_after_archive?.metadata?.archived ?? null,
      unarchive_success: http.detail_after_unarchive?.metadata?.archived === false,
      delete_memory_matches_recent: http.delete?.memory_id === summary.recent_memory_id,
      context_after_delete: {
        status_code: http.context_after_delete?.status_code ?? null,
        detail: http.context_after_delete?.body?.detail ?? null,
      },
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-56',
      status: 'passed',
      navigation_surface: 'search_memory_link',
      recent_memory_id: 'mem-launch',
      query_source_memory_id: 'mem-launch',
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
      final_url: '/memories/mem-launch',
    },
    http: {
      health: { status: 'healthy' },
      query: { answer: 'launch answer', sources: [{ metadata: { title: 'Launch ownership note' } }] },
      memory_detail: { metadata: { title: 'Launch ownership note' } },
      memory_context: { entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }] },
      delete: { memory_id: 'mem-launch', success: true, message: 'deleted' },
      detail_after_archive: { metadata: { archived: true } },
      detail_after_unarchive: { metadata: { archived: false } },
      detail_after_delete: { status_code: 404, body: { detail: 'missing' } },
      context_after_delete: { status_code: 404, body: { detail: 'missing' } },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-56',
    status: 'passed',
    navigation_surface: 'search_memory_link',
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
    final_route: '/memories/mem-launch',
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
    delete_success: true,
    delete_message: 'deleted',
    detail_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
    query_source_matches_recent: true,
    query_answer: 'launch answer',
    query_source_titles: ['Launch ownership note'],
    memory_detail_title: 'Launch ownership note',
    memory_context_entity_names: ['Alice', 'Launch Checklist'],
    archive_success: true,
    unarchive_success: true,
    delete_memory_matches_recent: true,
    context_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
  })
})

test('buildRemainingWebMemoryDeleteFailureNormalizer supports search-linked delete-failure variants', () => {
  const normalize = buildRemainingWebMemoryDeleteFailureNormalizer({
    includeNavigationSurface: true,
    includeQuerySourceMatch: true,
    customNormalize: ({ summary, http }) => ({
      query_answer: http.query?.answer ?? null,
      query_source_titles: (http.query?.sources ?? []).map((source) => source?.metadata?.title ?? source?.title).filter(Boolean),
      delete_memory_matches_recent: http.delete?.body?.memory_id === summary.recent_memory_id,
      all_after_titles: (http.all_after_delete?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-57',
      status: 'passed',
      navigation_surface: 'search_memory_link',
      recent_memory_id: 'mem-launch',
      query_source_memory_id: 'mem-launch',
      delete_status: 200,
      detail_status_after_delete: 404,
      context_status_after_delete: 404,
      total_after_delete: 0,
      final_url: '/memories/mem-launch',
    },
    http: {
      health: { status: 'healthy' },
      query: { answer: 'launch answer', sources: [{ metadata: { title: 'Launch ownership note' } }] },
      delete: { body: { memory_id: 'mem-launch', success: true, message: 'deleted' } },
      detail_after_delete: { status_code: 404, body: { detail: 'missing' } },
      context_after_delete: { status_code: 404, body: { detail: 'missing' } },
      all_after_delete: { memories: [] },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-57',
    status: 'passed',
    navigation_surface: 'search_memory_link',
    query_source_matches_recent: true,
    delete_status: 200,
    detail_status_after_delete: 404,
    context_status_after_delete: 404,
    total_after_delete: 0,
    final_route: '/memories/mem-launch',
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
    delete_success: true,
    delete_message: 'deleted',
    detail_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
    context_after_delete: {
      status_code: 404,
      detail: 'missing',
    },
    query_answer: 'launch answer',
    query_source_titles: ['Launch ownership note'],
    delete_memory_matches_recent: true,
    all_after_titles: [],
  })
})

test('buildRemainingWebMemoryDeleteFailureNormalizer supports seeded missing-detail failure variants', () => {
  const normalize = buildRemainingWebMemoryDeleteFailureNormalizer({
    includeAfterDeleteStatusFields: false,
    customNormalize: ({ summary, http }) => ({
      missing_memory_id: summary.missing_memory_id ?? null,
      missing_detail_status: summary.missing_detail_status ?? null,
      missing_context_status: summary.missing_context_status ?? null,
      deleted_detail_status: summary.deleted_detail_status ?? null,
      deleted_context_status: summary.deleted_context_status ?? null,
      total_before_delete: summary.total_before_delete ?? null,
      seeded_memory_matches_delete: summary.seeded_memory_id === http.delete?.body?.memory_id,
      seeded_detail_title: http.seeded_detail?.metadata?.title ?? null,
      missing_detail: {
        status_code: http.missing_detail?.status_code ?? null,
        detail: http.missing_detail?.body?.detail ?? null,
      },
      missing_context: {
        status_code: http.missing_context?.status_code ?? null,
        detail: http.missing_context?.body?.detail ?? null,
      },
      all_before_titles: (http.all_before_delete?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
      deleted_detail: {
        status_code: http.deleted_detail?.status_code ?? null,
        detail: http.deleted_detail?.body?.detail ?? null,
      },
      deleted_context: {
        status_code: http.deleted_context?.status_code ?? null,
        detail: http.deleted_context?.body?.detail ?? null,
      },
      all_after_titles: (http.all_after_delete?.memories ?? []).map((memory) => memory?.metadata?.title ?? memory?.title).filter(Boolean),
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-37',
      status: 'passed',
      seeded_memory_id: 'mem-launch',
      missing_memory_id: 'mem-missing',
      missing_detail_status: 404,
      missing_context_status: 404,
      delete_status: 200,
      deleted_detail_status: 404,
      deleted_context_status: 404,
      total_before_delete: 1,
      total_after_delete: 0,
      final_url: '/memories',
    },
    http: {
      health: { status: 'healthy' },
      seeded_detail: { metadata: { title: 'Launch ownership note' } },
      missing_detail: { status_code: 404, body: { detail: 'missing detail' } },
      missing_context: { status_code: 404, body: { detail: 'missing context' } },
      all_before_delete: { memories: [{ metadata: { title: 'Launch ownership note' } }] },
      delete: { body: { memory_id: 'mem-launch', success: true, message: 'deleted' } },
      detail_after_delete: { status_code: 404, body: { detail: 'missing after delete' } },
      context_after_delete: { status_code: 404, body: { detail: 'missing context after delete' } },
      all_after_delete: { memories: [] },
      deleted_detail: { status_code: 404, body: { detail: 'deleted detail missing' } },
      deleted_context: { status_code: 404, body: { detail: 'deleted context missing' } },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-37',
    status: 'passed',
    delete_status: 200,
    total_after_delete: 0,
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
    delete_success: true,
    delete_message: 'deleted',
    detail_after_delete: {
      status_code: 404,
      detail: 'missing after delete',
    },
    context_after_delete: {
      status_code: 404,
      detail: 'missing context after delete',
    },
    missing_memory_id: 'mem-missing',
    missing_detail_status: 404,
    missing_context_status: 404,
    deleted_detail_status: 404,
    deleted_context_status: 404,
    total_before_delete: 1,
    seeded_memory_matches_delete: true,
    seeded_detail_title: 'Launch ownership note',
    missing_detail: {
      status_code: 404,
      detail: 'missing detail',
    },
    missing_context: {
      status_code: 404,
      detail: 'missing context',
    },
    all_before_titles: ['Launch ownership note'],
    deleted_detail: {
      status_code: 404,
      detail: 'deleted detail missing',
    },
    deleted_context: {
      status_code: 404,
      detail: 'deleted context missing',
    },
    all_after_titles: [],
  })
})

test('buildRemainingWebCommunityFailureNormalizer supports lineage-failure community variants', () => {
  const normalize = buildRemainingWebCommunityFailureNormalizer({
    includeAncestorError: true,
    includeDescendantError: true,
    includeEntityData: true,
    includeRelationshipData: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-40',
      status: 'passed',
      target_community_id: 'comm-release-readiness',
      ancestors_status: 500,
      descendants_status: 500,
      entities_status: 200,
      relationships_status: 200,
      final_url: '/communities#comm-release-readiness',
    },
    http: {
      health: { status: 'healthy' },
      community_detail: { title: 'Release Readiness' },
      ancestors: { status_code: 500, body: { detail: 'ancestors failed' } },
      descendants: { status_code: 500, body: { detail: 'descendants failed' } },
      entities: { entities: [{ name: 'Integration Tests' }], total: 1 },
      relationships: { relationships: [{ type: 'depends_on' }], total: 1 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-40',
    status: 'passed',
    target_community_id: 'comm-release-readiness',
    ancestors_status: 500,
    descendants_status: 500,
    entities_status: 200,
    relationships_status: 200,
    final_route: '/communities#comm-release-readiness',
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
    community_title: 'Release Readiness',
    ancestors: {
      status_code: 500,
      detail: 'ancestors failed',
    },
    descendants: {
      status_code: 500,
      detail: 'descendants failed',
    },
    entity_names: ['Integration Tests'],
    entity_total: 1,
    relationship_types: ['depends_on'],
    relationship_total: 1,
  })
})

test('buildRemainingWebCommunitySummaryRefreshNormalizer supports facet-failure refresh variants', () => {
  const normalize = buildRemainingWebCommunitySummaryRefreshNormalizer({
    includeAncestorTitles: true,
  })

  const result = normalize({
    summary: {
      command: 'node task-43',
      status: 'passed',
      target_community_id: 'comm-release-readiness',
      before_summary: 'stale summary',
      refreshed_summary: 'fresh summary',
      entities_status: 500,
      relationships_status: 500,
      ancestors_status: 200,
      descendants_status: 200,
      final_url: '/communities#comm-release-readiness',
    },
    http: {
      health: { status: 'healthy' },
      before_summary: { title: 'Release Readiness' },
      after_summary: { title: 'Release Readiness' },
      entities: { status_code: 500, body: { detail: 'entities failed' } },
      relationships: { status_code: 500, body: { detail: 'relationships failed' } },
      ancestors: { ancestors: [{ title: 'Level 2 Cluster 1' }], total: 1 },
      descendants: { total: 0 },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-43',
    status: 'passed',
    target_community_id: 'comm-release-readiness',
    before_summary: 'stale summary',
    refreshed_summary: 'fresh summary',
    summary_changed: true,
    entities_status: 500,
    relationships_status: 500,
    ancestors_status: 200,
    descendants_status: 200,
    final_route: '/communities#comm-release-readiness',
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
    before_title: 'Release Readiness',
    after_title: 'Release Readiness',
    entities: {
      status_code: 500,
      detail: 'entities failed',
    },
    relationships: {
      status_code: 500,
      detail: 'relationships failed',
    },
    ancestor_titles: ['Level 2 Cluster 1'],
    ancestor_total: 1,
    descendant_total: 0,
  })
})
