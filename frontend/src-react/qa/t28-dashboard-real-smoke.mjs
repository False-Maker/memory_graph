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

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpContract({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const stats = await requestJson(`${backendBaseUrl}/api/v1/graph/stats`)
  assertSmoke(stats.statusCode === 200, `GET /graph/stats failed: ${stats.raw}`)
  assertSmoke(stats.json?.total_entities === 2, `Expected 2 entities, got ${stats.json?.total_entities}`)
  assertSmoke(stats.json?.total_relationships === 1, `Expected 1 relationship, got ${stats.json?.total_relationships}`)
  assertSmoke(stats.json?.total_memories === 1, `Expected 1 memory, got ${stats.json?.total_memories}`)

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 1, `Expected 1 community, got ${communities.json?.total}`)

  const memories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  assertSmoke(memories.statusCode === 200, `GET /memories failed: ${memories.raw}`)
  assertSmoke(memories.json?.total === 1, `Expected 1 recent memory, got ${memories.json?.total}`)
  assertSmoke(memories.json?.memories?.[0]?.id === seedPayload.memory_id, `Expected recent memory_id=${seedPayload.memory_id}, got ${memories.json?.memories?.[0]?.id}`)

  const memoryDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
  assertSmoke(memoryDetail.statusCode === 200, `GET /memories/{id} failed: ${memoryDetail.raw}`)

  const memoryContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
  assertSmoke(memoryContext.statusCode === 200, `GET /memories/{id}/context failed: ${memoryContext.raw}`)
  assertSmoke(memoryContext.json?.total_communities === 1, `Expected 1 context community, got ${memoryContext.json?.total_communities}`)

  return { health, stats, communities, memories, memoryDetail, memoryContext }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })

    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statsGrid).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statEntities).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statRelationships).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statMemories).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statCommunities).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentSection).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).waitFor({ timeout: 30000 })

    assertSmoke((await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).count()) === 1, 'Expected exactly one recent item')
    await page.waitForSelector('text=Launch ownership note', { timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).click()
    await page.waitForURL(`**/memories/${seedPayload.memory_id}`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communitiesSection).waitFor({ timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-28-dashboard-real.png'),
      fullPage: true,
    })

    return { finalUrl: page.url() }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-28-dashboard-real-summary.txt',
    'task-28-dashboard-real-summary.json',
    'task-28-dashboard-real-http.json',
    'task-28-dashboard-real-seed.json',
    'task-28-dashboard-real.png',
    'task-28-dashboard-real-error.txt',
    'task-28-dashboard-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-real-'))
  const backendPort = await findAvailablePort(Number(process.env.T28_BACKEND_PORT ?? '38280'))
  const ollamaPort = await findAvailablePort(Number(process.env.T28_OLLAMA_PORT ?? '38281'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-28-dashboard-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'basic',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-28-dashboard-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      total_entities: httpEvidence.stats.json?.total_entities,
      total_relationships: httpEvidence.stats.json?.total_relationships,
      total_memories: httpEvidence.stats.json?.total_memories,
      total_communities: httpEvidence.communities.json?.total,
      recent_memories_total: httpEvidence.memories.json?.total,
      recent_memory_id: seedPayload.memory_id,
      recent_item_navigation: 'memory_detail',
      detail_context_communities: httpEvidence.memoryContext.json?.total_communities,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-28-dashboard-real.png',
      backend_log: '.sisyphus/evidence/task-28-dashboard-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-28-dashboard-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `total_entities=${summaryPayload.total_entities}`,
      `total_relationships=${summaryPayload.total_relationships}`,
      `total_memories=${summaryPayload.total_memories}`,
      `total_communities=${summaryPayload.total_communities}`,
      `recent_memories_total=${summaryPayload.recent_memories_total}`,
      `recent_memory_id=${summaryPayload.recent_memory_id}`,
      `recent_item_navigation=${summaryPayload.recent_item_navigation}`,
      `detail_context_communities=${summaryPayload.detail_context_communities}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-28-dashboard-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-28-dashboard-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-28-dashboard-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        communities: httpEvidence.communities.json,
        memories: httpEvidence.memories.json,
        memory_detail: httpEvidence.memoryDetail.json,
        memory_context: httpEvidence.memoryContext.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-28-dashboard-real-error.txt'),
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
