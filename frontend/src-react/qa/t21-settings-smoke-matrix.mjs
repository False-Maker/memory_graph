import { mkdir, writeFile } from 'node:fs/promises'
import fs from 'node:fs'
import path from 'node:path'

import {
  buildSettingsSmokeMatrixSummary,
  extractSettingsSmokeSummaryField,
  getSettingsSmokeMatrixEvidencePaths,
  getSettingsSmokeMatrixLogPath,
  getSettingsSmokeTaskEvidencePaths,
  listSettingsSmokeTasks,
  summarizeSettingsSmokeText,
} from './t21-settings-smoke-matrix-helpers.mjs'
import {
  buildBaseUrl,
  applyBrowserLibEnv,
  buildBrowserLibDir,
  buildSettingsSmokeMatrixChildEnv,
  findAvailablePort,
  resolvePlaywrightPreviewStartPort,
  runBuildWeb,
  startPreviewServer,
  stopPreviewServer,
  waitForManagedPreviewServerReady,
} from './settings-playwright-runtime.mjs'
import { chromium } from 'playwright'
import { runT12SettingsPlaywright } from './t12-settings-playwright.mjs'
import { runT19SettingsRecoveryPlaywright } from './t19-settings-recovery-playwright.mjs'
import { runT20SettingsReindexPlaywright } from './t20-settings-reindex-playwright.mjs'

const FRONTEND_ROOT = process.cwd()
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SOURCE = 'qa:settings-playwright'

function readOptionalFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8')
  } catch {
    return ''
  }
}

const SETTINGS_SMOKE_TASK_RUNNERS = Object.freeze({
  t12: runT12SettingsPlaywright,
  t19: runT19SettingsRecoveryPlaywright,
  t20: runT20SettingsReindexPlaywright,
})

function toTextChunk(chunk, encoding) {
  if (typeof chunk === 'string') {
    return chunk
  }
  if (chunk instanceof Uint8Array) {
    return Buffer.from(chunk).toString(typeof encoding === 'string' ? encoding : undefined)
  }
  return String(chunk)
}

function buildTaskBanner(task) {
  const packageName = process.env.npm_package_name || 'memory-graph-frontend'
  const packageVersion = process.env.npm_package_version || '1.0.0'
  return `\n> ${packageName}@${packageVersion} ${task.npmScript}\n> ${task.directCommand}\n\n`
}

async function withCapturedTaskOutput(task, runTask) {
  const logChunks = []
  const originalStdoutWrite = process.stdout.write
  const originalStderrWrite = process.stderr.write
  process.stdout.write = (chunk, encoding, callback) => {
    logChunks.push(toTextChunk(chunk, encoding))
    return Reflect.apply(originalStdoutWrite, process.stdout, [chunk, encoding, callback])
  }
  process.stderr.write = (chunk, encoding, callback) => {
    logChunks.push(toTextChunk(chunk, encoding))
    return Reflect.apply(originalStderrWrite, process.stderr, [chunk, encoding, callback])
  }

  let exitCode = 0
  try {
    process.stdout.write(buildTaskBanner(task))
    await runTask()
  } catch (error) {
    exitCode = 1
    process.stderr.write(`${error.stack || error.message}\n`)
  } finally {
    process.stdout.write = originalStdoutWrite
    process.stderr.write = originalStderrWrite
  }

  return {
    exitCode,
    log: logChunks.join(''),
  }
}

async function withTaskEnv(taskEnv, runTask) {
  const originalEnv = { ...process.env }
  for (const key of Object.keys(process.env)) {
    if (!(key in taskEnv)) {
      delete process.env[key]
    }
  }
  Object.assign(process.env, taskEnv)

  try {
    return await runTask()
  } finally {
    for (const key of Object.keys(process.env)) {
      if (!(key in originalEnv)) {
        delete process.env[key]
      }
    }
    Object.assign(process.env, originalEnv)
  }
}

