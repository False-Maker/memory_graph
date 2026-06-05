import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import { readFile } from 'node:fs/promises'

import { RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS } from './focused-real-smoke-task-registry.mjs'
import {
  extractTaskIdsFromArtifactPaths,
  parseFocusedSmokeWorkflowJobs,
  readContractGuardsWorkflowSource,
} from './workflow-focused-real-smoke-helpers.mjs'

const FRONTEND_PACKAGE_FILE = new URL('../../package.json', import.meta.url)
const QA_DIR_URL = new URL('./', import.meta.url)

test('release-critical focused smoke workflow preserves committed samples and runs compare for every task', async () => {
  const packageJson = JSON.parse(await readFile(FRONTEND_PACKAGE_FILE, 'utf8'))
  const scripts = packageJson.scripts || {}
  const workflowSource = await readContractGuardsWorkflowSource()
  const jobs = parseFocusedSmokeWorkflowJobs(workflowSource)
  const compareTaskIdsInWorkflow = new Set()

  for (const job of jobs) {
    for (const taskId of job.compareTaskIds) {
      compareTaskIdsInWorkflow.add(taskId)
    }

    if (job.compareTaskIds.length === 0) continue

    assert.equal(job.usesSharedReusableWorkflow, true, `${job.jobId} should use the shared focused-real-smoke reusable workflow`)
    assert.equal(job.usesSharedCompareAction, true, `${job.jobId} should use the shared focused-real-smoke compare action`)
    assert.equal(job.compareTaskIds.length, 1, `${job.jobId} should compare exactly one focused smoke task`)
    assert.equal(job.preservedTaskIds.length, 1, `${job.jobId} should preserve exactly one focused smoke task`)

    const [compareTaskId] = job.compareTaskIds
    const [preservedTaskId] = job.preservedTaskIds
    assert.equal(preservedTaskId, compareTaskId, `${job.jobId} preserve/compare task ids drifted`)

    const preservedKinds = job.preservedEvidenceByTask.get(compareTaskId)
    assert.equal(preservedKinds?.has('summary'), true, `${job.jobId} should preserve ${compareTaskId} summary sample`)
    assert.equal(preservedKinds?.has('http'), true, `${job.jobId} should preserve ${compareTaskId} http sample`)

    const artifactTaskIds = extractTaskIdsFromArtifactPaths(job.artifactPaths)
    assert.deepEqual(
      artifactTaskIds,
      [compareTaskId],
      `${job.jobId} artifact set should belong to the same focused smoke task`
    )

    assert.ok(job.realSmokeRunScript, `${job.jobId} is missing qa:real-stack-smoke run script`)
    const packageScript = scripts[job.realSmokeRunScript]
    assert.ok(packageScript?.startsWith('node src-react/qa/'), `${job.jobId} missing qa script for ${job.realSmokeRunScript}`)

    const qaScriptRelativePath = packageScript.replace(/^node\s+/, '')
    const qaScriptSource = await readFile(new URL(path.basename(qaScriptRelativePath), QA_DIR_URL), 'utf8')
    assert.match(
      qaScriptSource,
      new RegExp(`${compareTaskId}-`),
      `${job.jobId} qa script ${qaScriptRelativePath} does not reference ${compareTaskId} evidence`
    )
  }

  const expectedReleaseCriticalTaskIds = [...RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS].sort()
  const actualComparedTaskIds = [...compareTaskIdsInWorkflow].sort()

  assert.deepEqual(
    actualComparedTaskIds,
    expectedReleaseCriticalTaskIds,
    `contract-guards workflow compare coverage drifted for release-critical tasks`
  )
})
