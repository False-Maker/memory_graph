import { mkdir } from 'node:fs/promises'
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { chromium } from 'playwright'

import {
  applyBrowserLibEnv,
  buildBaseUrl,
  buildBrowserLibDir,
  ensureSettingsSmokeBuild,
  findAvailablePort,
  openSettingsSmokeBrowser,
  resetSettingsSmokePage,
  resolvePlaywrightPreviewStartPort,
  resolveSettingsSmokeBaseUrl,
  shouldSkipSettingsSmokePreview,
  startPreviewServer,
  stopPreviewServer,
  waitForManagedPreviewServerReady,
  withSettingsSmokeContext,
  withSettingsSmokePage,
  writeSharedSettingsSmokePreviewLog,
} from './settings-playwright-runtime.mjs'
import {
  createSettingsSmokeScenarioRegistry,
  runSettingsSmokeScenarioRegistry,
} from './settings-playwright-scenarios.mjs'
import {
  buildSettingsConfigPayload,
  registerHealthyRuntimeDiagnosticsRoute,
  registerSettingsConfigRoute,
} from './settings-playwright-mocks.mjs'
import { writeSettingsSmokeTaskEvidence } from './t21-settings-smoke-matrix-helpers.mjs'
import { SETTINGS_SMOKE_TEST_IDS } from '../pages/SettingsPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')
const TASK_ID = 't20'
const TASK_COMMAND = 'node src-react/qa/t20-settings-reindex-playwright.mjs'

async function waitForSettingsReady(page) {
  await page.waitForURL('**/settings', { timeout: 30000 })
  await page.waitForSelector('.settings-content', { state: 'visible', timeout: 30000 })
}

async function mockBaseSettingsApis(page) {
  await registerSettingsConfigRoute(page, {
    getPayload: buildSettingsConfigPayload(),
  })
  await registerHealthyRuntimeDiagnosticsRoute(page, {
    generatedAt: '2026-04-03T13:30:00Z',
  })
}

async function registerT20ScenarioRoutes(page, state) {
  await page.route('**/api/v1/data/reindex?*', async (route) => {
    if (state.mode === 'success') {
      state.successCalls += 1
    } else {
      state.failureCalls += 1
    }
    const requestUrl = new URL(route.request().url())
    if (state.mode === 'success') {
      if (requestUrl.searchParams.get('reembed') !== 'true') {
        throw new Error(`Expected reembed=true, got ${requestUrl.searchParams.toString()}`)
      }
      if (requestUrl.searchParams.get('batch_size') !== '16') {
        throw new Error(`Expected batch_size=16, got ${requestUrl.searchParams.toString()}`)
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          result: { documents: 12, reembedded: 12, indexed: 12 },
          state: { indexed_documents: 12, stored_documents: 12, dimension_mismatch: false }
        })
      })
      return
    }

    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'reindex service unavailable' })
    })
  })
}

async function runHappyPathScenario({ page, baseUrl, state }) {
  await page.goto(`${baseUrl}/settings`, { waitUntil: 'networkidle' })
  await waitForSettingsReady(page)

  await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.reindexBlock}"]`, { timeout: 30000 })
  await page.locator(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.reindexBlock}"] input[type="checkbox"]`).check()
  await page.locator(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.reindexBlock}"] input[type="number"]`).fill('16')
  await page.click(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.reindexButton}"]`)
  await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.reindexResult}"]`, { timeout: 30000 })
  await page.waitForSelector('text="indexed_documents": 12', { timeout: 30000 })

  if (state.successCalls < 1) {
    throw new Error(`Expected at least one reindex call, got ${state.successCalls}`)
  }

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-20-settings-reindex.png'), fullPage: true })
}

