import { mkdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'

import {
  buildBaseUrl,
  findAvailablePort,
  resolvePlaywrightPreviewStartPort,
  runBuildWeb,
  startPreviewServer as startManagedPreviewServer,
  stopPreviewServer as stopManagedPreviewServer,
  waitForManagedPreviewServerReady,
} from './settings-playwright-runtime.mjs'
import {
  launchPlaywrightBrowser,
  writePlaywrightSmokeEvidence,
} from './playwright-smoke-runtime.mjs'
import { DASHBOARD_SMOKE_TEST_IDS } from '../pages/DashboardPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  await context.route('**/api/v1/graph/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ entities: 11, relationships: 9, memories: 7, communities: 3 })
    })
  })

  await context.route('**/api/v1/communities?limit=500', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        communities: [
          {
            id: 'comm-1',
            title: 'Rollout Cluster',
            summary: 'Release planning and rollout context',
            level: 1,
            entity_count: 3,
            rank: 0.8,
            created_at: '2026-04-03T10:00:00Z'
          }
        ],
        total: 1
      })
    })
  })

  await context.route('**/api/v1/memories?limit=10', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        memories: [
          {
            id: 'mem-1',
            title: '测试记忆',
            preview: '这是用于 Playwright happy path 的记忆内容',
            created_at: '2026-03-18T08:00:00Z'
          }
        ],
        total: 1,
        limit: 10,
        offset: 0
      })
    })
  })

  await context.route('**/api/v1/memories?limit=20&offset=0&status=active', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        memories: [
          {
            id: 'mem-1',
            content: '这是用于 Playwright happy path 的记忆内容',
            metadata: {
              source: 'manual',
              title: '测试记忆',
              tags: ['dashboard'],
              source_path: 'notes/dashboard-memory.md',
              record_type: 'note',
              timestamp: '2026-03-18T08:00:00Z',
            },
            provenance: {
              type: 'manual',
              time: '2026-03-18T08:00:00Z',
              imported_from: 'notes/dashboard-memory.md',
            },
            created_at: '2026-03-18T08:00:00Z',
          }
        ],
        total: 1,
        limit: 20,
        offset: 0,
      })
    })
  })

  await context.route('**/api/v1/memories/mem-1/context', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        entities: [{ id: 'entity-1', name: 'Alice' }],
        communities: [{ id: 'comm-1', title: 'Rollout Cluster', level: 1 }],
        total_entities: 1,
        total_communities: 1,
      })
    })
  })

  await context.route('**/api/v1/memories/mem-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'mem-1',
        content: '这是用于 Playwright happy path 的记忆内容',
        metadata: {
          source: 'manual',
          title: '测试记忆',
          tags: ['dashboard'],
          source_path: 'notes/dashboard-memory.md',
          record_type: 'note',
          timestamp: '2026-03-18T08:00:00Z',
        },
        provenance: {
          type: 'manual',
          time: '2026-03-18T08:00:00Z',
          imported_from: 'notes/dashboard-memory.md',
        },
        created_at: '2026-03-18T08:00:00Z',
      })
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/dashboard`, { waitUntil: 'networkidle' })
  await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statsGrid).waitFor({ timeout: 30000 })
  await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).waitFor({ timeout: 30000 })
  await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).click()
  await page.waitForURL('**/memories/mem-1', { timeout: 30000 })
  await page.waitForSelector('.memory-detail', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-7-dashboard.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'happy_path',
    artifact: 'task-7-dashboard.png',
    recentDetailNavigation: true,
  }
}

async function runFailurePath(browser, baseUrl) {
  const context = await browser.newContext()
  await context.route('**/api/v1/graph/stats', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'stats unavailable' })
    })
  })

  await context.route('**/api/v1/communities?limit=500', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'communities unavailable' })
    })
  })

  await context.route('**/api/v1/memories?limit=10', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'memories unavailable' })
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/dashboard`, { waitUntil: 'networkidle' })
  await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.statsError).waitFor({ timeout: 30000 })
  await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentState).waitFor({ timeout: 30000 })
  const recentItems = await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).count()
  if (recentItems !== 0) {
    throw new Error(`Expected 0 recent dashboard items on failure path, got ${recentItems}`)
  }
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-7-dashboard-error.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'failure_path',
    artifact: 'task-7-dashboard-error.png',
  }
}

async function runStaleRecentDetailPath(browser, baseUrl) {
  const context = await browser.newContext()

  await context.route('**/api/v1/graph/stats', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ entities: 11, relationships: 9, memories: 7, communities: 3 })
    })
  })

  await context.route('**/api/v1/communities?limit=500', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        communities: [
          {
            id: 'comm-1',
            title: 'Rollout Cluster',
            summary: 'Release planning and rollout context',
            level: 1,
            entity_count: 3,
            rank: 0.8,
            created_at: '2026-04-03T10:00:00Z'
          }
        ],
        total: 1
      })
    })
  })

  await context.route('**/api/v1/memories?limit=10', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        memories: [
          {
            id: 'mem-stale',
            title: '失效最近记忆',
            preview: '这条最近记忆对应的 detail 已不可用',
            created_at: '2026-03-18T08:00:00Z'
          }
        ],
        total: 1,
        limit: 10,
        offset: 0
      })
    })
  })

  await context.route('**/api/v1/memories?limit=20&offset=0&status=active', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        memories: [],
        total: 0,
        limit: 20,
        offset: 0
      })
    })
  })

  await context.route('**/api/v1/memories/mem-stale/context', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Memory not found' })
    })
  })

  await context.route('**/api/v1/memories/mem-stale', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Memory not found' })
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/dashboard`, { waitUntil: 'networkidle' })
  await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).click()
  await page.waitForURL('**/memories/mem-stale', { timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailState).waitFor({ timeout: 30000 })
  await page.waitForSelector('text=Memory not found', { timeout: 30000 })
  if (await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).count()) {
    throw new Error('Stale recent detail should not expose archive action')
  }
  if (await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).count()) {
    throw new Error('Stale recent detail should not expose delete action')
  }
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-7-dashboard-stale-detail.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'stale_recent_detail',
    artifact: 'task-7-dashboard-stale-detail.png',
    staleRecentDetail: true,
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-7-preview.log')
  await Promise.all([
    'task-7-dashboard-summary.txt',
    'task-7-dashboard-summary.json',
    'task-7-dashboard-error.txt',
    'task-7-dashboard.png',
    'task-7-dashboard-error.png',
    'task-7-dashboard-stale-detail.png',
    'task-7-preview.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t7', 'T7_PREVIEW_PORT'))
  const baseUrl = buildBaseUrl(previewPort)

  const previewServer = startManagedPreviewServer({
    frontendRoot: FRONTEND_ROOT,
    previewLogPath,
    port: previewPort,
  })
  try {
    await waitForManagedPreviewServerReady(previewServer, `${baseUrl}/`)
    const browser = await launchPlaywrightBrowser(chromium, FRONTEND_ROOT)
    try {
      const results = []
      results.push(await runHappyPath(browser, baseUrl))
      results.push(await runStaleRecentDetailPath(browser, baseUrl))
      results.push(await runFailurePath(browser, baseUrl))

      await writePlaywrightSmokeEvidence({
        evidenceDir: EVIDENCE_DIR,
        summaryFileName: 'task-7-dashboard-summary.txt',
        jsonFileName: 'task-7-dashboard-summary.json',
        generatedAt: new Date().toISOString(),
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-7-preview.log'],
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T7 dashboard Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-7-dashboard-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
