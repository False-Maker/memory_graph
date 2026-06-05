function clone(value) {
  return structuredClone(value)
}

function buildJsonResponse(body, status = 200) {
  return {
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  }
}

async function fulfillJson(route, body, status = 200) {
  await route.fulfill(buildJsonResponse(body, status))
}

async function registerRoutePatterns(context, patterns, handler) {
  for (const pattern of patterns) {
    await context.route(pattern, handler)
  }
}

export function buildT8SearchHappyQueryPayload() {
  return {
    answer: '图谱中包含项目启动会、技术方案评审与迭代复盘等记忆。',
    sources: [
      {
        memory_id: 'memory-1',
        content: '项目启动会确认了里程碑与负责人。',
        relevance: 0.92,
        community_id: 'community-alpha',
        community_summary: '围绕启动会、负责人和里程碑的社区摘要。',
        provenance: {
          type: 'decision',
          time: '2026-04-03T09:00:00Z',
          imported_from: 'notes/startup.md',
        },
        source: 'manual',
        title: '项目启动会',
        workspace_id: 'workspace-project',
        timestamp: '2026-04-03T09:00:00Z',
        entities: ['项目', '负责人'],
      },
      {
        memory_id: 'memory-2',
        content: '技术方案评审讨论了检索策略与缓存机制。',
        relevance: 0.84,
        community_id: 'community-beta',
        community_summary: '技术方案与缓存策略社区摘要。',
        source: 'sync',
        title: '技术方案评审',
        workspace_id: 'workspace-project',
        timestamp: '2026-04-04T08:30:00Z',
        entities: ['检索', '缓存'],
      },
    ],
    strategy: 'local',
    entities: ['项目', '检索'],
    communities: [
      {
        community_id: 'community-alpha',
        title: '项目主社区',
        summary: '围绕启动会、负责人和里程碑的社区摘要。',
        level: 0,
        entities: ['项目', '负责人'],
        relevance: 0.93,
      },
    ],
    processing_time_ms: 148,
  }
}

export function buildT8SearchSourceDetailFallbackPayload() {
  return {
    answer: '图谱里存在一条暂时缺少 memory_id 的来源证据。',
    sources: [
      {
        content: 'Alice 仍然负责 launch checklist 和 release coordination。',
        relevance: 0.88,
        community_id: 'community-alpha',
        community_summary: '围绕启动会、负责人和里程碑的社区摘要。',
        provenance: {
          type: 'decision',
          time: '2026-04-03T09:00:00Z',
          imported_from: 'notes/startup.md',
        },
        source: 'manual',
        title: '缺失 memory_id 的来源',
        workspace_id: 'workspace-project',
        timestamp: '2026-04-03T09:00:00Z',
        entities: ['Alice', 'Launch Checklist'],
      },
    ],
    strategy: 'local',
    entities: ['Alice'],
    communities: [
      {
        community_id: 'community-alpha',
        title: '项目主社区',
        summary: '围绕启动会、负责人和里程碑的社区摘要。',
        level: 0,
        entities: ['Alice', 'Launch Checklist'],
        relevance: 0.89,
      },
    ],
    processing_time_ms: 132,
  }
}

export function buildT9GraphHappyPayload() {
  return {
    entities: [
      { id: 'n-1', name: '人工智能', type: 'entity', properties: { description: 'AI 节点描述' }, community_id: 'c-1' },
      { id: 'n-2', name: '机器学习', type: 'entity', community_id: 'c-1' },
      { id: 'n-3', name: '深度学习', type: 'entity', community_id: 'c-2' },
      { id: 'n-4', name: '社区节点', type: 'community', community_id: 'c-2' },
    ],
    relationships: [
      { source_id: 'n-1', target_id: 'n-2', type: 'related_to' },
      { source_id: 'n-2', target_id: 'n-3', type: 'depends_on' },
      { source_id: 'n-4', target_id: 'n-3', type: 'contains' },
    ],
  }
}

export function buildT10CommunitiesPayload() {
  return [
    {
      id: 'c-root',
      title: 'AI 社区',
      summary: '覆盖大模型和检索主题。',
      level: 0,
      entity_count: 12,
      rank: 0.9,
      created_at: '2026-03-20T08:00:00Z',
    },
    {
      id: 'c-child',
      title: '机器学习子社区',
      summary: '聚焦训练、评估和部署。',
      level: 1,
      entity_count: 7,
      rank: 0.8,
      created_at: '2026-03-20T08:01:00Z',
      parent_id: 'c-root',
    },
  ]
}

