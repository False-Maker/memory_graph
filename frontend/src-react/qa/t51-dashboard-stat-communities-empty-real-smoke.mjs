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
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

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

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  const hierarchy = await requestJson(`${backendBaseUrl}/api/v1/communities/hierarchy`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(hierarchy.statusCode === 200, `GET /communities/hierarchy failed: ${hierarchy.raw}`)
  assertSmoke(communities.json?.total === 0, `Expected 0 communities, got ${communities.json?.total}`)
  assertSmoke(hierarchy.json?.total_communities === 0, `Expected hierarchy total_communities=0, got ${hierarchy.json?.total_communities}`)

  const recentMemories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  assertSmoke(recentMemories.statusCode === 200, `GET /memories?limit=10 failed: ${recentMemories.raw}`)
  assertSmoke(recentMemories.json?.total === 0, `Expected 0 recent memories, got ${recentMemories.json?.total}`)

  return {
    health,
    stats,
    communities,
    hierarchy,
    recentMemories,
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
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statCommunities).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无记忆，开始添加您的第一条记忆吧！', { timeout: 30000 })

    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statCommunities).click()
    await page.waitForURL(`${backendBaseUrl}/communities`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.listPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.listStatePanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无社区', { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detectButton).waitFor({ timeout: 30000 })

    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.hierarchyToggle).click()
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.hierarchyPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无层次结构数据', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-51-dashboard-stat-communities-empty-real.png'),
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
    'task-51-dashboard-stat-communities-empty-real-summary.txt',
    'task-51-dashboard-stat-communities-empty-real-summary.json',
    'task-51-dashboard-stat-communities-empty-real-http.json',
    'task-51-dashboard-stat-communities-empty-real.png',
    'task-51-dashboard-stat-communities-empty-real-error.txt',
    'task-51-dashboard-stat-communities-empty-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-stat-communities-empty-'))
  const backendPort = await findAvailablePort(Number(process.env.T51_BACKEND_PORT ?? '38510'))
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
    logFileName: 'task-51-dashboard-stat-communities-empty-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:stats:communities:empty',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      navigation_surface: 'communities->communities_empty',
      total_entities: httpEvidence.stats.json?.total_entities,
      total_relationships: httpEvidence.stats.json?.total_relationships,
      total_memories: httpEvidence.stats.json?.total_memories,
      total_communities: httpEvidence.communities.json?.total,
      hierarchy_total: httpEvidence.hierarchy.json?.total_communities,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-51-dashboard-stat-communities-empty-real.png',
      backend_log: '.sisyphus/evidence/task-51-dashboard-stat-communities-empty-real-backend.log',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `navigation_surface=${summaryPayload.navigation_surface}`,
      `total_entities=${summaryPayload.total_entities}`,
      `total_relationships=${summaryPayload.total_relationships}`,
      `total_memories=${summaryPayload.total_memories}`,
      `total_communities=${summaryPayload.total_communities}`,
      `hierarchy_total=${summaryPayload.hierarchy_total}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-51-dashboard-stat-communities-empty-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-51-dashboard-stat-communities-empty-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-51-dashboard-stat-communities-empty-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        communities: httpEvidence.communities.json,
        hierarchy: httpEvidence.hierarchy.json,
        recent_memories: httpEvidence.recentMemories.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-51-dashboard-stat-communities-empty-real-error.txt'),
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