async function runTask(task, sharedPreview) {
  const runner = SETTINGS_SMOKE_TASK_RUNNERS[task.taskId]
  if (!runner) {
    throw new Error(`Missing settings smoke runner for task: ${task.taskId}`)
  }

  const taskEnv = buildSettingsSmokeMatrixChildEnv(process.env, {
    baseUrl: sharedPreview.baseUrl,
    previewLogPath: sharedPreview.logPath,
    browserWsEndpoint: sharedPreview.browserWsEndpoint,
  })
  const { exitCode, log } = await withCapturedTaskOutput(
    task,
    () => withTaskEnv(taskEnv, runner)
  )

  const logPath = getSettingsSmokeMatrixLogPath(EVIDENCE_DIR, task.taskId)
  await writeFile(logPath, log, 'utf8')

  const evidencePaths = getSettingsSmokeTaskEvidencePaths(EVIDENCE_DIR, task.taskId)
  const summaryRaw = readOptionalFile(evidencePaths.summary)
  const summaryStatus = extractSettingsSmokeSummaryField(summaryRaw, 'status')
  const summaryError = extractSettingsSmokeSummaryField(summaryRaw, 'error')
  const status = exitCode === 0 && summaryStatus === 'passed'
    ? 'passed'
    : summaryStatus === 'blocked'
      ? 'blocked'
      : 'failed'

  process.stdout.write(`[settings-matrix] ${task.taskId}: ${status}\n`)

  return {
    taskId: task.taskId,
    label: task.label,
    status,
    reason: status === 'passed' ? '' : (summaryError || `child_exit_code=${exitCode}`),
    exitCode,
    command: `npm --prefix frontend run ${task.npmScript}`,
    evidence: path.relative(REPO_ROOT, evidencePaths.summary),
    jsonEvidence: path.relative(REPO_ROOT, evidencePaths.json),
    log: path.relative(REPO_ROOT, logPath),
    summaryExcerpt: summarizeSettingsSmokeText(summaryRaw),
  }
}

async function main() {
  const generatedAt = new Date().toISOString()
  const tasks = listSettingsSmokeTasks()
  const taskScope = tasks.map((task) => task.taskId).join(',')
  const sharedPreviewLogPath = path.join(EVIDENCE_DIR, 'task-21-settings-smoke-matrix-preview.log')

  await mkdir(EVIDENCE_DIR, { recursive: true })
  await runBuildWeb(FRONTEND_ROOT)
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t21', 'T21_PREVIEW_PORT'))
  const sharedPreview = {
    baseUrl: buildBaseUrl(previewPort),
    logPath: sharedPreviewLogPath,
  }

  const previewServer = startPreviewServer({
    frontendRoot: FRONTEND_ROOT,
    previewLogPath: sharedPreview.logPath,
    port: previewPort,
  })
  let browserServer = null

  const rows = []
  try {
    await waitForManagedPreviewServerReady(previewServer, `${sharedPreview.baseUrl}/`)
    const browserLibDir = buildBrowserLibDir(FRONTEND_ROOT)
    const browserServerEnv = fs.existsSync(browserLibDir)
      ? applyBrowserLibEnv(browserLibDir, process.env)
      : process.env
    browserServer = await chromium.launchServer({ env: browserServerEnv })
    sharedPreview.browserWsEndpoint = browserServer.wsEndpoint()
    for (const task of tasks) {
      rows.push(await runTask(task, sharedPreview))
    }
  } finally {
    await browserServer?.close()
    await stopPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  const matrixEvidencePaths = getSettingsSmokeMatrixEvidencePaths(EVIDENCE_DIR)
  const summary = buildSettingsSmokeMatrixSummary(rows, {
    generatedAt,
    source: SOURCE,
    taskScope,
  })

  await writeFile(matrixEvidencePaths.summary, summary, 'utf8')
  await writeFile(
    matrixEvidencePaths.json,
    `${JSON.stringify({
      generated_at: generatedAt,
      source: SOURCE,
      task_scope: taskScope,
      tasks: rows,
      counts: {
        passed: rows.filter((row) => row.status === 'passed').length,
        blocked: rows.filter((row) => row.status === 'blocked').length,
        failed: rows.filter((row) => row.status === 'failed').length,
      },
    }, null, 2)}\n`,
    'utf8'
  )

  process.stdout.write(summary)
  if (rows.some((row) => row.status === 'failed')) {
    process.exitCode = 1
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exit(1)
})
