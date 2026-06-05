import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { chromium } from 'playwright'

import {
  buildBaseUrl,
  findAvailablePort,
  runBuildWeb,
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
import { IMPORT_SMOKE_TEST_IDS } from '../pages/ImportPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SETTINGS_PATH_ENV = 'MEMORY_GRAPH_SETTINGS_PATH'

async function startFakeOllamaServer(port) {
  let tagRequests = 0

  const server = http.createServer((request, response) => {
    if (request.method === 'GET' && request.url === '/api/tags') {
      tagRequests += 1
      response.writeHead(200, { 'content-type': 'application/json' })
      response.end(JSON.stringify({ models: [] }))
      return
    }

    response.writeHead(404, { 'content-type': 'application/json' })
    response.end(JSON.stringify({ detail: 'not found' }))
  })

  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(port, '127.0.0.1', resolve)
  })

  return {
    getTagRequests: () => tagRequests,
    async close() {
      await new Promise((resolve) => server.close(resolve))
    },
  }
}

async function writeTaskChainFixtures(workspaceRoot, homeDir) {
  const dataDir = path.join(workspaceRoot, 'data')
  const sourceWorkspaceRoot = path.join(workspaceRoot, 'workspace-notes')
  await mkdir(dataDir, { recursive: true })
  await mkdir(sourceWorkspaceRoot, { recursive: true })

  const syncSourcesPath = path.join(dataDir, 'sync-sources.json')
  await writeFile(
    syncSourcesPath,
    `${JSON.stringify({
      version: 1,
      sources: [
        {
          source_id: 'src-1',
          label: 'Workspace Notes',
          source_system: 'notes',
          workspace_id: 'workspace-notes',
          workspace_root: sourceWorkspaceRoot,
          source_paths: ['notes/**/*.md'],
        },
      ],
    }, null, 2)}\n`,
    'utf8'
  )

  const stateDir = path.join(homeDir, '.openclaw', 'workspace-notes', 'state')
  await mkdir(stateDir, { recursive: true })
  const statePath = path.join(stateDir, 'memory-graph-sync.json')
  await writeFile(
    statePath,
    `${JSON.stringify({
      workspace_id: 'workspace-notes',
      last_pulled_seq: 12,
      records: {
        'ext-1': {
          external_id: 'ext-1',
          source_path: 'notes/a.md',
          last_checksum: 'sha256:a',
          sync_status: 'synced',
        },
        'ext-2': {
          external_id: 'ext-2',
          source_path: 'notes/b.md',
          last_checksum: 'sha256:b',
          sync_status: 'conflict',
        },
        'ext-3': {
          external_id: 'ext-3',
          source_path: 'notes/c.md',
          last_checksum: 'sha256:c',
          sync_status: 'deleted',
        },
      },
      recent_mutation_ids: [],
    }, null, 2)}\n`,
    'utf8'
  )

  return { syncSourcesPath, statePath, sourceWorkspaceRoot }
}

async function verifyHttpContract({ backendBaseUrl, fakeOllama }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const diagnostics = await requestJson(`${backendBaseUrl}/api/v1/diagnostics/runtime`)
  assertSmoke(diagnostics.statusCode === 200, `GET /diagnostics/runtime failed: ${diagnostics.raw}`)
  assertSmoke(diagnostics.json?.status === 'healthy', `Expected diagnostics status=healthy, got ${diagnostics.json?.status}`)
  assertSmoke(diagnostics.json?.checks?.provider?.current_provider === 'ollama', `Expected current provider=ollama, got ${diagnostics.json?.checks?.provider?.current_provider}`)
  assertSmoke(diagnostics.json?.checks?.provider?.ok === true, `Expected provider.ok=true, got ${diagnostics.json?.checks?.provider?.ok}`)
  assertSmoke(diagnostics.json?.task_chain?.status === 'degraded', `Expected task_chain.status=degraded, got ${diagnostics.json?.task_chain?.status}`)
  assertSmoke(diagnostics.json?.task_chain?.configured_sources === 1, `Expected configured_sources=1, got ${diagnostics.json?.task_chain?.configured_sources}`)
  assertSmoke(
    diagnostics.json?.task_chain?.sources?.[0]?.label === 'Workspace Notes',
    `Expected source label Workspace Notes, got ${diagnostics.json?.task_chain?.sources?.[0]?.label}`
  )
  assertSmoke(
    diagnostics.json?.task_chain?.sources?.[0]?.conflicts === 1,
    `Expected one conflict, got ${diagnostics.json?.task_chain?.sources?.[0]?.conflicts}`
  )
  assertSmoke(
    Array.isArray(diagnostics.json?.recent_failures) && diagnostics.json.recent_failures.some((item) => item?.component === 'task_chain'),
    'Expected recent_failures to include task_chain entry'
  )
  assertSmoke(fakeOllama.getTagRequests() >= 2, `Expected fake ollama to be hit at least twice, got ${fakeOllama.getTagRequests()}`)

  return { health, diagnostics }
}