export function buildT18MemoryRecords() {
  return [
    {
      id: 'mem-1',
      content: 'Memory one body',
      metadata: {
        source: 'manual',
        title: 'Memory One',
        tags: ['alpha'],
        source_path: 'notes/memory-one.md',
        record_type: 'decision',
        timestamp: '2026-04-03T08:58:00Z',
        archived: false,
      },
      provenance: {
        type: 'decision',
        time: '2026-04-03T08:58:00Z',
        imported_from: 'notes/memory-one.md',
      },
      created_at: '2026-04-03T09:00:00Z',
    },
    {
      id: 'mem-2',
      content: 'Memory two body',
      metadata: {
        source: 'sync',
        title: 'Memory Two',
        tags: ['beta'],
        archived: false,
      },
      provenance: {
        type: 'sync',
        time: '2026-04-03T09:05:00Z',
        imported_from: 'sync://memory-two',
      },
      created_at: '2026-04-03T09:05:00Z',
    },
    {
      id: 'mem-3',
      content: 'Archived memory body',
      metadata: {
        source: 'manual',
        title: 'Memory Three',
        tags: ['gamma'],
        archived: true,
        archived_at: '2026-04-05T12:00:00Z',
      },
      provenance: {
        type: 'manual',
        time: '2026-04-03T09:10:00Z',
        imported_from: 'notes/memory-three.md',
      },
      created_at: '2026-04-03T09:10:00Z',
    },
  ]
}

