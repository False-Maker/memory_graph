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
  resolvePlaywrightPreviewStartPort,
  resolveSettingsSmokeBaseUrl,
  shouldSkipSettingsSmokePreview,
  startPreviewServer,
  stopPreviewServer,
  withSettingsSmokeContext,
  waitForManagedPreviewServerReady,
  writeSharedSettingsSmokePreviewLog,
} from './settings-playwright-runtime.mjs'
import { runSettingsSmokeScenarioRegistry } from './settings-playwright-scenarios.mjs'
import { T12_SCENARIOS } from './t12-settings-playwright-scenarios.mjs'
import { writeSettingsSmokeTaskEvidence } from './t21-settings-smoke-matrix-helpers.mjs'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')
const TASK_ID = 't12'
const TASK_COMMAND = 'node src-react/qa/t12-settings-playwright.mjs'

export async function runT12SettingsPlaywright() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-12-preview.log')
  const useSharedPreview = shouldSkipSettingsSmokePreview(process.env)
  const previewPort = useSharedPreview
    ? null
    : await findAvailablePort(resolvePlaywrightPreviewStartPort('t12', 'T12_PREVIEW_PORT'))
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
    notes: 'settings save, diagnostics, provider switching, and visualization storage smoke',
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
          await runSettingsSmokeScenarioRegistry(T12_SCENARIOS, {
            context,
            baseUrl,
            evidenceDir: EVIDENCE_DIR,
            completedScenarios,
            artifacts,
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
    process.stdout.write('T12 settings Playwright scenarios completed.\n')
  } catch (error) {
    evidenceResult.error = error.stack || error.message
    throw error
  } finally {
    await writeSettingsSmokeTaskEvidence(EVIDENCE_DIR, evidenceResult)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runT12SettingsPlaywright().catch((error) => {
    process.stderr.write(`${error.stack || error.message}\n`)
    process.exitCode = 1
  })
}