async function runFailurePathScenario({ page, baseUrl, state }) {
  await page.goto(`${baseUrl}/settings`, { waitUntil: 'networkidle' })
  await waitForSettingsReady(page)

  await page.click(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.reindexButton}"]`)
  await page.waitForSelector('text=reindex service unavailable', { timeout: 30000 })
  if (state.failureCalls < 1) {
    throw new Error(`Expected at least one failure reindex call, got ${state.failureCalls}`)
  }
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-20-settings-reindex-error.png'), fullPage: true })
}

const T20_SCENARIOS = createSettingsSmokeScenarioRegistry([
  {
    id: 'reindex_happy_path',
    artifact: 'task-20-settings-reindex.png',
    resetAfter: { clearRoutes: false },
    execute: runHappyPathScenario,
  },
  {
    id: 'reindex_failure_path',
    artifact: 'task-20-settings-reindex-error.png',
    prepare: ({ state }) => {
      state.mode = 'failure'
    },
    execute: runFailurePathScenario,
  },
])

export async function runT20SettingsReindexPlaywright() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-20-preview.log')
  const useSharedPreview = shouldSkipSettingsSmokePreview(process.env)
  const previewPort = useSharedPreview
    ? null
    : await findAvailablePort(resolvePlaywrightPreviewStartPort('t20', 'T20_PREVIEW_PORT'))
  const baseUrl = useSharedPreview
    ? resolveSettingsSmokeBaseUrl(0, process.env)
    : buildBaseUrl(previewPort)
  const completedScenarios = []
  const artifacts = []
  const evidenceResult = {
    taskId: TASK_ID,
    generatedAt: new Date().toISOString(),
    command: TASK_COMMAND,
    status: 'failed',
    exitCode: 1,
    scenarios: completedScenarios,
    artifacts,
    notes: 'settings reindex smoke with happy path and error path',
  }

  try {
    await ensureSettingsSmokeBuild(FRONTEND_ROOT)

    const previewServer = useSharedPreview
      ? null
      : startPreviewServer({
          frontendRoot: FRONTEND_ROOT,
          previewLogPath,
          port: previewPort
        })
    try {
      if (useSharedPreview) {
        await writeSharedSettingsSmokePreviewLog(previewLogPath, process.env)
      } else {
        await waitForManagedPreviewServerReady(previewServer, `${baseUrl}/`)
      }

      const browserLibDir = buildBrowserLibDir(FRONTEND_ROOT)
      if (fs.existsSync(browserLibDir)) {
        Object.assign(process.env, applyBrowserLibEnv(browserLibDir, process.env))
      }

      const browser = await openSettingsSmokeBrowser(chromium, process.env)
      try {
        await withSettingsSmokeContext(browser, async (context) => {
          await withSettingsSmokePage(context, async (page) => {
            const state = {
              mode: 'success',
              successCalls: 0,
              failureCalls: 0,
            }
            await mockBaseSettingsApis(page)
            await registerT20ScenarioRoutes(page, state)
            await runSettingsSmokeScenarioRegistry(T20_SCENARIOS, {
              page,
              baseUrl,
              state,
              completedScenarios,
              artifacts,
              resetScenarioTarget: (options) => resetSettingsSmokePage(page, options),
            })
          })
        })
      } finally {
        await browser.close()
      }
    } finally {
      if (previewServer) {
        await stopPreviewServer(previewServer.child)
        await previewServer.flushLog()
      }
      artifacts.push(path.basename(previewLogPath))
    }

    evidenceResult.status = 'passed'
    evidenceResult.exitCode = 0
    evidenceResult.generatedAt = new Date().toISOString()
    process.stdout.write('T20 settings reindex Playwright scenarios completed.\n')
  } catch (error) {
    evidenceResult.error = error.stack || error.message
    throw error
  } finally {
    await writeSettingsSmokeTaskEvidence(EVIDENCE_DIR, evidenceResult)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runT20SettingsReindexPlaywright().catch((error) => {
    process.stderr.write(`${error.stack || error.message}\n`)
    process.exitCode = 1
  })
}