export async function registerT8SearchHappyPathRoutes(context) {
  const state = { queryRequestCount: 0 }
  const queryPayload = buildT8SearchHappyQueryPayload()

  await context.route('**/api/v1/query', async (route) => {
    state.queryRequestCount += 1
    const payload = route.request().postDataJSON()

    if (payload?.question === '图谱里有哪些项目记忆？') {
      await fulfillJson(route, queryPayload)
      return
    }

    await fulfillJson(route, { detail: 'unexpected query in happy path' }, 500)
  })

  await context.route('**/api/v1/memories?**', async (route) => {
    await fulfillJson(route, {
      memories: [
        {
          id: 'memory-1',
          content: '项目启动会确认了里程碑与负责人。',
          metadata: { source: 'manual', title: '项目启动会', tags: ['项目'] },
          provenance: {
            type: 'decision',
            time: '2026-04-03T09:00:00Z',
            imported_from: 'notes/startup.md',
          },
          created_at: '2026-04-03T09:00:00Z',
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    })
  })

  await context.route('**/api/v1/memories/memory-1', async (route) => {
    await fulfillJson(route, {
      id: 'memory-1',
      content: '项目启动会确认了里程碑与负责人。',
      metadata: {
        source: 'manual',
        title: '项目启动会',
        tags: ['项目'],
        source_path: 'notes/startup.md',
        record_type: 'decision',
        timestamp: '2026-04-03T09:00:00Z',
      },
      provenance: {
        type: 'decision',
        time: '2026-04-03T09:00:00Z',
        imported_from: 'notes/startup.md',
      },
      created_at: '2026-04-03T09:00:00Z',
    })
  })

  await context.route('**/api/v1/memories/memory-1/context', async (route) => {
    await fulfillJson(route, {
      memory_id: 'memory-1',
      entities: [
        { id: 'entity-1', name: '负责人', type: 'person', mention_text: '负责人已确认', confidence: 0.9 },
      ],
      communities: [
        { id: 'community-alpha', title: '项目主社区', level: 0, entity_count: 3, summary: '项目启动社区' },
      ],
      total_entities: 1,
      total_communities: 1,
    })
  })

  await registerRoutePatterns(context, ['**/api/v1/communities', '**/api/v1/communities?*'], async (route) => {
    await fulfillJson(route, {
      communities: [
        {
          id: 'community-alpha',
          title: '项目主社区',
          summary: '围绕启动会、负责人和里程碑的社区摘要。',
          level: 0,
          entity_count: 3,
          rank: 0.9,
          created_at: '2026-04-03T09:10:00Z',
        },
      ],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/community-alpha', async (route) => {
    await fulfillJson(route, {
      id: 'community-alpha',
      title: '项目主社区',
      summary: '围绕启动会、负责人和里程碑的社区摘要。',
      level: 0,
      entity_count: 3,
      rank: 0.9,
      created_at: '2026-04-03T09:10:00Z',
    })
  })

  await context.route('**/api/v1/communities/community-alpha/entities*', async (route) => {
    await fulfillJson(route, {
      community_id: 'community-alpha',
      entities: [{ id: 'entity-1', name: '负责人', type: 'person' }],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/community-alpha/relationships*', async (route) => {
    await fulfillJson(route, {
      community_id: 'community-alpha',
      relationships: [{ id: 'rel-1', source: '项目', target: '负责人', type: 'assigned_to' }],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/community-alpha/ancestors*', async (route) => {
    await fulfillJson(route, { community_id: 'community-alpha', ancestors: [], total: 0 })
  })

  await context.route('**/api/v1/communities/community-alpha/descendants*', async (route) => {
    await fulfillJson(route, { community_id: 'community-alpha', descendants: [], total: 0 })
  })

  return state
}

export async function registerT8SearchFailureRoutes(context) {
  await context.route('**/api/v1/query', async (route) => {
    await fulfillJson(route, { detail: 'query service unavailable' }, 500)
  })
}

export async function registerT8SearchSourceDetailFallbackRoutes(context) {
  const state = {
    queryRequestCount: 0,
    detailRequestCount: 0,
  }
  const queryPayload = buildT8SearchSourceDetailFallbackPayload()

  await context.route('**/api/v1/query', async (route) => {
    state.queryRequestCount += 1
    const payload = route.request().postDataJSON()

    if (payload?.question === '图谱里有哪些缺失记忆编号的来源？') {
      await fulfillJson(route, queryPayload)
      return
    }

    await fulfillJson(route, { detail: 'unexpected query in source detail fallback path' }, 500)
  })

  await context.route('**/api/v1/memories/*', async (route) => {
    state.detailRequestCount += 1
    await fulfillJson(route, { detail: 'unexpected memory detail request for source without memory_id' }, 500)
  })

  return state
}

export async function registerT9GraphRoutes(context, { empty = false } = {}) {
  const payload = empty ? { entities: [], relationships: [] } : buildT9GraphHappyPayload()
  const state = {
    entityCount: payload.entities.length,
    relationshipCount: payload.relationships.length,
  }

  await context.route('**/api/v1/graph/entities?limit=200', async (route) => {
    await fulfillJson(route, { entities: clone(payload.entities) })
  })

  await context.route('**/api/v1/graph/relationships?limit=400', async (route) => {
    await fulfillJson(route, { relationships: clone(payload.relationships) })
  })

  return state
}

export async function registerT10CommunityRoutes(context, { summaryFailure = false } = {}) {
  const communities = clone(buildT10CommunitiesPayload())
  const state = { detectCount: 0, summaryFailure }

  await context.route('**/api/v1/communities/detect*', async (route) => {
    state.detectCount += 1
    await fulfillJson(route, {
      job_id: `job-${state.detectCount}`,
      status: 'completed',
      algorithm: 'leiden',
      resolution: 1.0,
      num_communities: communities.length,
      modularity: 0.42,
      message: 'Community detection completed.',
    })
  })

  await context.route('**/api/v1/communities/hierarchy*', async (route) => {
    await fulfillJson(route, {
      roots: [
        {
          id: 'c-root',
          title: 'AI 社区',
          level: 0,
          entity_count: 12,
          children: [{ id: 'c-child', title: '机器学习子社区', level: 1, entity_count: 7, children: [] }],
        },
      ],
      max_level: 1,
      total_communities: 2,
    })
  })

  await registerRoutePatterns(context, ['**/api/v1/communities', '**/api/v1/communities?*'], async (route) => {
    const level = new URL(route.request().url()).searchParams.get('level')
    const filtered = level === null ? communities : communities.filter((item) => String(item.level) === String(level))
    await fulfillJson(route, { communities: clone(filtered), total: filtered.length })
  })

  await context.route('**/api/v1/communities/c-root', async (route) => {
    await fulfillJson(route, clone(communities[0]))
  })

  await context.route('**/api/v1/communities/c-child', async (route) => {
    await fulfillJson(route, clone(communities[1]))
  })

  await context.route('**/api/v1/communities/c-root/summarize', async (route) => {
    const payload = route.request().postDataJSON?.() ?? {}
    if (payload?.regenerate !== true) {
      await fulfillJson(route, { detail: 'regenerate=true is required for summary refresh' }, 400)
      return
    }

    if (summaryFailure) {
      await fulfillJson(route, { detail: 'summary service unavailable' }, 500)
      return
    }

    await fulfillJson(route, {
      community_id: 'c-root',
      summary: '新的摘要：AI 社区涵盖推理、检索增强和应用实践。',
      generated_at: '2026-03-20T08:20:00Z',
      token_count: 16,
    })
  })

  await context.route('**/api/v1/communities/c-root/entities*', async (route) => {
    await fulfillJson(route, {
      community_id: 'c-root',
      entities: [{ id: 'e-1', name: '大模型' }, { id: 'e-2', name: 'RAG' }],
      total: 2,
    })
  })

  await context.route('**/api/v1/communities/c-root/relationships*', async (route) => {
    await fulfillJson(route, {
      community_id: 'c-root',
      relationships: [{ id: 'r-1', source: '大模型', target: 'RAG', type: 'supports' }],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/c-root/ancestors*', async (route) => {
    await fulfillJson(route, { community_id: 'c-root', ancestors: [], total: 0 })
  })

  await context.route('**/api/v1/communities/c-root/descendants*', async (route) => {
    await fulfillJson(route, {
      community_id: 'c-root',
      descendants: [{ id: 'c-child', title: '机器学习子社区' }],
      total: 1,
    })
  })

  return state
}

export async function registerT18MemoriesHappyPathRoutes(context) {
  const state = {
    deleteCalls: 0,
    archiveCalls: 0,
    unarchiveCalls: 0,
    memoryRecords: clone(buildT18MemoryRecords()),
  }

  await context.route('**/api/v1/memories?**', async (route) => {
    const url = new URL(route.request().url())
    const status = (url.searchParams.get('status') || 'active').toLowerCase()
    const filtered = state.memoryRecords.filter((memory) => {
      const archived = memory.metadata?.archived === true
      if (status === 'all') return true
      if (status === 'archived') return archived
      return !archived
    })

    await fulfillJson(route, {
      memories: clone(filtered),
      total: filtered.length,
      limit: 20,
      offset: 0,
    })
  })

  await context.route('**/api/v1/memories/mem-1', async (route) => {
    if (route.request().method() === 'DELETE') {
      state.deleteCalls += 1
      state.memoryRecords = state.memoryRecords.filter((memory) => memory.id !== 'mem-1')
      await fulfillJson(route, {
        success: true,
        message: 'Memory deleted',
        memory_id: 'mem-1',
        server_version: 2,
        sync_status: 'deleted',
      })
      return
    }

    const memory = state.memoryRecords.find((item) => item.id === 'mem-1') || null
    await fulfillJson(route, clone(memory))
  })

  await context.route('**/api/v1/memories/mem-1/archive', async (route) => {
    state.archiveCalls += 1
    const memory = state.memoryRecords.find((item) => item.id === 'mem-1')
    if (memory) {
      memory.metadata.archived = true
      memory.metadata.archived_at = '2026-04-06T08:00:00Z'
    }
    await fulfillJson(route, {
      success: true,
      memory_id: 'mem-1',
      archived: true,
      archived_at: '2026-04-06T08:00:00Z',
    })
  })

  await context.route('**/api/v1/memories/mem-1/unarchive', async (route) => {
    state.unarchiveCalls += 1
    const memory = state.memoryRecords.find((item) => item.id === 'mem-1')
    if (memory) {
      memory.metadata.archived = false
      delete memory.metadata.archived_at
    }
    await fulfillJson(route, {
      success: true,
      memory_id: 'mem-1',
      archived: false,
      archived_at: null,
    })
  })

  await context.route('**/api/v1/memories/mem-1/context', async (route) => {
    await fulfillJson(route, {
      memory_id: 'mem-1',
      entities: [
        {
          id: 'entity-1',
          name: 'Alice',
          type: 'person',
          mention_text: 'Alice approved the rollout',
          confidence: 0.93,
        },
      ],
      communities: [
        {
          id: 'comm-1',
          title: 'Rollout Cluster',
          level: 1,
          entity_count: 3,
          summary: 'Release planning and rollout context',
        },
      ],
      total_entities: 1,
      total_communities: 1,
    })
  })

  await registerRoutePatterns(context, ['**/api/v1/communities', '**/api/v1/communities?*'], async (route) => {
    await fulfillJson(route, {
      communities: [
        {
          id: 'comm-1',
          title: 'Rollout Cluster',
          summary: 'Release planning and rollout context',
          level: 1,
          entity_count: 3,
          rank: 0.8,
          created_at: '2026-04-03T10:00:00Z',
        },
      ],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/comm-1', async (route) => {
    await fulfillJson(route, {
      id: 'comm-1',
      title: 'Rollout Cluster',
      summary: 'Release planning and rollout context',
      level: 1,
      entity_count: 3,
      rank: 0.8,
      created_at: '2026-04-03T10:00:00Z',
    })
  })

  await context.route('**/api/v1/communities/comm-1/entities*', async (route) => {
    await fulfillJson(route, {
      community_id: 'comm-1',
      entities: [{ id: 'entity-1', name: 'Alice', type: 'person' }],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/comm-1/relationships*', async (route) => {
    await fulfillJson(route, {
      community_id: 'comm-1',
      relationships: [{ id: 'rel-1', source: 'Alice', target: 'Rollout', type: 'approved' }],
      total: 1,
    })
  })

  await context.route('**/api/v1/communities/comm-1/ancestors*', async (route) => {
    await fulfillJson(route, { community_id: 'comm-1', ancestors: [], total: 0 })
  })

  await context.route('**/api/v1/communities/comm-1/descendants*', async (route) => {
    await fulfillJson(route, { community_id: 'comm-1', descendants: [], total: 0 })
  })

  return state
}

export async function registerT18MemoriesFailureRoutes(context) {
  await context.route('**/api/v1/memories?**', async (route) => {
    await fulfillJson(route, { detail: 'memories unavailable' }, 500)
  })
}
