import path from 'node:path'
import { writeFile } from 'node:fs/promises'

const SETTINGS_SMOKE_TASKS = Object.freeze([
  Object.freeze({
    taskId: 't12',
    label: 'settings-core',
    npmScript: 'qa:settings-playwright:t12',
    directCommand: 'node src-react/qa/t12-settings-playwright.mjs',
    summaryStem: 'task-12-settings',
  }),
  Object.freeze({
    taskId: 't19',
    label: 'settings-recovery-dry-run',
    npmScript: 'qa:settings-playwright:t19',
    directCommand: 'node src-react/qa/t19-settings-recovery-playwright.mjs',
    summaryStem: 'task-19-settings-recovery',
  }),
  Object.freeze({
    taskId: 't20',
    label: 'settings-reindex',
    npmScript: 'qa:settings-playwright:t20',
    directCommand: 'node src-react/qa/t20-settings-reindex-playwright.mjs',
    summaryStem: 'task-20-settings-reindex',
  }),
])

function normalizeOptionalValue(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

function normalizeList(values) {
  if (!Array.isArray(values)) {
    return []
  }
  return values
    .map((value) => normalizeOptionalValue(value))
    .filter(Boolean)
}

export function listSettingsSmokeTasks() {
  return SETTINGS_SMOKE_TASKS.map((task) => ({ ...task }))
}

export function getSettingsSmokeTask(taskId) {
  return SETTINGS_SMOKE_TASKS.find((task) => task.taskId === taskId) || null
}

export function extractSettingsSmokeSummaryField(raw, field) {
  if (typeof raw !== 'string') {
    return ''
  }

  const match = raw.match(new RegExp(`^${field}=(.*)$`, 'm'))
  return match ? match[1] : ''
}

export function getSettingsSmokeTaskEvidencePaths(evidenceDir, taskId) {
  const task = getSettingsSmokeTask(taskId)
  if (!task) {
    throw new Error(`Unknown settings smoke task: ${taskId}`)
  }

  return {
    summary: path.join(evidenceDir, `${task.summaryStem}-summary.txt`),
    json: path.join(evidenceDir, `${task.summaryStem}-summary.json`),
  }
}

export function getSettingsSmokeMatrixEvidencePaths(evidenceDir) {
  return {
    summary: path.join(evidenceDir, 'task-21-settings-smoke-matrix-summary.txt'),
    json: path.join(evidenceDir, 'task-21-settings-smoke-matrix-summary.json'),
  }
}

export function getSettingsSmokeMatrixLogPath(evidenceDir, taskId) {
  const task = getSettingsSmokeTask(taskId)
  if (!task) {
    throw new Error(`Unknown settings smoke task: ${taskId}`)
  }

  return path.join(evidenceDir, `task-21-settings-smoke-matrix-${task.taskId}.log`)
}

export function summarizeSettingsSmokeText(raw, maxLines = 4) {
  if (typeof raw !== 'string' || !raw.trim()) {
    return ''
  }

  return raw
    .trim()
    .split('\n')
    .slice(0, maxLines)
    .join(' | ')
}

export function buildSettingsSmokeTaskSummary(result) {
  const task = getSettingsSmokeTask(result.taskId)
  if (!task) {
    throw new Error(`Unknown settings smoke task: ${result.taskId}`)
  }

  const artifacts = normalizeList(result.artifacts)
  const scenarios = normalizeList(result.scenarios)
  const lines = [
    `task=${task.taskId}`,
    `label=${task.label}`,
    `status=${normalizeOptionalValue(result.status) || 'failed'}`,
    `generated_at=${normalizeOptionalValue(result.generatedAt)}`,
    `command=${normalizeOptionalValue(result.command) || task.directCommand}`,
    `exit_code=${Number.isInteger(result.exitCode) ? result.exitCode : 1}`,
    `scenario_count=${scenarios.length}`,
    `scenarios=${scenarios.join(',')}`,
    `artifact_count=${artifacts.length}`,
    `artifacts=${artifacts.join(',')}`,
    `error=${normalizeOptionalValue(result.error)}`,
    `notes=${normalizeOptionalValue(result.notes)}`,
  ]

  return `${lines.join('\n')}\n`
}

export async function writeSettingsSmokeTaskEvidence(evidenceDir, result) {
  const paths = getSettingsSmokeTaskEvidencePaths(evidenceDir, result.taskId)
  const task = getSettingsSmokeTask(result.taskId)
  const payload = {
    task_id: task.taskId,
    label: task.label,
    status: normalizeOptionalValue(result.status) || 'failed',
    generated_at: normalizeOptionalValue(result.generatedAt),
    command: normalizeOptionalValue(result.command) || task.directCommand,
    exit_code: Number.isInteger(result.exitCode) ? result.exitCode : 1,
    scenarios: normalizeList(result.scenarios),
    artifacts: normalizeList(result.artifacts),
    error: normalizeOptionalValue(result.error),
    notes: normalizeOptionalValue(result.notes),
  }

  await writeFile(paths.summary, buildSettingsSmokeTaskSummary(result), 'utf8')
  await writeFile(`${paths.json}`, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')

  return paths
}

export function buildSettingsSmokeMatrixSummary(rows, meta = {}) {
  const lines = []

  if (normalizeOptionalValue(meta.generatedAt)) {
    lines.push(`generated_at=${normalizeOptionalValue(meta.generatedAt)}`)
  }
  if (normalizeOptionalValue(meta.source)) {
    lines.push(`source=${normalizeOptionalValue(meta.source)}`)
  }
  if (normalizeOptionalValue(meta.taskScope)) {
    lines.push(`task_scope=${normalizeOptionalValue(meta.taskScope)}`)
  }
  if (lines.length > 0) {
    lines.push('')
  }

  for (const row of rows) {
    lines.push(`task=${row.taskId}`)
    lines.push(`label=${row.label || ''}`)
    lines.push(`status=${row.status}`)
    lines.push(`reason=${row.reason || ''}`)
    lines.push(`exit_code=${row.exitCode}`)
    lines.push(`command=${row.command}`)
    lines.push(`evidence=${row.evidence || ''}`)
    lines.push(`json_evidence=${row.jsonEvidence || ''}`)
    lines.push(`log=${row.log || ''}`)
    lines.push(`summary_excerpt=${row.summaryExcerpt || ''}`)
    lines.push('')
  }

  lines.push(`passed_count=${rows.filter((row) => row.status === 'passed').length}`)
  lines.push(`blocked_count=${rows.filter((row) => row.status === 'blocked').length}`)
  lines.push(`failed_count=${rows.filter((row) => row.status === 'failed').length}`)

  return `${lines.join('\n')}\n`
}
