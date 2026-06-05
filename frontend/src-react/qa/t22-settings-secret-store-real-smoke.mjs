import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { chromium } from 'playwright'

import {
  ensureSettingsSmokeBuild,
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
import { SETTINGS_SMOKE_TEST_IDS } from '../pages/SettingsPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const BACKEND_PORT = Number(process.env.T22_BACKEND_PORT ?? '38220')
const BACKEND_BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`
const SETTINGS_PATH_ENV = 'MEMORY_GRAPH_SETTINGS_PATH'
const DISABLE_SECRET_STORE_ENV = 'MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE'

async function verifyHttpContract() {
  const health = await waitForStatus(
    `${BACKEND_BASE_URL}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const configResponse = await requestJson(`${BACKEND_BASE_URL}/api/v1/config`)
  assertSmoke(configResponse.statusCode === 200, `GET /api/v1/config failed: ${configResponse.raw}`)
  assertSmoke(configResponse.json?.secret_storage?.available === false, 'Expected secret_storage.available=false')
  assertSmoke(
    configResponse.json?.secret_storage?.storage_type === 'environment_only',
    `Expected storage_type=environment_only, got ${configResponse.json?.secret_storage?.storage_type}`
  )

  const directSaveResponse = await requestJson(`${BACKEND_BASE_URL}/api/v1/config`, {
    method: 'PUT',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      openai_api_key: 'sk-direct-secret',
    }),
  })
  assertSmoke(directSaveResponse.statusCode === 503, `Expected PUT /config 503, got ${directSaveResponse.statusCode}`)
  assertSmoke(
    directSaveResponse.json?.code === 'secure_secret_store_unavailable',
    `Expected secure_secret_store_unavailable, got ${directSaveResponse.json?.code}`
  )

  const diagnosticsResponse = await requestJson(`${BACKEND_BASE_URL}/api/v1/diagnostics/runtime`)
  assertSmoke(diagnosticsResponse.statusCode === 200, `GET /diagnostics/runtime failed: ${diagnosticsResponse.raw}`)
  assertSmoke(
    diagnosticsResponse.json?.checks?.provider?.current_provider === 'openai',
    `Expected diagnostics current provider to stay openai, got ${diagnosticsResponse.json?.checks?.provider?.current_provider}`
  )
  assertSmoke(
    diagnosticsResponse.json?.checks?.provider?.ok === false,
    `Expected diagnostics provider.ok=false without API key, got ${diagnosticsResponse.json?.checks?.provider?.ok}`
  )

  return {
    health,
    configResponse,
    directSaveResponse,
    diagnosticsResponse,
  }
}

