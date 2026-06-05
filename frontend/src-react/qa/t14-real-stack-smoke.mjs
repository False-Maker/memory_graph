import { spawn } from 'node:child_process'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import fs from 'node:fs'
import http from 'node:http'
import https from 'node:https'
import path from 'node:path'
import { chromium } from 'playwright'
import {
  assertCurrentProviderConnection,
  buildConfigPayloadFromSettings,
  buildConnectionSummary,
  buildOverrideConfigPayload,
  configPayloadEquals,
  getProviderFieldExpectation,
  parseRequireFlag,
  resolveCurrentProvider
} from './t14-real-stack-smoke-helpers.mjs'
import { buildInboxSmokeSummaryLines } from './t14-real-stack-smoke-inbox-helpers.mjs'
import { launchPlaywrightBrowser } from './playwright-smoke-runtime.mjs'

const REPO_ROOT = path.resolve(process.cwd(), '..')
const FRONTEND_ROOT = path.resolve(process.cwd())
const SIDECAR_ROOT = path.resolve(FRONTEND_ROOT, 'api')
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')
const BACKEND_PORT = process.env.T14_BACKEND_PORT ?? '38000'
const SIDECAR_PORT = process.env.T14_SIDECAR_PORT ?? '38001'
const EXPECTED_PROVIDER = process.env.T14_EXPECT_PROVIDER?.trim() || null
const REQUIRE_CURRENT_PROVIDER_SUCCESS = parseRequireFlag(process.env.T14_REQUIRE_CURRENT_PROVIDER_SUCCESS)
const BACKEND_BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`
const SIDECAR_BASE_URL = `http://127.0.0.1:${SIDECAR_PORT}`

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function assertSmoke(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

function resolveCommand(command) {
  if (process.platform === 'win32' && command === 'npm') {
    return 'npm.cmd'
  }
  return command
}

function requestJson(url, options = {}) {
  const { body, timeoutMs = 5000, ...requestOptions } = options
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http
    const request = client.request(url, requestOptions, (response) => {
      const chunks = []
      response.on('data', (chunk) => chunks.push(chunk))
      response.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8')
        let json = null
        try {
          json = raw ? JSON.parse(raw) : null
        } catch {
          json = null
        }
        resolve({
          statusCode: response.statusCode ?? 0,
          headers: response.headers,
          raw,
          json
        })
      })
    })
    request.on('error', reject)
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`timeout requesting ${url}`))
    })
    if (body) {
      request.write(body)
    }
    request.end()
  })
}

async function waitForStatus(url, predicate, timeoutMs = 30000) {
  const start = Date.now()
  let lastError = null

  while (Date.now() - start < timeoutMs) {
    try {
      const response = await requestJson(url)
      if (predicate(response)) {
        return response
      }
      lastError = new Error(`unexpected status ${response.statusCode}: ${response.raw}`)
    } catch (error) {
      lastError = error
    }
    await delay(500)
  }

  throw lastError || new Error(`Timed out waiting for ${url}`)
}

function formatHttpFailure(label, response) {
  const raw = typeof response?.raw === 'string' ? response.raw.trim() : ''
  return `${label} failed: HTTP ${response?.statusCode ?? 0}${raw ? ` ${raw}` : ''}`
}

async function runCommand(cwd, command, args, logName) {
  const logPath = path.join(EVIDENCE_DIR, logName)

  await new Promise((resolve, reject) => {
    const child = spawn(resolveCommand(command), args, {
      cwd,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false
    })

    const chunks = []
    child.stdout.on('data', (chunk) => chunks.push(String(chunk)))
    child.stderr.on('data', (chunk) => chunks.push(String(chunk)))

    child.on('exit', async (code) => {
      await writeFile(logPath, chunks.join(''), 'utf8')
      if (code === 0) {
        resolve()
        return
      }
      reject(new Error(`${command} ${args.join(' ')} failed with exit code ${code}`))
    })

    child.on('error', reject)
  })
}

function startService({ cwd, command, args, env, logName }) {
  const logPath = path.join(EVIDENCE_DIR, logName)
  const child = spawn(resolveCommand(command), args, {
    cwd,
    env: { ...process.env, ...env },
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: false
  })

  const chunks = []
  child.stdout.on('data', (chunk) => chunks.push(String(chunk)))
  child.stderr.on('data', (chunk) => chunks.push(String(chunk)))

  return {
    child,
    async flushLog() {
      await writeFile(logPath, chunks.join(''), 'utf8')
    }
  }
}

