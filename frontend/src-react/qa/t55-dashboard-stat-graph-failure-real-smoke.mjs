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
import { DASHBOARD_SMOKE_TEST_IDS } from '../pages/DashboardPage.smoke-helpers.js'
import { GRAPH_SMOKE_TEST_IDS } from '../pages/GraphPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const QA_FAIL_ENV = 'MEMORY_GRAPH_QA_FAIL_GRAPH_READS'

async function verifyHttpContract({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const stats = await requestJson(`${backendBaseUrl}/api/v1/graph/stats`)
  assertSmoke(stats.statusCode === 200, `GET /graph/stats failed: ${stats.raw}`)
  assertSmoke(stats.json?.total_entities === 0, `Expected 0 entities, got ${stats.json?.total_entities}`)
  assertSmoke(stats.json?.total_relationships === 0, `Expected 0 relationships, got ${stats.json?.total_relationships}`)
  assertSmoke(stats.json?.total_memories === 0, `Expected 0 memories, got ${stats.json?.total_memories}`)

  const graphEntities = await requestJson(`${backendBaseUrl}/api/v1/graph/entities?limit=200`)
  const graphRelationships = await requestJson(`${backendBaseUrl}/api/v1/graph/relationships?limit=400`)
  assertSmoke(graphEntities.statusCode === 500, `Expected graph entities failure 500, got ${graphEntities.statusCode}`)
  assertSmoke(graphRelationships.statusCode === 500, `Expected graph relationships failure 500, got ${graphRelationships.statusCode}`)
  assertSmoke(graphEntities.json?.detail === 'QA forced failure for graph entities', `Unexpected graph entities detail: ${graphEntities.raw}`)
  assertSmoke(graphRelationships.json?.detail === 'QA forced failure for graph relationships', `Unexpected graph relationships detail: ${graphRelationships.raw}`)

  const recentMemories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  assertSmoke(recentMemories.statusCode === 200, `GET /memories?limit=10 failed: ${recentMemories.raw}`)
  assertSmoke(communities.statusCode === 200, `GET /communities?limit=500 failed: ${communities.raw}`)
  assertSmoke(recentMemories.json?.total === 0, `Expected 0 recent memories, got ${recentMemories.json?.total}`)
  assertSmoke(communities.json?.total === 0, `Expected 0 communities, got ${communities.json?.total}`)

  return {
    health,
    stats,
    graphEntities,
    graphRelationships,
    recentMemories,
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
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statEntities).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statRelationships).waitFor({ timeout: 30000 })

    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statEntities).click()
    await page.waitForURL(`${backendBaseUrl}/graph`, { timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.errorOverlay).waitFor({ timeout: 30000 })
    const firstErrorText = await page.getByTestId(GRAPH_SMOKE_TEST_IDS.errorOverlay).textContent()
    assertSmoke(
      String(firstErrorText || '').includes('QA forced failure for graph'),
      `Unexpected graph error overlay text after entities card navigation: ${firstErrorText}`
    )

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statRelationships).click()
    await page.waitForURL(`${backendBaseUrl}/graph`, { timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.errorOverlay).waitFor({ timeout: 30000 })
    const secondErrorText = await page.getByTestId(GRAPH_SMOKE_TEST_IDS.errorOverlay).textContent()
    assertSmoke(
      String(secondErrorText || '').includes('QA forced failure for graph'),
      `Unexpected graph error overlay text after relationships card navigation: ${secondErrorText}`
    )

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-55-dashboard-stat-graph-failure-real.png'),
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
    'task-55-dashboard-stat-graph-failure-real-summary.txt',
    'task-55-dashboard-stat-graph-failure-real-summary.json',
    'task-55-dashboard-stat-graph-failure-real-http.json',
    'task-55-dashboard-stat-graph-failure-real.png',
    'task-55-dashboard-stat-graph-failure-real-error.txt',
    'task-55-dashboard-stat-graph-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-stat-graph-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T55_BACKEND_PORT ?? '38550'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })

  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-55-dashboard-stat-graph-failure-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
      [QA_FAIL_ENV]: 'entities,relationships',
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:stats:graph:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      navigation_surfaces: ['entities->graph_failure', 'relationships->graph_failure'],
      total_entities: httpEvidence.stats.json?.total_entities,
      total_relationships: httpEvidence.stats.json?.total_relationships,
      total_memories: httpEvidence.stats.json?.total_memories,
      graph_entities_status: httpEvidence.graphEntities.statusCode,
      graph_relationships_status: httpEvidence.graphRelationships.statusCode,
      entities_error_detail: httpEvidence.graphEntities.json?.detail,
      relationships_error_detail: httpEvidence.graphRelationships.json?.detail,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-55-dashboard-stat-graph-failure-real.png',
      backend_log: '.sisyphus/evidence/task-55-dashboard-stat-graph-failure-real-backend.log',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `navigation_surfaces=${summaryPayload.navigation_surfaces.join(',')}`,
      `total_entities=${summaryPayload.total_entities}`,
      `total_relationships=${summaryPayload.total_relationships}`,
      `total_memories=${summaryPayload.total_memories}`,
      `graph_entities_status=${summaryPayload.graph_entities_status}`,
      `graph_relationships_status=${summaryPayload.graph_relationships_status}`,
      `entities_error_detail=${summaryPayload.entities_error_detail}`,
      `relationships_error_detail=${summaryPayload.relationships_error_detail}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-55-dashboard-stat-graph-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-55-dashboard-stat-graph-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-55-dashboard-stat-graph-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        graph_entities: {
          status_code: httpEvidence.graphEntities.statusCode,
          body: httpEvidence.graphEntities.json,
        },
        graph_relationships: {
          status_code: httpEvidence.graphRelationships.statusCode,
          body: httpEvidence.graphRelationships.json,
        },
        recent_memories: httpEvidence.recentMemories.json,
        communities: httpEvidence.communities.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-55-dashboard-stat-graph-failure-real-error.txt'),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    await stopPreviewServer(backend.child)
    await backend.flushLog()
    await rm(workspaceRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
