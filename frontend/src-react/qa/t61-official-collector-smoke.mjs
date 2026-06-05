import { copyFile, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import {
  assertSmoke,
  delay,
  requestJson,
  startBackendService,
  waitForStatus,
} from './focused-real-smoke-runtime.mjs'
import {
  OFFICIAL_COLLECTOR_SMOKE_CASES,
  buildOfficialCollectorMatrixSummary,
  getOfficialCollectorMatrixEvidencePaths,
} from './t61-official-collector-matrix-helpers.mjs'

const FRONTEND_ROOT = process.cwd()
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const FIXTURE_DIR = path.resolve(REPO_ROOT, 'tests', 'fixtures', 'phase1_import')
const SETTINGS_PATH_ENV = 'MEMORY_GRAPH_SETTINGS_PATH'
const BACKEND_PORT = Number(process.env.T61_BACKEND_PORT ?? '38261')
const BACKEND_BASE_URL = `http://127.0.0.1:${BACKEND_PORT}`
const SUMMARY_TXT_NAME = 'task-61-official-collector-matrix-summary.txt'
const SUMMARY_JSON_NAME = 'task-61-official-collector-matrix-summary.json'
const BACKEND_LOG_NAME = 'task-61-official-collector-matrix-backend.log'
const ERROR_TXT_NAME = 'task-61-official-collector-matrix-error.txt'

function normalizePathForYaml(value) {
  return String(value).replace(/\\/g, '/')
}

function buildSettingsYaml({ workspaceRoot, windsurfDir, claudeDir, aiderProjectDir }) {
  return [
    'llm:',
    '  provider: "openai"',
    '  openai:',
    '    api_key: ""',
    '    base_url: "https://api.openai.com/v1"',
    '    model: "gpt-4o"',
    'database:',
    '  vector:',
    '    type: "faiss"',
    '    faiss:',
    `      persist_directory: "${normalizePathForYaml(path.join(workspaceRoot, 'data', 'faiss'))}"`,
    'app:',
    '  host: "127.0.0.1"',
    `  port: ${BACKEND_PORT}`,
    'collectors:',
    '  windsurf:',
    '    enabled: true',
    `    data_dir: "${normalizePathForYaml(windsurfDir)}"`,
    '    auto_scan_interval: 1',
    '    watch_projects: []',
    '  claude_code:',
    '    enabled: true',
    `    data_dir: "${normalizePathForYaml(claudeDir)}"`,
    '    auto_scan_interval: 1',
    '    project_dirs: []',
    '    watch_terminal: false',
    '  aider:',
    '    enabled: true',
    '    auto_scan_interval: 1',
    `    project_dirs: ["${normalizePathForYaml(aiderProjectDir)}"]`,
    '',
  ].join('\n')
}

async function waitForCollectorProcessing(url, collectorType, minProcessedCount = 1, timeoutMs = 30000) {
  const start = Date.now()
  let lastResponse = null

  while (Date.now() - start < timeoutMs) {
    lastResponse = await requestJson(url)
    if (lastResponse.statusCode === 200) {
      const json = lastResponse.json || {}
      const collectors = Array.isArray(json.collectors) ? json.collectors : []
      const bySource = json?.stats?.by_source || {}
      const collectorStatus = collectors.find((item) => item?.type === collectorType)
      if (
        collectorStatus?.running === true
        && collectorStatus?.support_tier === 'official'
        && Number(bySource[collectorType] || 0) >= minProcessedCount
      ) {
        return lastResponse
      }
    }
    await delay(500)
  }

  throw new Error(`Timed out waiting for collector ${collectorType} processing; last=${lastResponse?.raw || 'none'}`)
}

async function prepareCollectorFixtures(workspaceRoot) {
  const windsurfDir = path.join(workspaceRoot, 'windsurf')
  const claudeDir = path.join(workspaceRoot, 'home', '.claude')
  const aiderProjectDir = path.join(workspaceRoot, 'aider-project')

  await mkdir(path.join(windsurfDir, 'conversations'), { recursive: true })
  await mkdir(path.join(claudeDir, 'sessions'), { recursive: true })
  await mkdir(aiderProjectDir, { recursive: true })

  await copyFile(
    path.join(FIXTURE_DIR, 'claude_code_session.jsonl'),
    path.join(windsurfDir, 'conversations', 'windsurf-session.jsonl')
  )
  await copyFile(
    path.join(FIXTURE_DIR, 'claude_code_session.jsonl'),
    path.join(claudeDir, 'sessions', 'claude-code-session.jsonl')
  )

  await writeFile(
    path.join(aiderProjectDir, '.aider.chat.history'),
    [
      '[user]: Summarize the rollout plan for Memory Graph.',
      '[aider]: Windsurf, Claude Code, and Aider are the current official collectors.',
      '',
    ].join('\n'),
    'utf8'
  )

  return { windsurfDir, claudeDir, aiderProjectDir }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const evidencePaths = getOfficialCollectorMatrixEvidencePaths(EVIDENCE_DIR)
  await Promise.all([
    path.join(EVIDENCE_DIR, SUMMARY_TXT_NAME),
    path.join(EVIDENCE_DIR, SUMMARY_JSON_NAME),
    evidencePaths.http,
    path.join(EVIDENCE_DIR, BACKEND_LOG_NAME),
    path.join(EVIDENCE_DIR, ERROR_TXT_NAME),
  ].map((target) => rm(target, { force: true })))

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-official-collectors-'))
  const configDir = path.join(workspaceRoot, 'config')
  await mkdir(configDir, { recursive: true })

  const fixtures = await prepareCollectorFixtures(workspaceRoot)
  const configPath = path.join(configDir, 'settings.yaml')
  await writeFile(configPath, buildSettingsYaml({ workspaceRoot, ...fixtures }), 'utf8')

  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: BACKEND_LOG_NAME,
    backendPort: BACKEND_PORT,
    extraEnv: {
      HOME: path.join(workspaceRoot, 'home'),
      [SETTINGS_PATH_ENV]: configPath,
    },
  })

  try {
    const healthResponse = await waitForStatus(
      `${BACKEND_BASE_URL}/health`,
      (response) => response.statusCode === 200 && response.json?.status === 'healthy'
    )

    const startResponse = await requestJson(`${BACKEND_BASE_URL}/api/collectors/start`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        enabled_types: OFFICIAL_COLLECTOR_SMOKE_CASES.map((item) => item.collectorType),
      }),
    })
    assertSmoke(startResponse.statusCode === 200, `collector start failed: ${startResponse.raw}`)

    const tasks = []
    for (const collectorCase of OFFICIAL_COLLECTOR_SMOKE_CASES) {
      const statusResponse = await waitForCollectorProcessing(
        `${BACKEND_BASE_URL}/api/collectors/status`,
        collectorCase.collectorType
      )
      const detailResponse = await requestJson(
        `${BACKEND_BASE_URL}/api/collectors/collectors/${collectorCase.collectorType}`
      )
      assertSmoke(
        detailResponse.statusCode === 200,
        `collector detail failed for ${collectorCase.collectorType}: ${detailResponse.raw}`
      )
      assertSmoke(
        detailResponse.json?.support_tier === 'official',
        `expected official support tier for ${collectorCase.collectorType}`
      )

      tasks.push({
        collectorType: collectorCase.collectorType,
        label: collectorCase.label,
        supportTier: collectorCase.supportTier,
        status: 'passed',
        exitCode: 0,
        processedCount: Number(statusResponse.json?.stats?.by_source?.[collectorCase.collectorType] || 0),
        detail: `running=${detailResponse.json?.running}|status=${detailResponse.json?.status}`,
      })
    }

    const stopResponse = await requestJson(`${BACKEND_BASE_URL}/api/collectors/stop`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        collector_types: OFFICIAL_COLLECTOR_SMOKE_CASES.map((item) => item.collectorType),
      }),
    })
    assertSmoke(stopResponse.statusCode === 200, `collector stop failed: ${stopResponse.raw}`)

    const httpEvidence = {
      generated_at: new Date().toISOString(),
      health: healthResponse.json,
      start: startResponse.json,
      stop: stopResponse.json,
      tasks: tasks,
    }

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:collectors:official',
      status: 'passed',
      backend_base_url: BACKEND_BASE_URL,
      settings_path: configPath,
      tasks: tasks,
      counts: {
        passed: tasks.filter((task) => task.status === 'passed').length,
        blocked: 0,
        failed: tasks.filter((task) => task.status === 'failed').length,
      },
      http_evidence: '.sisyphus/evidence/task-61-official-collector-matrix-http.json',
      backend_log: '.sisyphus/evidence/task-61-official-collector-matrix-backend.log',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `source=qa:real-stack-smoke:collectors:official`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `backend_base_url=${summaryPayload.backend_base_url}`,
      ...tasks.flatMap((task) => [
        '',
        `collector=${task.collectorType}`,
        `label=${task.label}`,
        `support_tier=${task.supportTier}`,
        `status=${task.status}`,
        `processed_count=${task.processedCount}`,
        `detail=${task.detail}`,
      ]),
      '',
      `passed_count=${summaryPayload.counts.passed}`,
      `failed_count=${summaryPayload.counts.failed}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, SUMMARY_TXT_NAME), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, SUMMARY_JSON_NAME), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      evidencePaths.http,
      `${JSON.stringify({
        generated_at: httpEvidence.generated_at,
        health: healthResponse.json,
        start: startResponse.json,
        stop: stopResponse.json,
        tasks: tasks,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(buildOfficialCollectorMatrixSummary(tasks, {
      generatedAt: summaryPayload.generated_at,
      source: 'qa:real-stack-smoke:collectors:official',
      backendBaseUrl: BACKEND_BASE_URL,
    }))
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, ERROR_TXT_NAME),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    backend.child.kill('SIGTERM')
    await backend.flushLog()
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exit(1)
})
