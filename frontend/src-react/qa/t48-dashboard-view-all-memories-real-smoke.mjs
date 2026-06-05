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
import { runSeedFixture } from './search-real-smoke-fixtures.mjs'
import { DASHBOARD_SMOKE_TEST_IDS } from '../pages/DashboardPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpContract({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const recentMemories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  assertSmoke(recentMemories.statusCode === 200, `GET /memories?limit=10 failed: ${recentMemories.raw}`)
  assertSmoke(recentMemories.json?.total === 19, `Expected 19 active memories behind dashboard recent list, got ${recentMemories.json?.total}`)
  assertSmoke(recentMemories.json?.memories?.length === 10, `Expected 10 recent memory items, got ${recentMemories.json?.memories?.length}`)

  const memoriesList = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=active`)
  assertSmoke(memoriesList.statusCode === 200, `GET /memories active list failed: ${memoriesList.raw}`)
  assertSmoke(memoriesList.json?.total === 19, `Expected 19 active memories in list view, got ${memoriesList.json?.total}`)
  assertSmoke(memoriesList.json?.memories?.length === 19, `Expected 19 visible active memories on first page, got ${memoriesList.json?.memories?.length}`)

  return {
    health,
    recentMemories,
    memoriesList,
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
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentSection).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.viewAllLink).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=List memory 21', { timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.viewAllLink).click()

    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.list).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.activeFilter).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=1 / 1', { timeout: 30000 })
    await page.waitForSelector('text=List memory 21', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.item).count()) === 19, 'Expected 19 active memories visible after dashboard view-all navigation')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-48-dashboard-view-all-memories-real.png'),
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
    'task-48-dashboard-view-all-memories-real-summary.txt',
    'task-48-dashboard-view-all-memories-real-summary.json',
    'task-48-dashboard-view-all-memories-real-http.json',
    'task-48-dashboard-view-all-memories-real-seed.json',
    'task-48-dashboard-view-all-memories-real.png',
    'task-48-dashboard-view-all-memories-real-error.txt',
    'task-48-dashboard-view-all-memories-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-view-all-memories-'))
  const backendPort = await findAvailablePort(Number(process.env.T48_BACKEND_PORT ?? '38480'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-48-dashboard-view-all-memories-real-seed.json')

  await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'memories_list',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-48-dashboard-view-all-memories-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:view-all:memories',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      profile: 'memories_list',
      navigation_surface: 'dashboard_view_all',
      recent_memories_total: httpEvidence.recentMemories.json?.total,
      recent_memories_visible: httpEvidence.recentMemories.json?.memories?.length,
      active_list_total: httpEvidence.memoriesList.json?.total,
      active_list_visible: httpEvidence.memoriesList.json?.memories?.length,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-48-dashboard-view-all-memories-real.png',
      backend_log: '.sisyphus/evidence/task-48-dashboard-view-all-memories-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-48-dashboard-view-all-memories-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `profile=${summaryPayload.profile}`,
      `navigation_surface=${summaryPayload.navigation_surface}`,
      `recent_memories_total=${summaryPayload.recent_memories_total}`,
      `recent_memories_visible=${summaryPayload.recent_memories_visible}`,
      `active_list_total=${summaryPayload.active_list_total}`,
      `active_list_visible=${summaryPayload.active_list_visible}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-48-dashboard-view-all-memories-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-48-dashboard-view-all-memories-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-48-dashboard-view-all-memories-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        recent_memories: httpEvidence.recentMemories.json,
        memories_list: httpEvidence.memoriesList.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-48-dashboard-view-all-memories-real-error.txt'),
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