async function waitForProcessExit(child, timeoutMs = 5000) {
  if (!child || child.exitCode !== null) {
    return
  }

  await new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

async function stopService(service) {
  if (!service?.child || service.child.killed) {
    return
  }

  if (process.platform === 'win32') {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/pid', String(service.child.pid), '/t', '/f'], {
        stdio: 'ignore',
        shell: false
      })
      killer.on('exit', () => resolve())
      killer.on('error', () => resolve())
    })
    await waitForProcessExit(service.child)
  } else {
    service.child.kill('SIGTERM')
    await waitForProcessExit(service.child)
    if (service.child.exitCode === null) {
      service.child.kill('SIGKILL')
      await waitForProcessExit(service.child, 1000)
    }
  }

  await service.flushLog()
}

async function assertProviderSpecificSettings(page, provider) {
  await page.waitForSelector('#settings-llm-provider', { state: 'visible', timeout: 30000 })
  const selectedProvider = await page.locator('#settings-llm-provider').inputValue()
  assertSmoke(
    selectedProvider === provider,
    `Settings page selected provider mismatch: expected ${provider}, got ${selectedProvider}`
  )

  const expectation = getProviderFieldExpectation(provider)
  for (const selector of expectation.selectors) {
    await page.waitForSelector(selector, { state: 'visible', timeout: 30000 })
  }
  return expectation.summary
}

async function applyProviderFormValues(page, payload) {
  await page.selectOption('#settings-llm-provider', payload.llm_provider)

  if (payload.llm_provider === 'openai') {
    await page.locator('#settings-openai-base-url').fill(payload.openai_base_url)
    await page.locator('#settings-openai-model').fill(payload.openai_model)
    return
  }

  if (payload.llm_provider === 'anthropic') {
    await page.locator('#settings-anthropic-model').fill(payload.anthropic_model)
    return
  }

  await page.locator('#settings-ollama-url').fill(payload.ollama_url)
  await page.locator('#settings-ollama-model').fill(payload.ollama_model)
}

async function runBrowserChecks(activePayload, overrideApplied) {
  const browser = await launchPlaywrightBrowser(chromium, FRONTEND_ROOT)
  try {
    const page = await browser.newPage()

    await page.goto(`${BACKEND_BASE_URL}/startup`, { waitUntil: 'networkidle' })
    await page.waitForSelector('.btn-check-services', { state: 'visible', timeout: 30000 })
    await page.click('.btn-check-services')
    await page.waitForSelector('.startup-alert--success, .startup-alert--warning', { timeout: 30000 })
    const startupAlertLocator = page.locator('.startup-alert--success, .startup-alert--warning').first()
    const startupAlertClass = await startupAlertLocator.getAttribute('class')
    const startupAlertText = (await startupAlertLocator.textContent())?.trim() || ''
    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-14-real-startup.png'),
      fullPage: true
    })

    await page.goto(`${BACKEND_BASE_URL}/settings`, { waitUntil: 'networkidle' })
    await page.waitForSelector('.settings-content', { state: 'visible', timeout: 30000 })
    await page.waitForSelector('.settings-save-btn', { state: 'visible', timeout: 30000 })

    const currentLayout = await page.locator('#settings-visual-layout').inputValue()
    const nextLayout = currentLayout === 'force' ? 'hierarchical' : 'force'
    await page.selectOption('#settings-visual-layout', nextLayout)
    await page.click('.settings-save-btn')
    await page.waitForSelector('text=配置已保存', { timeout: 30000 })

    if (overrideApplied) {
      await applyProviderFormValues(page, activePayload)
    }

    const providerFields = await assertProviderSpecificSettings(page, activePayload.llm_provider)

    await page.click('.settings-test-btn')
    await page.waitForSelector('.settings-connection-item', { timeout: 30000 })
    await page.waitForSelector('.settings-status--success, .settings-status--failed', {
      timeout: 30000
    })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-14-real-settings.png'),
      fullPage: true
    })

    const inboxSmoke = await runInboxChecks(page)

    return {
      providerFields,
      inboxSmoke,
      startupAlertType: startupAlertClass?.includes('startup-alert--warning') ? 'warning' : 'success',
      startupAlertText,
    }
  } finally {
    await browser.close()
  }
}

