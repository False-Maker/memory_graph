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

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')
const BACKEND_HEALTH_ROUTE = /http:\/\/(127\.0\.0\.1|localhost):8000\/health$/
const BACKEND_DIAGNOSTICS_ROUTE = /http:\/\/(127\.0\.0\.1|localhost):8000\/api\/v1\/diagnostics\/runtime$/
const SIDECAR_HEALTH_ROUTE = /http:\/\/(127\.0\.0\.1|localhost):3001\/health$/

async function waitForStartupReady(page) {
  await page.waitForURL('**/startup', { timeout: 30000 })
  await page.waitForSelector('.btn-check-services', { state: 'visible', timeout: 30000 })
  await page.waitForSelector('text=运维指引', { timeout: 30000 })
}

async function registerHealthyStartupRoutes(context) {
  await context.route(BACKEND_HEALTH_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'healthy', service: 'Memory Graph API', version: '1.0.0' })
    })
  })

  await context.route(BACKEND_DIAGNOSTICS_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'healthy',
        generated_at: '2026-04-08T02:00:00Z',
        checks: {
          config: { ok: true },
          provider: { ok: true, current_provider: 'openai', providers: { openai: true }, provider_errors: {}, current_error: null },
          sqlite: { ok: true },
          vector_store: { ok: true, state: { indexed_documents: 12, stored_documents: 12, dimension_mismatch: false } }
        },
        task_chain: { status: 'not_configured', configured_sources: 0, sources: [], detail: null },
        recent_failures: []
      })
    })
  })

  await context.route(SIDECAR_HEALTH_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'UP' })
    })
  })
}

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  await registerHealthyStartupRoutes(context)

  const page = await context.newPage()
  await page.goto(`${baseUrl}/startup`, { waitUntil: 'networkidle' })
  await waitForStartupReady(page)

  await page.click('.btn-check-services')
  await page.waitForSelector('text=Backend API', { timeout: 30000 })
  await page.waitForSelector('text=Sidecar API', { timeout: 30000 })
  await page.waitForSelector('text=Runtime OK', { timeout: 30000 })
  await page.waitForSelector('text=UP', { timeout: 30000 })
  await page.waitForSelector('text=所有基础服务探测通过', { timeout: 30000 })

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-13-startup-status.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'healthy_path',
    status: 'passed',
    alert: 'success',
    artifact: 'task-13-startup-status.png',
  }
}

async function runWarningPath(browser, baseUrl) {
  const context = await browser.newContext()

  await context.route(BACKEND_HEALTH_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'healthy', service: 'Memory Graph API', version: '1.0.0' })
    })
  })

  await context.route(BACKEND_DIAGNOSTICS_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'unhealthy',
        generated_at: '2026-04-08T02:05:00Z',
        checks: {
          config: { ok: true },
          provider: {
            ok: false,
            current_provider: 'openai',
            providers: { current: false, ollama: true },
            provider_errors: { current: 'OpenAI API key is not configured' },
            current_error: 'OpenAI API key is not configured',
          },
          sqlite: { ok: true },
          vector_store: { ok: true, state: { indexed_documents: 12, stored_documents: 12, dimension_mismatch: false } }
        },
        task_chain: { status: 'not_configured', configured_sources: 0, sources: [], detail: null },
        recent_failures: [
          { component: 'provider', detail: 'OpenAI API key is not configured', source: '/api/v1/diagnostics/runtime', count: 1 }
        ]
      })
    })
  })

  await context.route(SIDECAR_HEALTH_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'UP' })
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/startup`, { waitUntil: 'networkidle' })
  await waitForStartupReady(page)

  await page.click('.btn-check-services')
  await page.waitForSelector('text=基础服务可达，但 backend 运行诊断仍有告警', { timeout: 30000 })
  await page.waitForSelector('text=Runtime ATTN', { timeout: 30000 })
  await page.waitForSelector('text=OpenAI API key is not configured', { timeout: 30000 })

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-13-startup-warning.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'warning_path',
    status: 'passed',
    alert: 'warning',
    artifact: 'task-13-startup-warning.png',
  }
}

async function runFailurePath(browser, baseUrl) {
  const context = await browser.newContext()

  await context.route(BACKEND_HEALTH_ROUTE, async (route) => {
    await route.abort('failed')
  })

  await context.route(SIDECAR_HEALTH_ROUTE, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'UP' })
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/startup`, { waitUntil: 'networkidle' })
  await waitForStartupReady(page)

  await page.click('.btn-check-services')
  await page.waitForSelector('text=检测到基础服务不可达', { timeout: 30000 })
  await page.waitForSelector('.startup-status-badge--down', { timeout: 30000 })

  const backendCard = page.locator('article[aria-label="Backend API status card"]')
  await backendCard.waitFor({ state: 'visible', timeout: 30000 })
  await backendCard.locator('text=DOWN').waitFor({ timeout: 30000 })

  const sidecarCard = page.locator('article[aria-label="Sidecar API status card"]')
  await sidecarCard.waitFor({ state: 'visible', timeout: 30000 })
  await sidecarCard.locator('text=UP').waitFor({ timeout: 30000 })

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-13-startup-down.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'down_path',
    status: 'passed',
    alert: 'error',
    artifact: 'task-13-startup-down.png',
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-13-preview.log')
  await Promise.all([
    'task-13-startup-summary.txt',
    'task-13-startup-summary.json',
    'task-13-startup-error.txt',
    'task-13-startup-status.png',
    'task-13-startup-warning.png',
    'task-13-startup-down.png',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb()
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t13', 'T13_PREVIEW_PORT'))
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
      results.push(await runWarningPath(browser, baseUrl))
      results.push(await runFailurePath(browser, baseUrl))

      const generatedAt = new Date().toISOString()
      await writePlaywrightSmokeEvidence({
        evidenceDir: EVIDENCE_DIR,
        summaryFileName: 'task-13-startup-summary.txt',
        jsonFileName: 'task-13-startup-summary.json',
        generatedAt,
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-13-preview.log'],
        extraSummaryFields: {
          alerts: results.map((item) => item.alert).join(','),
        },
        extraJsonFields: {
          alerts: results.map((item) => item.alert),
        },
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T13 startup Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-13-startup-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
