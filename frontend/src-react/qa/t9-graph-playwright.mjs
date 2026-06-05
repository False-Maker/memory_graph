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
import { registerT9GraphRoutes } from './mainline-playwright-fixtures.mjs'
import { GRAPH_SMOKE_TEST_IDS } from '../pages/GraphPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')

async function waitForGraphReady(page) {
  await page.waitForURL('**/graph', { timeout: 30000 })
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.toolbar).waitFor({ state: 'visible', timeout: 30000 })
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).waitFor({ state: 'visible', timeout: 30000 })
}

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  const state = await registerT9GraphRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/graph`, { waitUntil: 'networkidle' })
  await waitForGraphReady(page)
  await page.waitForTimeout(500)

  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('circular')
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('hierarchical')
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('clustered')
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('force')

  await page.locator(`[data-testid="${GRAPH_SMOKE_TEST_IDS.node}"]`).first().click()
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.detailPanel).waitFor({ state: 'visible', timeout: 30000 })
  await page.waitForSelector('.graph-detail-value', { state: 'visible', timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-9-graph-happy.png'), fullPage: true })

  await context.close()
  return {
    scenario: 'happy_path',
    artifact: 'task-9-graph-happy.png',
    entityCount: state.entityCount,
    relationshipCount: state.relationshipCount,
  }
}

async function runEmptyPath(browser, baseUrl) {
  const context = await browser.newContext()
  await registerT9GraphRoutes(context, { empty: true })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/graph`, { waitUntil: 'networkidle' })
  await waitForGraphReady(page)
  await page.getByTestId(GRAPH_SMOKE_TEST_IDS.emptyOverlay).waitFor({ state: 'visible', timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-9-graph-empty.png'), fullPage: true })

  await context.close()
  return {
    scenario: 'empty_path',
    artifact: 'task-9-graph-empty.png',
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-9-preview.log')
  await Promise.all([
    'task-9-graph-summary.txt',
    'task-9-graph-summary.json',
    'task-9-graph-error.txt',
    'task-9-graph-happy.png',
    'task-9-graph-empty.png',
    'task-9-preview.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t9', 'T9_PREVIEW_PORT'))
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
      const emptyResult = await runEmptyPath(browser, baseUrl)
      const results = [happyResult, emptyResult]

      await writePlaywrightSmokeEvidence({
        evidenceDir: EVIDENCE_DIR,
        summaryFileName: 'task-9-graph-summary.txt',
        jsonFileName: 'task-9-graph-summary.json',
        generatedAt: new Date().toISOString(),
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-9-preview.log'],
        extraSummaryFields: {
          happy_entities: String(happyResult.entityCount),
          happy_relationships: String(happyResult.relationshipCount),
        },
        extraJsonFields: {
          happy_entities: happyResult.entityCount,
          happy_relationships: happyResult.relationshipCount,
        },
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T9 graph Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-9-graph-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