async function runInboxChecks(page) {
  await page.goto(`${BACKEND_BASE_URL}/inbox`, { waitUntil: 'networkidle' })
  await page.waitForSelector('.import-page', { state: 'visible', timeout: 30000 })
  await page.waitForSelector('.import-tabs', { state: 'visible', timeout: 30000 })
  await page.waitForSelector('.import-tab[data-tab="directory"]', { state: 'visible', timeout: 30000 })
  await page.click('.import-tab[data-tab="directory"]')
  await page.waitForSelector('#import-directory-path-input', { state: 'visible', timeout: 30000 })
  await page.waitForSelector('section[aria-label="Recent import runs"]', {
    state: 'visible',
    timeout: 30000
  })
  await page.waitForSelector('.import-run-history-refresh', { state: 'visible', timeout: 30000 })

  await page.screenshot({
    path: path.join(EVIDENCE_DIR, 'task-14-real-inbox.png'),
    fullPage: true
  })

  return {
    status: 'passed',
    checks: [
      'inbox_page_loaded',
      'import_tabs_visible',
      'directory_tab_switchable',
      'directory_form_visible',
      'recent_import_runs_panel_visible'
    ]
  }
}

async function fetchConfigSnapshot() {
  const response = await requestJson(`${BACKEND_BASE_URL}/api/v1/config`)
  assertSmoke(
    response.statusCode === 200 && response.json && typeof response.json === 'object',
    formatHttpFailure('GET /api/v1/config', response)
  )
  return response
}

