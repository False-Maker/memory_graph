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
import { GRAPH_SMOKE_TEST_IDS } from '../pages/GraphPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'

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
  assertSmoke(stats.json?.total_relationships === 1, `Expected 1 relationships, got ${stats.json?.total_relationships}`)
  assertSmoke(stats.json?.total_memories === 1, `Expected 1 memories, got ${stats.json?.total_memories}`)

  const graphEntities = await requestJson(`${backendBaseUrl}/api/v1/graph/entities?limit=200`)
  const graphRelationships = await requestJson(`${backendBaseUrl}/api/v1/graph/relationships?limit=400`)
  assertSmoke(graphEntities.statusCode === 200, `GET /graph/entities failed: ${graphEntities.raw}`)
  assertSmoke(graphRelationships.statusCode === 200, `GET /graph/relationships failed: ${graphRelationships.raw}`)
  assertSmoke(graphEntities.json?.entities?.length === 2, `Expected 2 graph entities, got ${graphEntities.json?.entities?.length}`)
  assertSmoke(graphRelationships.json?.relationships?.length === 1, `Expected 1 graph relationships, got ${graphRelationships.json?.relationships?.length}`)

  const memories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=active`)
  assertSmoke(memories.statusCode === 200, `GET /memories active failed: ${memories.raw}`)
  assertSmoke(memories.json?.total === 1, `Expected 1 active memory, got ${memories.json?.total}`)
  assertSmoke(memories.json?.memories?.[0]?.id === seedPayload.memory_id, `Expected memory_id=${seedPayload.memory_id}, got ${memories.json?.memories?.[0]?.id}`)

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 1, `Expected 1 community, got ${communities.json?.total}`)
  assertSmoke(communities.json?.communities?.[0]?.id === seedPayload.community_id, `Expected community_id=${seedPayload.community_id}, got ${communities.json?.communities?.[0]?.id}`)

  return {
    health,
    stats,
    graphEntities,
    graphRelationships,
    memories,
    communities,
  }
}

async function runBrowserFlow({ backendBaseUrl }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statEntities).click()
    await page.waitForURL(`${backendBaseUrl}/graph`, { timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.node).first().waitFor({ timeout: 30000 })

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statRelationships).click()
    await page.waitForURL(`${backendBaseUrl}/graph`, { timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statMemories).click()
    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.list).waitFor({ timeout: 30000 })

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statCommunities).click()
    await page.waitForURL(`${backendBaseUrl}/communities`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.listPanel).waitFor({ timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-49-dashboard-stat-navigation-real.png'),
      fullPage: true,
    })

    return {
      finalUrl: page.url(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-49-dashboard-stat-navigation-real-summary.txt',
    'task-49-dashboard-stat-navigation-real-summary.json',
    'task-49-dashboard-stat-navigation-real-http.json',
    'task-49-dashboard-stat-navigation-real-seed.json',
    'task-49-dashboard-stat-navigation-real.png',
    'task-49-dashboard-stat-navigation-real-error.txt',
    'task-49-dashboard-stat-navigation-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-stat-navigation-'))
  const backendPort = await findAvailablePort(Number(process.env.T49_BACKEND_PORT ?? '38490'))
  const ollamaPort = await findAvailablePort(Number(process.env.T49_OLLAMA_PORT ?? '38491'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-49-dashboard-stat-navigation-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-49-dashboard-stat-navigation-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, seedPayload })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:stats-navigation',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      navigation_surfaces: [
        'entities->graph',
        'relationships->graph',
        'memories->memories',
        'communities->communities',
      ],
      total_entities: httpEvidence.stats.json?.total_entities,
      total_relationships: httpEvidence.stats.json?.total_relationships,
      total_memories: httpEvidence.stats.json?.total_memories,
      total_communities: httpEvidence.communities.json?.total,
      graph_entity_count: httpEvidence.graphEntities.json?.entities?.length,
      graph_relationship_count: httpEvidence.graphRelationships.json?.relationships?.length,
      memories_list_total: httpEvidence.memories.json?.total,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-49-dashboard-stat-navigation-real.png',
      backend_log: '.sisyphus/evidence/task-49-dashboard-stat-navigation-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-49-dashboard-stat-navigation-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `navigation_surfaces=${summaryPayload.navigation_surfaces.join(',')}`,
      `total_entities=${summaryPayload.total_entities}`,
      `total_relationships=${summaryPayload.total_relationships}`,
      `total_memories=${summaryPayload.total_memories}`,
      `total_communities=${summaryPayload.total_communities}`,
      `graph_entity_count=${summaryPayload.graph_entity_count}`,
      `graph_relationship_count=${summaryPayload.graph_relationship_count}`,
      `memories_list_total=${summaryPayload.memories_list_total}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-49-dashboard-stat-navigation-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-49-dashboard-stat-navigation-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-49-dashboard-stat-navigation-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        graph_entities: httpEvidence.graphEntities.json,
        graph_relationships: httpEvidence.graphRelationships.json,
        memories: httpEvidence.memories.json,
        communities: httpEvidence.communities.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-49-dashboard-stat-navigation-real-error.txt'),
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
