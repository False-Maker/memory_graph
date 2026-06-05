import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildT8SearchHappyQueryPayload,
  buildT8SearchSourceDetailFallbackPayload,
  buildT9GraphHappyPayload,
  buildT10CommunitiesPayload,
  buildT18MemoryRecords,
  registerT8SearchHappyPathRoutes,
  registerT9GraphRoutes,
  registerT10CommunityRoutes,
  registerT8SearchSourceDetailFallbackRoutes,
  registerT18MemoriesHappyPathRoutes,
} from './mainline-playwright-fixtures.mjs'

function createRouteRecorder() {
  const entries = []

  return {
    context: {
      async route(pattern, handler) {
        entries.push({ pattern, handler })
      },
    },
    find(pattern) {
      const normalized = String(pattern)
      const entry = entries.find((item) => String(item.pattern) === normalized)
      if (!entry) {
        throw new Error(`Route not registered: ${normalized}`)
      }
      return entry.handler
    },
  }
}

function createMockRoute({ url, method = 'GET', jsonBody } = {}) {
  const fulfillCalls = []

  return {
    request() {
      return {
        url: () => url,
        method: () => method,
        postDataJSON: () => jsonBody,
      }
    },
    async fulfill(payload) {
      fulfillCalls.push(payload)
    },
    lastJson() {
      return JSON.parse(fulfillCalls.at(-1).body)
    },
  }
}

test('mainline playwright fixture builders keep stable contract shapes', () => {
  const searchPayload = buildT8SearchHappyQueryPayload()
  const graphPayload = buildT9GraphHappyPayload()
  const communities = buildT10CommunitiesPayload()
  const memories = buildT18MemoryRecords()

  assert.equal(searchPayload.sources[0].provenance.imported_from, 'notes/startup.md')
  assert.equal(buildT8SearchSourceDetailFallbackPayload().sources[0].memory_id, undefined)
  assert.equal(searchPayload.communities[0].community_id, 'community-alpha')
  assert.equal(graphPayload.entities.length, 4)
  assert.equal(graphPayload.relationships.length, 3)
  assert.equal(communities[1].parent_id, 'c-root')
  assert.equal(memories[2].metadata.archived, true)
})

test('registerT8SearchHappyPathRoutes wires query contract and tracks request count', async () => {
  const recorder = createRouteRecorder()
  const state = await registerT8SearchHappyPathRoutes(recorder.context)
  const queryHandler = recorder.find('**/api/v1/query')

  const route = createMockRoute({
    url: 'http://127.0.0.1:8000/api/v1/query',
    method: 'POST',
    jsonBody: { question: '图谱里有哪些项目记忆？' },
  })
  await queryHandler(route)

  assert.equal(state.queryRequestCount, 1)
  assert.equal(route.lastJson().sources[0].community_summary, '围绕启动会、负责人和里程碑的社区摘要。')
})

test('registerT8SearchSourceDetailFallbackRoutes keeps missing memory_id source and blocks detail fetches by default', async () => {
  const recorder = createRouteRecorder()
  const state = await registerT8SearchSourceDetailFallbackRoutes(recorder.context)
  const queryHandler = recorder.find('**/api/v1/query')
  const detailHandler = recorder.find('**/api/v1/memories/*')

  const queryRoute = createMockRoute({
    url: 'http://127.0.0.1:8000/api/v1/query',
    method: 'POST',
    jsonBody: { question: '图谱里有哪些缺失记忆编号的来源？' },
  })
  await queryHandler(queryRoute)

  assert.equal(state.queryRequestCount, 1)
  assert.equal(queryRoute.lastJson().sources[0].memory_id, undefined)
  assert.equal(queryRoute.lastJson().sources[0].community_id, 'community-alpha')
  assert.equal(state.detailRequestCount, 0)

  const detailRoute = createMockRoute({
    url: 'http://127.0.0.1:8000/api/v1/memories/missing-memory',
  })
  await detailHandler(detailRoute)

  assert.equal(state.detailRequestCount, 1)
  assert.equal(detailRoute.lastJson().detail, 'unexpected memory detail request for source without memory_id')
})

test('registerT9GraphRoutes supports empty graph payloads', async () => {
  const recorder = createRouteRecorder()
  const state = await registerT9GraphRoutes(recorder.context, { empty: true })
  const entitiesHandler = recorder.find('**/api/v1/graph/entities?limit=200')

  const route = createMockRoute({ url: 'http://127.0.0.1:8000/api/v1/graph/entities?limit=200' })
  await entitiesHandler(route)

  assert.equal(state.entityCount, 0)
  assert.deepEqual(route.lastJson(), { entities: [] })
})

test('registerT10CommunityRoutes increments detect count and keeps summary success payload stable', async () => {
  const recorder = createRouteRecorder()
  const state = await registerT10CommunityRoutes(recorder.context)
  const detectHandler = recorder.find('**/api/v1/communities/detect*')
  const summarizeHandler = recorder.find('**/api/v1/communities/c-root/summarize')

  await detectHandler(createMockRoute({ url: 'http://127.0.0.1:8000/api/v1/communities/detect?algorithm=leiden', method: 'POST' }))
  const summarizeRoute = createMockRoute({
    url: 'http://127.0.0.1:8000/api/v1/communities/c-root/summarize',
    method: 'POST',
    jsonBody: { regenerate: true },
  })
  await summarizeHandler(summarizeRoute)

  assert.equal(state.detectCount, 1)
  assert.match(summarizeRoute.lastJson().summary, /新的摘要：AI 社区/)
})

test('registerT10CommunityRoutes requires regenerate=true for summary refresh', async () => {
  const recorder = createRouteRecorder()
  await registerT10CommunityRoutes(recorder.context)
  const summarizeHandler = recorder.find('**/api/v1/communities/c-root/summarize')

  const summarizeRoute = createMockRoute({
    url: 'http://127.0.0.1:8000/api/v1/communities/c-root/summarize',
    method: 'POST',
    jsonBody: {},
  })
  await summarizeHandler(summarizeRoute)

  assert.equal(summarizeRoute.lastJson().detail, 'regenerate=true is required for summary refresh')
})

test('registerT18MemoriesHappyPathRoutes tracks archive and delete lifecycle', async () => {
  const recorder = createRouteRecorder()
  const state = await registerT18MemoriesHappyPathRoutes(recorder.context)
  const archiveHandler = recorder.find('**/api/v1/memories/mem-1/archive')
  const listHandler = recorder.find('**/api/v1/memories?**')
  const memoryHandler = recorder.find('**/api/v1/memories/mem-1')

  await archiveHandler(createMockRoute({ url: 'http://127.0.0.1:8000/api/v1/memories/mem-1/archive', method: 'POST' }))
  const archivedRoute = createMockRoute({ url: 'http://127.0.0.1:8000/api/v1/memories?status=archived' })
  await listHandler(archivedRoute)
  await memoryHandler(createMockRoute({ url: 'http://127.0.0.1:8000/api/v1/memories/mem-1', method: 'DELETE' }))

  assert.equal(state.archiveCalls, 1)
  assert.equal(state.deleteCalls, 1)
  assert.equal(archivedRoute.lastJson().memories.some((memory) => memory.id === 'mem-1'), true)
})