async function putConfig(payload) {
  const response = await requestJson(`${BACKEND_BASE_URL}/api/v1/config`, {
    method: 'PUT',
    headers: {
      'content-type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
  assertSmoke(response.statusCode === 200, formatHttpFailure('PUT /api/v1/config', response))
  return response
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-14-real-backend-health.json',
    'task-14-real-browser-blocker.txt',
    'task-14-real-connection.json',
    'task-14-real-inbox.png',
    'task-14-real-settings.png',
    'task-14-real-sidecar-health.json',
    'task-14-real-smoke-error.txt',
    'task-14-real-smoke-summary.txt',
    'task-14-real-startup.png'
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runCommand(FRONTEND_ROOT, 'npm', ['run', 'build:web'], 'task-14-build-frontend.log')
  await runCommand(SIDECAR_ROOT, 'npm', ['run', 'build'], 'task-14-build-sidecar.log')

  const sidecar = startService({
    cwd: SIDECAR_ROOT,
    command: 'node',
    args: ['dist/main.js'],
    env: {
      HOST: '127.0.0.1',
      PORT: String(SIDECAR_PORT),
      BACKEND_BASE_URL: BACKEND_BASE_URL
    },
    logName: 'task-14-sidecar.log'
  })

  const backend = startService({
    cwd: REPO_ROOT,
    command: 'python3',
    args: ['-m', 'uvicorn', 'src.api.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    env: {
      PYTHONPATH: '.',
      SIDECAR_BASE_URL: SIDECAR_BASE_URL
    },
    logName: 'task-14-backend.log'
  })

  try {
    const backendHealth = await waitForStatus(
      `${BACKEND_BASE_URL}/health`,
      (response) => response.statusCode === 200 && response.json?.status === 'healthy'
    )

    const sidecarHealth = await waitForStatus(
      `${SIDECAR_BASE_URL}/health`,
      (response) => response.statusCode === 200 && response.json?.status === 'UP'
    )

    let capturedError = null
    const settingsBefore = await fetchConfigSnapshot()
    const originalPayload = buildConfigPayloadFromSettings(settingsBefore.json)
    const overrideConfig = buildOverrideConfigPayload(originalPayload, process.env)
    const activePayload = overrideConfig.payload
    let saveResponse = null
    let connectionResponse = null
    let currentProvider = activePayload.llm_provider
    let currentProviderSuccess = null
    let providerFields = 'unknown'
    let startupAlertType = 'unknown'
    let startupAlertText = ''
    let inboxSmoke = { status: 'failed', checks: [], note: 'not_executed' }
    const overrideMode = overrideConfig.overrideApplied ? 'transient' : 'none'

    try {
      saveResponse = await putConfig(originalPayload)
      currentProvider = resolveCurrentProvider(activePayload, EXPECTED_PROVIDER)

      connectionResponse = await requestJson(`${BACKEND_BASE_URL}/api/v1/config/test-connection`, {
        method: 'POST',
        timeoutMs: 30000,
        headers: {
          'content-type': 'application/json'
        },
        body: JSON.stringify(activePayload)
      })
      assertSmoke(
        connectionResponse.statusCode === 200,
        formatHttpFailure('POST /api/v1/config/test-connection', connectionResponse)
      )
      assertSmoke(
        connectionResponse.json?.graph_store === true,
        `POST /api/v1/config/test-connection reported graph_store=${connectionResponse.json?.graph_store}`
      )
      assertSmoke(
        connectionResponse.json?.vector_store === true,
        `POST /api/v1/config/test-connection reported vector_store=${connectionResponse.json?.vector_store}`
      )
      currentProviderSuccess = assertCurrentProviderConnection(
        connectionResponse.json,
        currentProvider,
        REQUIRE_CURRENT_PROVIDER_SUCCESS
      )

      try {
        const browserChecks = await runBrowserChecks(activePayload, overrideConfig.overrideApplied)
        providerFields = browserChecks.providerFields
        inboxSmoke = browserChecks.inboxSmoke
        startupAlertType = browserChecks.startupAlertType
        startupAlertText = browserChecks.startupAlertText
      } catch (error) {
        await writeFile(
          path.join(EVIDENCE_DIR, 'task-14-real-browser-blocker.txt'),
          `${error.stack || error.message || String(error)}\n`,
          'utf8'
        )
        throw new Error(`Browser smoke failed: ${error instanceof Error ? error.message : String(error)}`)
      }
    } catch (error) {
      capturedError = error
    }

    if (capturedError) {
      throw capturedError
    }

    const settingsAfter = await fetchConfigSnapshot()
    const finalPayload = buildConfigPayloadFromSettings(settingsAfter.json)
    assertSmoke(
      configPayloadEquals(finalPayload, originalPayload),
      'Visible config fields changed during smoke run'
    )

    const summary = [
      `backend_health_status=${backendHealth.json?.status}`,
      `sidecar_health_status=${sidecarHealth.json?.status}`,
      `startup_alert_type=${startupAlertType}`,
      `startup_alert_text=${startupAlertText}`,
      `settings_save_status=${saveResponse.statusCode}`,
      `settings_save_message=${saveResponse.json?.message || ''}`,
      `config_override_applied=${overrideConfig.overrideApplied}`,
      `config_override_fields=${overrideConfig.changedFields.join(',') || 'none'}`,
      `config_override_mode=${overrideMode}`,
      'config_restore_status=not-needed',
      'config_restore_verified=true',
      `config_restore_message=${overrideConfig.overrideApplied ? 'override was never persisted' : ''}`,
      `current_provider=${currentProvider}`,
      `current_provider_fields=${providerFields}`,
      `current_provider_success=${currentProviderSuccess}`,
      `require_current_provider_success=${REQUIRE_CURRENT_PROVIDER_SUCCESS}`,
      `connection_test=${buildConnectionSummary(connectionResponse.json)}`,
      ...buildInboxSmokeSummaryLines(inboxSmoke),
      'browser_smoke=passed'
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-14-real-smoke-summary.txt'), summary, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-14-real-backend-health.json'),
      JSON.stringify(backendHealth.json, null, 2),
      'utf8'
    )
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-14-real-sidecar-health.json'),
      JSON.stringify(sidecarHealth.json, null, 2),
      'utf8'
    )
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-14-real-connection.json'),
      JSON.stringify(connectionResponse.json, null, 2),
      'utf8'
    )

    process.stdout.write(`${summary}\n`)
  } finally {
    await stopService(backend)
    await stopService(sidecar)
  }
}

main().catch(async (error) => {
  const failurePath = path.join(EVIDENCE_DIR, 'task-14-real-smoke-error.txt')
  if (!fs.existsSync(EVIDENCE_DIR)) {
    await mkdir(EVIDENCE_DIR, { recursive: true })
  }
  await writeFile(failurePath, `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