async function runBrowserFlow({ backendBaseUrl, fakeOllama }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env)
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/inbox`, { waitUntil: 'networkidle' })
    await page.waitForSelector(`[data-testid="${IMPORT_SMOKE_TEST_IDS.diagnosticsCard}"]`, { timeout: 30000 })
    await page.waitForSelector(`[data-testid="${IMPORT_SMOKE_TEST_IDS.diagnosticsSummary}"]`, { timeout: 30000 })
    await page.waitForSelector('text=核心运行依赖健康，但同步链路仍有待处理项。', { timeout: 30000 })
    await page.waitForSelector('text=Task Chain：1 sync source(s) need attention', { timeout: 30000 })
    await page.waitForSelector('text=attention_sources: 1', { timeout: 30000 })
    await page.waitForSelector('text=recent_failures: 1', { timeout: 30000 })
    await page.waitForSelector('text=Workspace Notes', { timeout: 30000 })
    await page.waitForSelector('text=1 conflicted records require attention', { timeout: 30000 })
    await page.waitForSelector('text=retry guidance: 检测到冲突记录', { timeout: 30000 })

    const initialTagRequests = fakeOllama.getTagRequests()
    const refreshResponse = page.waitForResponse(
      (response) => response.url().endsWith('/api/v1/diagnostics/runtime') && response.status() === 200
    )
    await page.click(`[data-testid="${IMPORT_SMOKE_TEST_IDS.diagnosticsRefreshButton}"]`)
    await refreshResponse
    assertSmoke(fakeOllama.getTagRequests() > initialTagRequests, 'Expected refresh to trigger another provider check')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-23-import-diagnostics-real.png'),
      fullPage: true,
    })

    return {
      fakeOllamaTagRequests: fakeOllama.getTagRequests(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-23-import-diagnostics-real-summary.txt',
    'task-23-import-diagnostics-real-summary.json',
    'task-23-import-diagnostics-real-http.json',
    'task-23-import-diagnostics-real.png',
    'task-23-import-diagnostics-real-error.txt',
    'task-23-import-diagnostics-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-import-diagnostics-'))
  const homeDir = path.join(workspaceRoot, 'home')
  await mkdir(homeDir, { recursive: true })

  const backendPort = await findAvailablePort(Number(process.env.T23_BACKEND_PORT ?? '38230'))
  const ollamaPort = await findAvailablePort(Number(process.env.T23_OLLAMA_PORT ?? '38231'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)

  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
  })
  const taskChainFixture = await writeTaskChainFixtures(workspaceRoot, homeDir)
  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-23-import-diagnostics-real-backend.log',
    backendPort,
    extraEnv: {
      HOME: homeDir,
      [SETTINGS_PATH_ENV]: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, fakeOllama })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, fakeOllama })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:import:diagnostics',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      sync_sources_path: taskChainFixture.syncSourcesPath,
      state_path: taskChainFixture.statePath,
      diagnostics_status: httpEvidence.diagnostics.json?.status,
      provider_ok: httpEvidence.diagnostics.json?.checks?.provider?.ok,
      task_chain_status: httpEvidence.diagnostics.json?.task_chain?.status,
      task_chain_configured_sources: httpEvidence.diagnostics.json?.task_chain?.configured_sources,
      task_chain_conflicts: httpEvidence.diagnostics.json?.task_chain?.sources?.[0]?.conflicts,
      recent_failures_count: Array.isArray(httpEvidence.diagnostics.json?.recent_failures)
        ? httpEvidence.diagnostics.json.recent_failures.length
        : 0,
      fake_ollama_tag_requests: browserEvidence.fakeOllamaTagRequests,
      screenshot: '.sisyphus/evidence/task-23-import-diagnostics-real.png',
      backend_log: '.sisyphus/evidence/task-23-import-diagnostics-real-backend.log',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `diagnostics_status=${summaryPayload.diagnostics_status}`,
      `provider_ok=${summaryPayload.provider_ok}`,
      `task_chain_status=${summaryPayload.task_chain_status}`,
      `task_chain_configured_sources=${summaryPayload.task_chain_configured_sources}`,
      `task_chain_conflicts=${summaryPayload.task_chain_conflicts}`,
      `recent_failures_count=${summaryPayload.recent_failures_count}`,
      `fake_ollama_tag_requests=${summaryPayload.fake_ollama_tag_requests}`,
      `config_path=${summaryPayload.config_path}`,
      `sync_sources_path=${summaryPayload.sync_sources_path}`,
      `state_path=${summaryPayload.state_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-23-import-diagnostics-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-23-import-diagnostics-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-23-import-diagnostics-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        diagnostics: httpEvidence.diagnostics.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-23-import-diagnostics-real-error.txt'),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    await stopPreviewServer(backend.child)
    await backend.flushLog()
    await fakeOllama.close()
    await rm(workspaceRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
