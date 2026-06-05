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
const TASK_ID = 't19'
const TASK_COMMAND = 'node src-react/qa/t19-settings-recovery-playwright.mjs'

async function waitForSettingsReady(page) {
  await page.waitForURL('**/settings', { timeout: 30000 })
  await page.waitForSelector('.settings-content', { state: 'visible', timeout: 30000 })
}

async function mockBaseSettingsApis(page) {
  await registerSettingsConfigRoute(page, {
    getPayload: buildSettingsConfigPayload(),
  })
  await registerHealthyRuntimeDiagnosticsRoute(page, {
    generatedAt: '2026-04-03T13:00:00Z',
  })
}

async function registerT19ScenarioRoutes(page, state) {
  await page.addInitScript(() => {
    window.URL.createObjectURL = () => 'blob:mock-export'
    window.URL.revokeObjectURL = () => {}
  })

  await page.route('**/api/v1/data/export', async (route) => {
    state.exportCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        manifest: {
          format: 'memory_graph_export',
          version: 1,
          exported_at: '2026-04-03T13:10:00Z',
          counts: { memories: 2, entities: 1, relationships: 1 }
        },
        memories: [{ id: 'mem-1' }, { id: 'mem-2' }],
        entities: [{ id: 'entity-1' }],
        relationships: [{ id: 'rel-1' }]
      })
    })
  })

  await page.route('**/api/v1/data/restore?*', async (route) => {
    state.restoreDryRunCalls += 1
    const requestUrl = new URL(route.request().url())
    if (requestUrl.searchParams.get('dry_run') !== 'true') {
      throw new Error(`Expected dry_run=true, got ${requestUrl.searchParams.toString()}`)
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        dry_run: true,
        validated: true,
        preview: { memories: 2, entities: 1, relationships: 1 },
        manifest: { present: true, version: 1, exported_at: '2026-04-03T13:10:00Z', counts: { memories: 2, entities: 1, relationships: 1 }, matches_payload: true },
        would_clear_existing: true,
        would_reindex: true,
        would_reembed: false
      })
    })
  })
}

async function runHappyPathScenario({ page, baseUrl, state }) {
  await page.goto(`${baseUrl}/settings`, { waitUntil: 'networkidle' })
  await waitForSettingsReady(page)

  await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.exportBlock}"]`, { timeout: 30000 })
  await page.click(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.exportButton}"]`)
  await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.exportResult}"]`, { timeout: 30000 })
  await page.waitForSelector('text=导出成功：', { timeout: 30000 })

  await page.setInputFiles(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.restoreDryRunFile}"]`, {
    name: 'memory-graph-export.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({ manifest: { counts: { memories: 2, entities: 1, relationships: 1 } }, memories: [{ id: 'm1' }, { id: 'm2' }], entities: [{}], relationships: [{}] }), 'utf8')
  })
  await page.click(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.restoreDryRunButton}"]`)
  await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.restoreDryRunResult}"]`, { timeout: 30000 })
  await page.waitForSelector('text="validated": true', { timeout: 30000 })

  if (state.exportCalls < 1) {
    throw new Error(`Expected at least one export call, got ${state.exportCalls}`)
  }
  if (state.restoreDryRunCalls < 1) {
    throw new Error(`Expected at least one restore dry-run call, got ${state.restoreDryRunCalls}`)
  }

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-19-settings-recovery.png'), fullPage: true })
}

async function runFailurePathScenario({ page, baseUrl }) {
  await page.goto(`${baseUrl}/settings`, { waitUntil: 'networkidle' })
  await waitForSettingsReady(page)

  await page.click(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.restoreDryRunButton}"]`)
  await page.waitForSelector('text=请先选择 restore JSON 文件', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-19-settings-recovery-error.png'), fullPage: true })
}

const T19_SCENARIOS = createSettingsSmokeScenarioRegistry([
  {
    id: 'export_and_restore_dry_run_happy_path',
    artifact: 'task-19-settings-recovery.png',
    resetAfter: { clearRoutes: false },
    execute: runHappyPathScenario,
  },
  {
    id: 'restore_dry_run_missing_file_path',
    artifact: 'task-19-settings-recovery-error.png',
    execute: runFailurePathScenario,
  },
])

export async function runT19SettingsRecoveryPlaywright() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-19-preview.log')
  const useSharedPreview = shouldSkipSettingsSmokePreview(process.env)
  const previewPort = useSharedPreview
    ? null
    : await findAvailablePort(resolvePlaywrightPreviewStartPort('t19', 'T19_PREVIEW_PORT'))
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
    notes: 'settings export and restore dry-run smoke only',
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
              exportCalls: 0,
              restoreDryRunCalls: 0,
            }
            await mockBaseSettingsApis(page)
            await registerT19ScenarioRoutes(page, state)
            await runSettingsSmokeScenarioRegistry(T19_SCENARIOS, {
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
    process.stdout.write('T19 settings recovery Playwright scenarios completed.\n')
  } catch (error) {
    evidenceResult.error = error.stack || error.message
    throw error
  } finally {
    await writeSettingsSmokeTaskEvidence(EVIDENCE_DIR, evidenceResult)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runT19SettingsRecoveryPlaywright().catch((error) => {
    process.stderr.write(`${error.stack || error.message}\n`)
    process.exitCode = 1
  })
}
