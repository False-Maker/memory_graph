import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildHighSignalSingleMemoryContextEvidenceAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'
import {
  buildSingleMemoryContextReadNormalizer,
} from './focused-real-smoke-compare-cases/helpers.mjs'
import {
  buildSingleMemoryContextSchemaCase,
  buildSingleMemoryContextValueCase,
} from './focused-real-smoke-single-memory-context-contract-helpers.mjs'

test('buildSingleMemoryContextSchemaCase supports search-style variants', () => {
  assert.deepEqual(
    buildSingleMemoryContextSchemaCase({
      summaryMemoryIdKey: 'memory_id',
      summaryContextCountKey: 'context_community_count',
      includeCommunityId: true,
      extraSummaryKeys: ['query_modes_tested'],
      httpKeys: ['memories', 'query_modes'],
    }),
    {
      summaryKeys: ['memory_id', 'community_id', 'context_community_count', 'query_modes_tested'],
      httpKeys: ['health', 'communities', 'memory_context', 'memories', 'query_modes'],
    }
  )
})

test('buildSingleMemoryContextValueCase supports dashboard-style variants', () => {
  const valueCase = buildSingleMemoryContextValueCase({
    memoryIdPattern: /recent_memory_id:\s*seedPayload\.memory_id/,
    contextCountPattern: /detail_context_communities:\s*httpEvidence\.memoryContext\.json\?\.total_communities/,
    patterns: [/recent_item_navigation:\s*'memory_detail'/],
    tailPatterns: [/memory_detail:\s*httpEvidence\.memoryDetail\.json/],
  })

  assert.equal(valueCase.patterns.length, 4)
  assert.match('recent_memory_id: seedPayload.memory_id', valueCase.patterns[0])
  assert.match('detail_context_communities: httpEvidence.memoryContext.json?.total_communities', valueCase.patterns[1])
  assert.match("recent_item_navigation: 'memory_detail'", valueCase.patterns[2])
  assert.match('memory_detail: httpEvidence.memoryDetail.json', valueCase.patterns[3])
})

test('buildSingleMemoryContextReadNormalizer supports search navigation memory-context variants', () => {
  const normalize = buildSingleMemoryContextReadNormalizer({
    getMemoryContent: (http) => http.memories?.memories?.[0]?.content ?? null,
    customNormalize: ({ summary, http }) => ({
      community_id: summary.community_id ?? null,
      query_modes_tested: summary.query_modes_tested ?? [],
      browser_modes_tested: summary.browser_modes_tested ?? [],
      source_detail_loaded: summary.source_detail_loaded ?? null,
      community_link_surfaces_tested: summary.community_link_surfaces_tested ?? [],
      context_community_count: summary.context_community_count ?? null,
      query_source_memory_matches_summary: summary.query_source_memory_id === summary.memory_id,
      query_source_community_matches_summary: summary.query_source_community_id === summary.community_id,
      memory_total: http.memories?.total ?? null,
      community_total: http.communities?.total ?? null,
      community_summary: http.communities?.communities?.[0]?.summary ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-24',
      status: 'passed',
      community_id: 'comm-launch-owners',
      query_modes_tested: ['global', 'local', 'hybrid'],
      browser_modes_tested: ['global', 'local', 'hybrid'],
      source_detail_loaded: true,
      community_link_surfaces_tested: ['source', 'result'],
      context_community_count: 1,
      memory_id: 'mem-launch',
      query_source_memory_id: 'mem-launch',
      query_source_community_id: 'comm-launch-owners',
      final_url: '/communities#comm-launch-owners',
    },
    http: {
      health: { status: 'healthy' },
      memories: { total: 1, memories: [{ content: 'Alice owns the launch checklist.' }] },
      communities: { total: 1, communities: [{ title: 'Launch Owners', summary: 'Alice owns the launch checklist and release coordination.' }] },
      memory_context: {
        entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }],
        total_entities: 2,
        total_communities: 1,
      },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-24',
    status: 'passed',
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
    community_title: 'Launch Owners',
    memory_content: 'Alice owns the launch checklist.',
    memory_context_entity_names: ['Alice', 'Launch Checklist'],
    memory_context_total_entities: 2,
    memory_context_total_communities: 1,
    community_id: 'comm-launch-owners',
    query_modes_tested: ['global', 'local', 'hybrid'],
    browser_modes_tested: ['global', 'local', 'hybrid'],
    source_detail_loaded: true,
    community_link_surfaces_tested: ['source', 'result'],
    context_community_count: 1,
    query_source_memory_matches_summary: true,
    query_source_community_matches_summary: true,
    memory_total: 1,
    community_total: 1,
    community_summary: 'Alice owns the launch checklist and release coordination.',
  })
})

