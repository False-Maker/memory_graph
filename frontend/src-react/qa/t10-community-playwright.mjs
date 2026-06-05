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
import { registerT10CommunityRoutes } from './mainline-playwright-fixtures.mjs'
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')
const REQUIRE_DEEPLINK = ['1', 'true', 'yes', 'on'].includes(
  String(process.env.T10_REQUIRE_DEEPLINK || '').trim().toLowerCase()
)

async function waitForCommunitiesReady(page) {
  await page.waitForURL('**/communities*', { timeout: 30000 })
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.toolbar).waitFor({ state: 'visible', timeout: 30000 })
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detectButton).waitFor({ state: 'visible', timeout: 30000 })
}

async function assertDetailSections(page) {
  const sectionCount = await page.locator('.community-detail-section').count()
  if (sectionCount > 0) {
    await page.waitForSelector('.community-detail-list, .community-detail-empty', { timeout: 30000 })
    return
  }
  await page.waitForSelector('.community-detail-panel', { state: 'visible', timeout: 30000 })
}

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  const state = await registerT10CommunityRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/communities#c-root`, { waitUntil: 'networkidle' })
  await waitForCommunitiesReady(page)
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.card).first().waitFor({ state: 'visible', timeout: 30000 })

  const deepLinkResolved = await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).isVisible().catch(() => false)
  if (!deepLinkResolved && REQUIRE_DEEPLINK) {
    throw new Error('Deep-link expected but detail panel is not visible on initial load')
  }
  if (!deepLinkResolved) {
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.card).first().click()
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ state: 'visible', timeout: 30000 })
  }

  await assertDetailSections(page)
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.summarizeButton).waitFor({ state: 'visible', timeout: 30000 })
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.summarizeButton).click()
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForSelector('text=新的摘要：AI 社区涵盖推理、检索增强和应用实践。', { timeout: 30000 })

  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detectButton).click()
  await page.waitForSelector('text=社区检测已触发，正在刷新数据...', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-10-community-detect.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'happy_path',
    artifact: 'task-10-community-detect.png',
    deepLinkResolved,
    detectCount: state.detectCount,
  }
}

async function runFailurePath(browser, baseUrl) {
  const context = await browser.newContext()
  await registerT10CommunityRoutes(context, { summaryFailure: true })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/communities`, { waitUntil: 'networkidle' })
  await waitForCommunitiesReady(page)

  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.card).first().click()
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ state: 'visible', timeout: 30000 })
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.summarizeButton).click()
  await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForSelector('text=summary service unavailable', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-10-community-error.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'failure_path',
    artifact: 'task-10-community-error.png',
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-10-preview.log')
  await Promise.all([
    'task-10-community-summary.txt',
    'task-10-community-summary.json',
    'task-10-community-run-error.txt',
    'task-10-community-detect.png',
    'task-10-community-error.png',
    'task-10-preview.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t10', 'T10_PREVIEW_PORT'))
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
        summaryFileName: 'task-10-community-summary.txt',
        jsonFileName: 'task-10-community-summary.json',
        generatedAt: new Date().toISOString(),
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-10-preview.log'],
        extraSummaryFields: {
          detect_calls: String(happyResult.detectCount),
          deep_link_resolved: String(happyResult.deepLinkResolved),
        },
        extraJsonFields: {
          detect_calls: happyResult.detectCount,
          deep_link_resolved: happyResult.deepLinkResolved,
        },
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T10 communities Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-10-community-run-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
