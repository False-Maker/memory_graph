import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { TASK_CASES } from './focused-real-smoke-compare-cases/index.mjs'
import { FOCUSED_REAL_SMOKE_TASK_GROUPS } from './focused-real-smoke-task-registry.mjs'

const REPO_ROOT = path.resolve(fileURLToPath(new URL('../../../', import.meta.url)))

export const DEFAULT_EVIDENCE_DIR = path.join(REPO_ROOT, '.sisyphus', 'evidence')
export const TASK_GROUPS = FOCUSED_REAL_SMOKE_TASK_GROUPS
export { TASK_CASES }

async function readJson(filePath) {
  return JSON.parse(await readFile(filePath, 'utf8'))
}

export function resolveTaskIds({ taskIds = [], groupNames = [] } = {}) {
  const resolved = []

  for (const groupName of groupNames) {
    const groupTaskIds = TASK_GROUPS[groupName]
    assert.ok(groupTaskIds, `Unknown focused smoke evidence group: ${groupName}`)
    resolved.push(...groupTaskIds)
  }

  resolved.push(...taskIds)

  const unique = [...new Set(resolved)]
  const finalTaskIds = unique.length > 0 ? unique : TASK_GROUPS['release-critical']

  for (const taskId of finalTaskIds) {
    assert.ok(TASK_CASES[taskId], `Unknown focused smoke evidence task: ${taskId}`)
  }

  return finalTaskIds
}

export async function compareTaskEvidence({ taskId, baselineDir = DEFAULT_EVIDENCE_DIR, freshDir = DEFAULT_EVIDENCE_DIR }) {
  const taskCase = TASK_CASES[taskId]
  assert.ok(taskCase, `Unknown focused smoke evidence task: ${taskId}`)

  const baselineSummary = await readJson(path.join(baselineDir, taskCase.summaryFile))
  const baselineHttp = await readJson(path.join(baselineDir, taskCase.httpFile))
  const freshSummary = await readJson(path.join(freshDir, taskCase.summaryFile))
  const freshHttp = await readJson(path.join(freshDir, taskCase.httpFile))

  const baselineNormalized = taskCase.normalize({ summary: baselineSummary, http: baselineHttp })
  const freshNormalized = taskCase.normalize({ summary: freshSummary, http: freshHttp })

  assert.deepEqual(
    freshNormalized,
    baselineNormalized,
    `${taskId} fresh evidence diverged from committed sample`
  )

  return {
    taskId,
    summaryFile: taskCase.summaryFile,
    httpFile: taskCase.httpFile,
    normalized: freshNormalized,
  }
}

export async function compareFocusedRealSmokeEvidence({
  baselineDir = DEFAULT_EVIDENCE_DIR,
  freshDir = DEFAULT_EVIDENCE_DIR,
  taskIds = [],
  groupNames = [],
} = {}) {
  const resolvedTaskIds = resolveTaskIds({ taskIds, groupNames })
  const results = []

  for (const taskId of resolvedTaskIds) {
    results.push(await compareTaskEvidence({ taskId, baselineDir, freshDir }))
  }

  return results
}

function parseArgs(argv) {
  function resolveCliPath(value) {
    return path.isAbsolute(value) ? value : path.resolve(REPO_ROOT, value)
  }

  const parsed = {
    baselineDir: DEFAULT_EVIDENCE_DIR,
    freshDir: DEFAULT_EVIDENCE_DIR,
    taskIds: [],
    groupNames: [],
  }

  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index]

    if (argument === '--baseline-dir') {
      parsed.baselineDir = resolveCliPath(argv[index + 1])
      index += 1
      continue
    }
    if (argument === '--fresh-dir') {
      parsed.freshDir = resolveCliPath(argv[index + 1])
      index += 1
      continue
    }
    if (argument === '--task') {
      parsed.taskIds.push(argv[index + 1])
      index += 1
      continue
    }
    if (argument === '--tasks') {
      parsed.taskIds.push(...String(argv[index + 1] || '').split(',').map((item) => item.trim()).filter(Boolean))
      index += 1
      continue
    }
    if (argument === '--group') {
      parsed.groupNames.push(argv[index + 1])
      index += 1
      continue
    }

    throw new Error(`Unknown argument: ${argument}`)
  }

  return parsed
}

async function main() {
  const parsed = parseArgs(process.argv.slice(2))
  const results = await compareFocusedRealSmokeEvidence(parsed)
  process.stdout.write(
    `fresh-evidence-compare=passed\ntasks=${results.map((result) => result.taskId).join(',')}\n`
  )
}

const isDirectRun = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (isDirectRun) {
  await main()
}