test('buildSingleMemoryContextReadNormalizer supports dashboard recent-memory context variants', () => {
  const normalize = buildSingleMemoryContextReadNormalizer({
    finalRouteResolver: (summary) => summary.final_url.replace(summary.recent_memory_id, ':id'),
    getMemoryContent: (http) => http.memory_detail?.content ?? null,
    customNormalize: ({ summary, http }) => ({
      total_entities: summary.total_entities ?? null,
      total_relationships: summary.total_relationships ?? null,
      total_memories: summary.total_memories ?? null,
      total_communities: summary.total_communities ?? null,
      recent_memories_total: summary.recent_memories_total ?? null,
      recent_item_navigation: summary.recent_item_navigation ?? null,
      detail_context_communities: summary.detail_context_communities ?? null,
      recent_memory_consistent:
        summary.recent_memory_id === http.memories?.memories?.[0]?.id
        && summary.recent_memory_id === http.memory_detail?.id,
      entity_types: http.stats?.entity_types ?? {},
      memory_title: http.memory_detail?.metadata?.title ?? null,
    }),
  })

  const result = normalize({
    summary: {
      command: 'node task-28',
      status: 'passed',
      total_entities: 2,
      total_relationships: 1,
      total_memories: 1,
      total_communities: 1,
      recent_memories_total: 1,
      recent_memory_id: 'mem-launch',
      recent_item_navigation: 'memory_detail',
      detail_context_communities: 1,
      final_url: '/memories/mem-launch',
    },
    http: {
      health: { status: 'healthy' },
      stats: { entity_types: { document: 1, person: 1 } },
      communities: { communities: [{ title: 'Launch Owners' }] },
      memories: { memories: [{ id: 'mem-launch' }] },
      memory_detail: { id: 'mem-launch', content: 'Alice owns the launch checklist.', metadata: { title: 'Launch ownership note' } },
      memory_context: {
        entities: [{ name: 'Alice' }, { name: 'Launch Checklist' }],
        total_entities: 2,
        total_communities: 1,
      },
    },
  })

  assert.deepEqual(result, {
    command: 'node task-28',
    status: 'passed',
    final_route: '/memories/:id',
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
    community_title: 'Launch Owners',
    memory_content: 'Alice owns the launch checklist.',
    memory_context_entity_names: ['Alice', 'Launch Checklist'],
    memory_context_total_entities: 2,
    memory_context_total_communities: 1,
    total_entities: 2,
    total_relationships: 1,
    total_memories: 1,
    total_communities: 1,
    recent_memories_total: 1,
    recent_item_navigation: 'memory_detail',
    detail_context_communities: 1,
    recent_memory_consistent: true,
    entity_types: { document: 1, person: 1 },
    memory_title: 'Launch ownership note',
  })
})

test('buildHighSignalSingleMemoryContextEvidenceAssertion supports search navigation variants', () => {
  const assertion = buildHighSignalSingleMemoryContextEvidenceAssertion('task-memory-context-search', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        memory_id: 'mem-launch',
        community_id: 'comm-launch-owners',
        query_modes_tested: ['global', 'local', 'hybrid'],
        browser_modes_tested: ['global', 'local', 'hybrid'],
        source_detail_loaded: true,
        query_source_memory_id: 'mem-launch',
        query_source_community_id: 'comm-launch-owners',
        community_link_surfaces_tested: ['source', 'result'],
        context_community_count: 1,
        fake_ollama_embedding_requests: 8,
        fake_ollama_generate_requests: 5,
      },
      http: {
        query_modes: {
          global: {
            sources: [{ memory_id: 'mem-launch', community_id: 'comm-launch-owners' }],
          },
        },
        memory_context: { total_communities: 1 },
      },
    })
  })
})

test('buildHighSignalSingleMemoryContextEvidenceAssertion supports dashboard memory-context variants', () => {
  const assertion = buildHighSignalSingleMemoryContextEvidenceAssertion('task-memory-context-dashboard', {
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
  })

  assert.doesNotThrow(() => {
    assertion({
      summary: {
        total_entities: 2,
        total_relationships: 1,
        total_memories: 1,
        total_communities: 1,
        recent_memories_total: 1,
        recent_memory_id: 'mem-launch',
        recent_item_navigation: 'memory_detail',
        detail_context_communities: 1,
      },
      http: {
        memory_detail: { id: 'mem-launch' },
        memories: { memories: [{ id: 'mem-launch' }] },
        memory_context: { total_communities: 1 },
      },
    })
  })
})
