import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { chromium } from 'playwright'

import {
  buildBaseUrl,
  findAvailablePort,
  runBuildWeb,
  stopPreviewServer,
} from './settings-playwright-runtime.mjs'
import {
  assertSmoke,
  buildSmokeBrowserEnv,
  requestJson,
  startBackendService,
  waitForStatus,
  writeTempSettingsConfig,
} from './focused-real-smoke-runtime.mjs'
import { runSeedFixture, startFakeOllamaServer } from './search-real-smoke-fixtures.mjs'
import { DASHBOARD_SMOKE_TEST_IDS } from '../pages/DashboardPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'
import { SEARCH_SMOKE_TEST_IDS } from '../pages/SearchPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SEARCH_QUESTION = 'What supports release readiness?'

async function verifyHttpContract({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const stats = await requestJson(`${backendBaseUrl}/api/v1/graph/stats`)
  assertSmoke(stats.statusCode === 200, `GET /graph/stats failed: ${stats.raw}`)
  assertSmoke(stats.json?.total_entities === 5, `Expected 5 entities, got ${stats.json?.total_entities}`)
  assertSmoke(stats.json?.total_relationships === 2, `Expected 2 relationships, got ${stats.json?.total_relationships}`)
  assertSmoke(stats.json?.total_memories === 3, `Expected 3 memories, got ${stats.json?.total_memories}`)

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 3, `Expected 3 communities, got ${communities.json?.total}`)
  const hierarchyRoot = (communities.json?.communities || []).find((community) => Number(community.level) === 2)
  assertSmoke(Boolean(hierarchyRoot), 'Expected one level-2 root community in /communities payload')

  const ancestors = await requestJson(`${backendBaseUrl}/api/v1/communities/comm-release-readiness/ancestors`)
  assertSmoke(ancestors.statusCode === 200, `GET /communities/.../ancestors failed: ${ancestors.raw}`)
  assertSmoke(ancestors.json?.total === 1, `Expected 1 ancestor for comm-release-readiness, got ${ancestors.json?.total}`)

  const memories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10&offset=0`)
  assertSmoke(memories.statusCode === 200, `GET /memories failed: ${memories.raw}`)
  assertSmoke(memories.json?.total === 3, `Expected 3 memories, got ${memories.json?.total}`)
  assertSmoke(
    memories.json?.memories?.map((item) => item.id).join(',') === [
      seedPayload.memory_ids[2],
      seedPayload.memory_ids[1],
      seedPayload.memory_ids[0],
    ].join(','),
    `Expected recent-first memory ordering, got ${memories.json?.memories?.map((item) => item.id).join(',')}`
  )

  const recentMemoryId = seedPayload.memory_ids[2]
  const memoryDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${recentMemoryId}`)
  assertSmoke(memoryDetail.statusCode === 200, `GET /memories/{id} failed: ${memoryDetail.raw}`)

  const memoryContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${recentMemoryId}/context`)
  assertSmoke(memoryContext.statusCode === 200, `GET /memories/{id}/context failed: ${memoryContext.raw}`)
  assertSmoke(memoryContext.json?.total_communities >= 1, `Expected recent memory to expose at least 1 context community, got ${memoryContext.json?.total_communities}`)

  const query = await requestJson(`${backendBaseUrl}/api/v1/query`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      question: SEARCH_QUESTION,
      strategy: 'graphrag',
      retrieval_mode: 'hybrid',
      top_k: 5,
      include_sources: true,
    }),
    timeoutMs: 15000,
  })
  assertSmoke(query.statusCode === 200, `POST /query failed: ${query.raw}`)
  const returnedMemoryIds = Array.isArray(query.json?.sources)
    ? [...new Set(query.json.sources.map((source) => source.memory_id).filter(Boolean))]
    : []
  assertSmoke(returnedMemoryIds.length >= 3, `Expected at least 3 unique source memory_ids, got ${returnedMemoryIds.length}`)
  assertSmoke(seedPayload.memory_ids.every((memoryId) => returnedMemoryIds.includes(memoryId)), `Expected all seeded memory_ids in query sources, got ${returnedMemoryIds.join(',')}`)
  assertSmoke(Array.isArray(query.json?.communities) && query.json.communities.length >= 2, `Expected at least 2 communities in query response, got ${query.json?.communities?.length}`)

  return {
    health,
    stats,
    communities,
    hierarchyRoot,
    ancestors,
    memories,
    memoryDetail,
    memoryContext,
    query,
    returnedMemoryIds,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statEntities).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statRelationships).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statMemories).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statCommunities).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).nth(0).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).nth(0).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=QA readiness note', { timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).nth(0).click()
    await page.waitForURL(`**/memories/${seedPayload.memory_ids[2]}`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communitiesSection).waitFor({ timeout: 30000 })

    await page.goto(`${backendBaseUrl}/search`, { waitUntil: 'networkidle' })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.form).waitFor({ timeout: 30000 })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill(SEARCH_QUESTION)
    await page.locator('button.search-strategy-button:has-text("混合检索")').click()
    const queryResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith('/api/v1/query')
        && response.request().method() === 'POST'
        && response.status() === 200
    )
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
    await queryResponse

    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.resultsGrid).waitFor({ timeout: 30000 })
    const memorySourceCount = await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memorySourceItem).count()
    const communitySourceCount = await page.getByTestId(SEARCH_SMOKE_TEST_IDS.communitySourceItem).count()
    assertSmoke(memorySourceCount >= 3, `Expected at least 3 memory source items, got ${memorySourceCount}`)
    assertSmoke(communitySourceCount >= 2, `Expected at least 2 community items, got ${communitySourceCount}`)

    await page
      .getByTestId(SEARCH_SMOKE_TEST_IDS.communitySourceItem)
      .filter({ hasText: 'Release Readiness' })
      .getByTestId(SEARCH_SMOKE_TEST_IDS.communityLink)
      .click()
    await page.waitForURL('**/communities#comm-release-readiness', { timeout: 30000 })
    await page.getByTestId('communities-detail-panel').waitFor({ timeout: 30000 })
    await page.getByTestId('communities-lineage-section').waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Level 2 Cluster 1', { timeout: 30000 })
    await page.getByTestId('communities-hierarchy-toggle').click()
    await page.getByTestId('communities-hierarchy-panel').waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Launch Owners', { timeout: 30000 })
    await page.waitForSelector('text=Release Readiness', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-30-dashboard-search-aggregate-real.png'),
      fullPage: true,
    })

    return {
      memorySourceCount,
      communitySourceCount,
      finalUrl: page.url(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-30-dashboard-search-aggregate-real-summary.txt',
    'task-30-dashboard-search-aggregate-real-summary.json',
    'task-30-dashboard-search-aggregate-real-http.json',
    'task-30-dashboard-search-aggregate-real-seed.json',
    'task-30-dashboard-search-aggregate-real.png',
    'task-30-dashboard-search-aggregate-real-error.txt',
    'task-30-dashboard-search-aggregate-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-search-aggregate-'))
  const backendPort = await findAvailablePort(Number(process.env.T30_BACKEND_PORT ?? '38300'))
  const ollamaPort = await findAvailablePort(Number(process.env.T30_OLLAMA_PORT ?? '38301'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-30-dashboard-search-aggregate-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'multi_aggregate',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-30-dashboard-search-aggregate-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, seedPayload })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, seedPayload })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:search:aggregate',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      profile: seedPayload.profile,
      memory_ids: seedPayload.memory_ids,
      community_ids: seedPayload.community_ids,
      total_entities: httpEvidence.stats.json?.total_entities,
      total_relationships: httpEvidence.stats.json?.total_relationships,
      total_memories: httpEvidence.stats.json?.total_memories,
      total_communities: httpEvidence.communities.json?.total,
      hierarchy_root_id: httpEvidence.hierarchyRoot?.id,
      ancestor_total: httpEvidence.ancestors.json?.total,
      returned_memory_ids: httpEvidence.returnedMemoryIds,
      recent_memory_id: seedPayload.memory_ids[2],
      recent_item_navigation: 'memory_detail',
      recent_memory_context_communities: httpEvidence.memoryContext.json?.total_communities,
      community_link_surface: 'result',
      browser_memory_source_count: browserEvidence.memorySourceCount,
      browser_community_source_count: browserEvidence.communitySourceCount,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-30-dashboard-search-aggregate-real.png',
      backend_log: '.sisyphus/evidence/task-30-dashboard-search-aggregate-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-30-dashboard-search-aggregate-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `profile=${summaryPayload.profile}`,
      `memory_ids=${summaryPayload.memory_ids.join(',')}`,
      `community_ids=${summaryPayload.community_ids.join(',')}`,
      `total_entities=${summaryPayload.total_entities}`,
      `total_relationships=${summaryPayload.total_relationships}`,
      `total_memories=${summaryPayload.total_memories}`,
      `total_communities=${summaryPayload.total_communities}`,
      `hierarchy_root_id=${summaryPayload.hierarchy_root_id}`,
      `ancestor_total=${summaryPayload.ancestor_total}`,
      `returned_memory_ids=${summaryPayload.returned_memory_ids.join(',')}`,
      `recent_memory_id=${summaryPayload.recent_memory_id}`,
      `recent_item_navigation=${summaryPayload.recent_item_navigation}`,
      `recent_memory_context_communities=${summaryPayload.recent_memory_context_communities}`,
      `community_link_surface=${summaryPayload.community_link_surface}`,
      `browser_memory_source_count=${summaryPayload.browser_memory_source_count}`,
      `browser_community_source_count=${summaryPayload.browser_community_source_count}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-30-dashboard-search-aggregate-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-30-dashboard-search-aggregate-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-30-dashboard-search-aggregate-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        communities: httpEvidence.communities.json,
        memories: httpEvidence.memories.json,
        memory_detail: httpEvidence.memoryDetail.json,
        memory_context: httpEvidence.memoryContext.json,
        query: httpEvidence.query.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-30-dashboard-search-aggregate-real-error.txt'),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    await stopPreviewServer(backend.child)
    await backend.flushLog()
    await fakeOllama.close()
    await rm(workspaceRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
