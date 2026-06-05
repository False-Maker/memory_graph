import test from 'node:test'
import assert from 'node:assert/strict'
import { mkdtemp, readFile, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import {
  DEFAULT_EVIDENCE_DIR,
  TASK_CASES,
  TASK_GROUPS,
  compareFocusedRealSmokeEvidence,
} from './focused-real-smoke-fresh-evidence-compare.mjs'

async function cloneTaskEvidence(taskId, targetDir) {
  const { summaryFile, httpFile } = TASK_CASES[taskId]
  for (const fileName of [summaryFile, httpFile]) {
    const sourcePath = path.join(DEFAULT_EVIDENCE_DIR, fileName)
    const targetPath = path.join(targetDir, fileName)
    await writeFile(targetPath, await readFile(sourcePath, 'utf8'), 'utf8')
  }
}

async function writeJson(filePath, value) {
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
}

test('fresh evidence compare helper accepts committed release-critical samples', async () => {
  const results = await compareFocusedRealSmokeEvidence({
    baselineDir: DEFAULT_EVIDENCE_DIR,
    freshDir: DEFAULT_EVIDENCE_DIR,
    groupNames: ['release-critical'],
  })

  assert.equal(results.length, TASK_GROUPS['release-critical'].length)
})

test('task-24 compare ignores runtime-only drift but catches semantic drift', async () => {
  const baselineDir = await mkdtemp(path.join(os.tmpdir(), 'fresh-evidence-compare-baseline-'))
  const freshDir = await mkdtemp(path.join(os.tmpdir(), 'fresh-evidence-compare-fresh-'))
  const taskId = 'task-24'

  await cloneTaskEvidence(taskId, baselineDir)
  await cloneTaskEvidence(taskId, freshDir)

  const summaryPath = path.join(freshDir, TASK_CASES[taskId].summaryFile)
  const runtimeOnlySummary = JSON.parse(await readFile(summaryPath, 'utf8'))
  runtimeOnlySummary.generated_at = '2030-01-01T00:00:00.000Z'
  runtimeOnlySummary.backend_base_url = 'http://127.0.0.1:49999'
  runtimeOnlySummary.config_path = '/tmp/another-run/config/settings.yaml'
  await writeJson(summaryPath, runtimeOnlySummary)

  await compareFocusedRealSmokeEvidence({
    baselineDir,
    freshDir,
    taskIds: [taskId],
  })

  const driftedSummary = JSON.parse(await readFile(summaryPath, 'utf8'))
  driftedSummary.community_link_surfaces_tested = ['source']
  await writeJson(summaryPath, driftedSummary)

  await assert.rejects(
    compareFocusedRealSmokeEvidence({
      baselineDir,
      freshDir,
      taskIds: [taskId],
    }),
    /task-24 fresh evidence diverged from committed sample/
  )
})

test('task-45 compare ignores runtime-only drift but catches dashboard failure semantic drift', async () => {
  const baselineDir = await mkdtemp(path.join(os.tmpdir(), 'fresh-evidence-compare-dashboard-baseline-'))
  const freshDir = await mkdtemp(path.join(os.tmpdir(), 'fresh-evidence-compare-dashboard-fresh-'))
  const taskId = 'task-45'

  await cloneTaskEvidence(taskId, baselineDir)
  await cloneTaskEvidence(taskId, freshDir)

  const summaryPath = path.join(freshDir, TASK_CASES[taskId].summaryFile)
  const runtimeOnlySummary = JSON.parse(await readFile(summaryPath, 'utf8'))
  runtimeOnlySummary.generated_at = '2031-02-03T04:05:06.000Z'
  runtimeOnlySummary.backend_base_url = 'http://127.0.0.1:49998'
  runtimeOnlySummary.config_path = '/tmp/dashboard-failure-compare/settings.yaml'
  await writeJson(summaryPath, runtimeOnlySummary)

  await compareFocusedRealSmokeEvidence({
    baselineDir,
    freshDir,
    taskIds: [taskId],
  })

  const driftedSummary = JSON.parse(await readFile(summaryPath, 'utf8'))
  driftedSummary.refreshed_dashboard_empty = false
  await writeJson(summaryPath, driftedSummary)

  await assert.rejects(
    compareFocusedRealSmokeEvidence({
      baselineDir,
      freshDir,
      taskIds: [taskId],
    }),
    /task-45 fresh evidence diverged from committed sample/
  )
})

test('task-22 compare ignores runtime-only drift but catches settings secret-store semantic drift', async () => {
  const baselineDir = await mkdtemp(path.join(os.tmpdir(), 'fresh-evidence-compare-settings-baseline-'))
  const freshDir = await mkdtemp(path.join(os.tmpdir(), 'fresh-evidence-compare-settings-fresh-'))
  const taskId = 'task-22'

  await cloneTaskEvidence(taskId, baselineDir)
  await cloneTaskEvidence(taskId, freshDir)

  const summaryPath = path.join(freshDir, TASK_CASES[taskId].summaryFile)
  const runtimeOnlySummary = JSON.parse(await readFile(summaryPath, 'utf8'))
  runtimeOnlySummary.generated_at = '2032-03-04T05:06:07.000Z'
  runtimeOnlySummary.backend_base_url = 'http://127.0.0.1:49997'
  runtimeOnlySummary.config_path = '/tmp/secret-store-compare/settings.yaml'
  runtimeOnlySummary.secret_store_env.MEMORY_GRAPH_SETTINGS_PATH = '/tmp/secret-store-compare/settings.yaml'
  await writeJson(summaryPath, runtimeOnlySummary)

  await compareFocusedRealSmokeEvidence({
    baselineDir,
    freshDir,
    taskIds: [taskId],
  })

  const driftedSummary = JSON.parse(await readFile(summaryPath, 'utf8'))
  driftedSummary.direct_put_code = 'unexpected_code'
  await writeJson(summaryPath, driftedSummary)

  await assert.rejects(
    compareFocusedRealSmokeEvidence({
      baselineDir,
      freshDir,
      taskIds: [taskId],
    }),
    /task-22 fresh evidence diverged from committed sample/
  )
})
