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
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const QA_FAIL_ENV = 'MEMORY_GRAPH_QA_FAIL_MEMORIES_LIST'

async function verifyHttpContract({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const stats = await requestJson(`${backendBaseUrl}/api/v1/graph/stats`)
  assertSmoke(stats.statusCode === 200, `GET /graph/stats failed: ${stats.raw}`)
  assertSmoke(stats.json?.total_memories === 0, `Expected 0 memories, got ${stats.json?.total_memories}`)

  const memoriesRecent = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  const memoriesList = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=active`)
  assertSmoke(memoriesRecent.statusCode === 500, `Expected recent memories failure 500, got ${memoriesRecent.statusCode}`)
  assertSmoke(memoriesList.statusCode === 500, `Expected memories list failure 500, got ${memoriesList.statusCode}`)
  assertSmoke(memoriesRecent.json?.detail === 'QA forced failure for memories list', `Unexpected recent memories detail: ${memoriesRecent.raw}`)
  assertSmoke(memoriesList.json?.detail === 'QA forced failure for memories list', `Unexpected memories list detail: ${memoriesList.raw}`)

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  assertSmoke(communities.statusCode === 200, `GET /communities?limit=500 failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 0, `Expected 0 communities, got ${communities.json?.total}`)

  return {
    health,
    stats,
    memoriesRecent,
    memoriesList,
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
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statMemories).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=QA forced failure for memories list', { timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statMemories).click()

    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.statePanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=QA forced failure for memories list', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.list).count()) === 0, 'Failure path should not render memories list')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-53-dashboard-stat-memories-failure-real.png'),
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
    'task-53-dashboard-stat-memories-failure-real-summary.txt',
    'task-53-dashboard-stat-memories-failure-real-summary.json',
    'task-53-dashboard-stat-memories-failure-real-http.json',
    'task-53-dashboard-stat-memories-failure-real.png',
    'task-53-dashboard-stat-memories-failure-real-error.txt',
    'task-53-dashboard-stat-memories-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-stat-memories-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T53_BACKEND_PORT ?? '38530'))
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
    logFileName: 'task-53-dashboard-stat-memories-failure-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
      [QA_FAIL_ENV]: '1',
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:stats:memories:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      navigation_surface: 'memories->memories_failure',
      total_memories: httpEvidence.stats.json?.total_memories,
      recent_memories_status: httpEvidence.memoriesRecent.statusCode,
      active_list_status: httpEvidence.memoriesList.statusCode,
      error_detail: httpEvidence.memoriesList.json?.detail,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-53-dashboard-stat-memories-failure-real.png',
      backend_log: '.sisyphus/evidence/task-53-dashboard-stat-memories-failure-real-backend.log',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `navigation_surface=${summaryPayload.navigation_surface}`,
      `total_memories=${summaryPayload.total_memories}`,
      `recent_memories_status=${summaryPayload.recent_memories_status}`,
      `active_list_status=${summaryPayload.active_list_status}`,
      `error_detail=${summaryPayload.error_detail}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-53-dashboard-stat-memories-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-53-dashboard-stat-memories-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-53-dashboard-stat-memories-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        recent_memories: {
          status_code: httpEvidence.memoriesRecent.statusCode,
          body: httpEvidence.memoriesRecent.json,
        },
        memories_list: {
          status_code: httpEvidence.memoriesList.statusCode,
          body: httpEvidence.memoriesList.json,
        },
        communities: httpEvidence.communities.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-53-dashboard-stat-memories-failure-real-error.txt'),
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
