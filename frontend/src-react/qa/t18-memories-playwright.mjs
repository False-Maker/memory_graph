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
import {
  registerT18MemoriesFailureRoutes,
  registerT18MemoriesHappyPathRoutes,
} from './mainline-playwright-fixtures.mjs'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')

async function waitForMemoriesReady(page) {
  await page.waitForURL('**/memories*', { timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.page).waitFor({ state: 'visible', timeout: 30000 })
}

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  const state = await registerT18MemoriesHappyPathRoutes(context)

  await context.addInitScript(() => {
    window.confirm = () => true
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/memories`, { waitUntil: 'networkidle' })
  await waitForMemoriesReady(page)

  const firstItem = page.locator(`[data-testid="${MEMORIES_SMOKE_TEST_IDS.item}"][data-memory-id="mem-1"]`)
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.item).first().waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForSelector('text=Memory One', { timeout: 30000 })
  await page.waitForSelector('text=Memory Two', { timeout: 30000 })
  await firstItem.getByTestId(MEMORIES_SMOKE_TEST_IDS.itemArchiveButton).click()
  await page.waitForSelector('text=记忆已归档', { timeout: 30000 })
  if (state.archiveCalls < 1) {
    throw new Error(`Expected at least one archive call, got ${state.archiveCalls}`)
  }
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.archivedFilter).click()
  await page.waitForSelector('text=Archived', { timeout: 30000 })
  await page.waitForSelector('text=Memory Three', { timeout: 30000 })
  await firstItem.getByTestId(MEMORIES_SMOKE_TEST_IDS.itemArchiveButton).click()
  await page.waitForSelector('text=记忆已取消归档', { timeout: 30000 })
  if (state.unarchiveCalls < 1) {
    throw new Error(`Expected at least one unarchive call, got ${state.unarchiveCalls}`)
  }
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.activeFilter).click()
  await page.waitForSelector('text=Memory One', { timeout: 30000 })
  await firstItem.getByTestId(MEMORIES_SMOKE_TEST_IDS.itemViewButton).click()
  await page.waitForURL('**/memories/mem-1', { timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForSelector('text=来源摘要', { timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communitiesSection).waitFor({ timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.entitiesSection).waitFor({ timeout: 30000 })
  await page.waitForSelector('a:has-text("跳转到社区详情")', { timeout: 30000 })
  await page.click('a:has-text("跳转到社区详情")')
  await page.waitForURL('**/communities*', { timeout: 30000 })
  await page.waitForSelector('.community-detail-panel', { timeout: 30000 })
  await page.waitForSelector('text=社区脉络', { timeout: 30000 })

  await page.goto(`${baseUrl}/memories/mem-1`, { waitUntil: 'networkidle' })
  await page.waitForURL('**/memories/mem-1', { timeout: 30000 })
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ state: 'visible', timeout: 30000 })

  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).click()
  await page.waitForURL('**/memories', { timeout: 30000 })
  if (state.deleteCalls < 1) {
    throw new Error(`Expected at least one delete call, got ${state.deleteCalls}`)
  }
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-18-memories-happy.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'happy_path',
    artifact: 'task-18-memories-happy.png',
    archiveCalls: state.archiveCalls,
    unarchiveCalls: state.unarchiveCalls,
    deleteCalls: state.deleteCalls,
  }
}

async function runFailurePath(browser, baseUrl) {
  const context = await browser.newContext()
  await registerT18MemoriesFailureRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/memories`, { waitUntil: 'networkidle' })
  await waitForMemoriesReady(page)
  await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.statePanel).waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForSelector('text=memories unavailable', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-18-memories-error.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'failure_path',
    artifact: 'task-18-memories-error.png',
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-18-preview.log')
  await Promise.all([
    'task-18-memories-summary.txt',
    'task-18-memories-summary.json',
    'task-18-memories-run-error.txt',
    'task-18-memories-happy.png',
    'task-18-memories-error.png',
    'task-18-preview.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t18', 'T18_PREVIEW_PORT'))
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
      const happyResult = await runHappyPath(browser, baseUrl)
      const failureResult = await runFailurePath(browser, baseUrl)
      const results = [happyResult, failureResult]

      await writePlaywrightSmokeEvidence({
        evidenceDir: EVIDENCE_DIR,
        summaryFileName: 'task-18-memories-summary.txt',
        jsonFileName: 'task-18-memories-summary.json',
        generatedAt: new Date().toISOString(),
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-18-preview.log'],
        extraSummaryFields: {
          archive_calls: String(happyResult.archiveCalls),
          unarchive_calls: String(happyResult.unarchiveCalls),
          delete_calls: String(happyResult.deleteCalls),
        },
        extraJsonFields: {
          archive_calls: happyResult.archiveCalls,
          unarchive_calls: happyResult.unarchiveCalls,
          delete_calls: happyResult.deleteCalls,
        },
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T18 memories Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-18-memories-run-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
