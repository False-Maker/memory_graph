import { mkdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'
import {
  buildBaseUrl,
  delay,
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
  registerT8SearchFailureRoutes,
  registerT8SearchHappyPathRoutes,
  registerT8SearchSourceDetailFallbackRoutes,
} from './mainline-playwright-fixtures.mjs'
import { SEARCH_SMOKE_TEST_IDS } from '../pages/SearchPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')

async function waitForSearchPageReady(page) {
  await page.waitForURL('**/search', { timeout: 30000 })
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.form).waitFor({ state: 'visible', timeout: 30000 })
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).waitFor({ state: 'visible', timeout: 30000 })
}

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  const state = await registerT8SearchHappyPathRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/search`, { waitUntil: 'networkidle' })
  await waitForSearchPageReady(page)

  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.validationError).waitFor({ timeout: 30000 })
  await delay(200)
  if (state.queryRequestCount !== 0) {
    throw new Error('Empty query should not fire API request')
  }

  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill('图谱里有哪些项目记忆？')
  await page.locator('button.search-strategy-button:has-text("本地检索")').click()
  await page.fill('input#search-top-k', '12')
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()

  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.resultsGrid).waitFor({ timeout: 30000 })
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memorySourceItem).first().waitFor({ timeout: 30000 })
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).first().click()
  await page.waitForURL('**/memories/memory-1', { timeout: 30000 })
  await page.waitForSelector('.memory-detail', { timeout: 30000 })
  await page.waitForSelector('text=关联社区', { timeout: 30000 })

  await page.goto(`${baseUrl}/search`, { waitUntil: 'networkidle' })
  await waitForSearchPageReady(page)
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill('图谱里有哪些项目记忆？')
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memorySourceItem).first().waitFor({ timeout: 30000 })
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.communityLink).first().click()
  await page.waitForURL('**/communities*', { timeout: 30000 })
  await page.waitForSelector('.community-detail-panel', { timeout: 30000 })
  await page.waitForSelector('text=社区脉络', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-8-search.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'happy_path',
    artifact: 'task-8-search.png',
    queryRequestCount: state.queryRequestCount,
  }
}

async function runFailurePath(browser, baseUrl) {
  const context = await browser.newContext()
  await registerT8SearchFailureRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/search`, { waitUntil: 'networkidle' })
  await waitForSearchPageReady(page)
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill('失败路径验证')
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.errorPanel).waitFor({ timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-8-search-error.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'failure_path',
    artifact: 'task-8-search-error.png',
  }
}

async function runSourceDetailFallbackPath(browser, baseUrl) {
  const context = await browser.newContext()
  const state = await registerT8SearchSourceDetailFallbackRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/search`, { waitUntil: 'networkidle' })
  await waitForSearchPageReady(page)
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill('图谱里有哪些缺失记忆编号的来源？')
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.resultsGrid).waitFor({ timeout: 30000 })
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailToggle).first().click()
  await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailState).waitFor({ timeout: 30000 })
  await page.waitForSelector('text=该来源未返回 memory_id，无法拉取详情。', { timeout: 30000 })
  if (await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).count()) {
    throw new Error('Missing-memory-id source should not expose memory detail link')
  }
  if ((await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceCommunityLink).count()) < 1) {
    throw new Error('Missing-memory-id source should keep a dedicated source community link')
  }
  if (state.detailRequestCount !== 0) {
    throw new Error(`Expected 0 memory detail requests, got ${state.detailRequestCount}`)
  }
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-8-search-source-detail-fallback.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'source_detail_missing_memory_id',
    artifact: 'task-8-search-source-detail-fallback.png',
    queryRequestCount: state.queryRequestCount,
    detailRequestCount: state.detailRequestCount,
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-8-preview.log')
  await Promise.all([
    'task-8-search-summary.txt',
    'task-8-search-summary.json',
    'task-8-search-error.txt',
    'task-8-search.png',
    'task-8-search-error.png',
    'task-8-search-source-detail-fallback.png',
    'task-8-preview.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t8', 'T8_PREVIEW_PORT'))
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
      const fallbackResult = await runSourceDetailFallbackPath(browser, baseUrl)
      const failureResult = await runFailurePath(browser, baseUrl)
      const results = [happyResult, fallbackResult, failureResult]

      await writePlaywrightSmokeEvidence({
        evidenceDir: EVIDENCE_DIR,
        summaryFileName: 'task-8-search-summary.txt',
        jsonFileName: 'task-8-search-summary.json',
        generatedAt: new Date().toISOString(),
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-8-preview.log'],
        extraSummaryFields: {
          happy_query_calls: String(happyResult.queryRequestCount),
          missing_memory_id_query_calls: String(fallbackResult.queryRequestCount),
          missing_memory_id_detail_requests: String(fallbackResult.detailRequestCount),
        },
        extraJsonFields: {
          happy_query_calls: happyResult.queryRequestCount,
          missing_memory_id_query_calls: fallbackResult.queryRequestCount,
          missing_memory_id_detail_requests: fallbackResult.detailRequestCount,
        },
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T8 search Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-8-search-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