async function runBrowserFlow() {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env)
  })
  try {
    const page = await browser.newPage()
    let putCount = 0
    page.on('request', (request) => {
      if (request.method() === 'PUT' && request.url().endsWith('/api/v1/config')) {
        putCount += 1
      }
    })

    await page.goto(`${BACKEND_BASE_URL}/settings`, { waitUntil: 'networkidle' })
    await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.secretStorageStatus}"]`, {
      timeout: 30000,
    })
    await page.waitForSelector('text=设置页不能保存新的 API Key', { timeout: 30000 })

    await page.locator('input[type="password"]').fill('sk-blocked')
    await page.click('.settings-save-btn')
    await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.globalErrorAlert}"]`, {
      timeout: 30000,
    })
    await page.waitForSelector('text=请清空 API Key 输入框后仅保存其他字段', { timeout: 30000 })
    assertSmoke(putCount === 0, `Expected blocked save to avoid PUT /config, got ${putCount}`)

    await page.locator('input[type="password"]').fill('')
    await page.locator('#settings-openai-base-url').fill('https://open.bigmodel.cn/api/coding/paas/v4')
    await page.locator('#settings-openai-model').fill('glm-4.7')
    const saveResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith('/api/v1/config')
        && response.request().method() === 'PUT'
        && response.status() === 200
    )
    await page.click('.settings-save-btn')
    await saveResponsePromise
    await page.waitForSelector('text=配置已保存，但运行诊断仍未通过', { timeout: 30000 })
    await page.waitForSelector(`[data-testid="${SETTINGS_SMOKE_TEST_IDS.diagnosticsSummary}"]`, {
      timeout: 30000,
    })
    await page.waitForSelector('text=核心运行依赖未通过诊断', { timeout: 30000 })
    assertSmoke(putCount === 1, `Expected one successful PUT /config after clearing API key, got ${putCount}`)

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-22-settings-secret-store-real.png'),
      fullPage: true,
    })

    return { putCount }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-22-settings-secret-store-real-summary.txt',
    'task-22-settings-secret-store-real-summary.json',
    'task-22-settings-secret-store-real-http.json',
    'task-22-settings-secret-store-real.png',
    'task-22-settings-secret-store-real-error.txt',
    'task-22-settings-secret-store-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await ensureSettingsSmokeBuild(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-secret-store-'))
  const configPath = await writeTempSettingsConfig(workspaceRoot)
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-22-settings-secret-store-real-backend.log',
    backendPort: BACKEND_PORT,
    extraEnv: {
      [SETTINGS_PATH_ENV]: configPath,
      [DISABLE_SECRET_STORE_ENV]: '1',
    },
  })

  try {
    const httpEvidence = await verifyHttpContract()
    const browserEvidence = await runBrowserFlow()
    const finalConfig = await requestJson(`${BACKEND_BASE_URL}/api/v1/config`)
    assertSmoke(finalConfig.statusCode === 200, `Final GET /config failed: ${finalConfig.raw}`)
    assertSmoke(
      finalConfig.json?.openai_base_url === 'https://open.bigmodel.cn/api/coding/paas/v4',
      `Expected saved openai_base_url, got ${finalConfig.json?.openai_base_url}`
    )
    assertSmoke(
      finalConfig.json?.openai_model === 'glm-4.7',
      `Expected saved openai_model, got ${finalConfig.json?.openai_model}`
    )

    const rawConfig = await readFile(configPath, 'utf8')
    assertSmoke(
      rawConfig.includes('base_url: https://open.bigmodel.cn/api/coding/paas/v4')
      || rawConfig.includes('base_url: "https://open.bigmodel.cn/api/coding/paas/v4"'),
      'Temp settings.yaml did not persist base_url'
    )
    assertSmoke(
      rawConfig.includes('model: glm-4.7')
      || rawConfig.includes('model: "glm-4.7"'),
      'Temp settings.yaml did not persist model'
    )
    assertSmoke(!rawConfig.includes('sk-direct-secret'), 'Direct secret PUT leaked into settings.yaml')
    assertSmoke(!rawConfig.includes('sk-blocked'), 'Blocked browser secret leaked into settings.yaml')

    const finalDiagnostics = await requestJson(`${BACKEND_BASE_URL}/api/v1/diagnostics/runtime`)
    assertSmoke(finalDiagnostics.statusCode === 200, `Final GET /diagnostics/runtime failed: ${finalDiagnostics.raw}`)
    assertSmoke(
      finalDiagnostics.json?.status === 'unhealthy',
      `Expected final diagnostics status=unhealthy, got ${finalDiagnostics.json?.status}`
    )
    assertSmoke(
      finalDiagnostics.json?.checks?.provider?.ok === false,
      `Expected final diagnostics provider.ok=false, got ${finalDiagnostics.json?.checks?.provider?.ok}`
    )

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:settings:secret-store',
      status: 'passed',
      backend_base_url: BACKEND_BASE_URL,
      config_path: configPath,
      secret_store_env: {
        [DISABLE_SECRET_STORE_ENV]: '1',
        [SETTINGS_PATH_ENV]: configPath,
      },
      direct_put_status: httpEvidence.directSaveResponse.statusCode,
      direct_put_code: httpEvidence.directSaveResponse.json?.code,
      initial_diagnostics_status: httpEvidence.diagnosticsResponse.json?.status,
      initial_provider_ok: httpEvidence.diagnosticsResponse.json?.checks?.provider?.ok,
      browser_put_count: browserEvidence.putCount,
      final_openai_base_url: finalConfig.json?.openai_base_url,
      final_openai_model: finalConfig.json?.openai_model,
      final_diagnostics_status: finalDiagnostics.json?.status,
      final_provider_ok: finalDiagnostics.json?.checks?.provider?.ok,
      screenshot: '.sisyphus/evidence/task-22-settings-secret-store-real.png',
      backend_log: '.sisyphus/evidence/task-22-settings-secret-store-real-backend.log',
    }
    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `direct_put_status=${summaryPayload.direct_put_status}`,
      `direct_put_code=${summaryPayload.direct_put_code}`,
      `initial_diagnostics_status=${summaryPayload.initial_diagnostics_status}`,
      `initial_provider_ok=${summaryPayload.initial_provider_ok}`,
      `browser_put_count=${summaryPayload.browser_put_count}`,
      `final_openai_base_url=${summaryPayload.final_openai_base_url}`,
      `final_openai_model=${summaryPayload.final_openai_model}`,
      `final_diagnostics_status=${summaryPayload.final_diagnostics_status}`,
      `final_provider_ok=${summaryPayload.final_provider_ok}`,
      `config_path=${summaryPayload.config_path}`,
      `disable_secret_store_env=${DISABLE_SECRET_STORE_ENV}=1`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-22-settings-secret-store-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-22-settings-secret-store-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-22-settings-secret-store-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        initial_config: httpEvidence.configResponse.json,
        direct_secret_put: httpEvidence.directSaveResponse.json,
        initial_diagnostics: httpEvidence.diagnosticsResponse.json,
        final_config: finalConfig.json,
        final_diagnostics: finalDiagnostics.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-22-settings-secret-store-real-error.txt'),
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
