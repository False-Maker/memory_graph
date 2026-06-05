import test from 'node:test'
import assert from 'node:assert/strict'

import { RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS } from './focused-real-smoke-task-registry.mjs'
import {
  parseFocusedSmokeWorkflowJobs,
  readContractGuardsWorkflowSource,
} from './workflow-focused-real-smoke-helpers.mjs'

const RELEASE_CRITICAL_TASK_IDS = new Set(RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS)

test('release-critical compare-enabled focused smoke jobs use the shared upload action', async () => {
  const workflowSource = await readContractGuardsWorkflowSource()
  const jobs = parseFocusedSmokeWorkflowJobs(workflowSource)
  const coveredTaskIds = new Set()

  for (const job of jobs) {
    if (job.compareTaskIds.length !== 1) continue
    const [taskId] = job.compareTaskIds
    if (!RELEASE_CRITICAL_TASK_IDS.has(taskId)) continue

    coveredTaskIds.add(taskId)
    assert.equal(job.usesSharedReusableWorkflow, true, `${job.jobId} should use the shared focused-real-smoke reusable workflow`)
    assert.equal(job.usesSharedUploadAction, true, `${job.jobId} should use the shared focused-real-smoke upload action`)
  }

  assert.deepEqual([...coveredTaskIds].sort(), [...RELEASE_CRITICAL_TASK_IDS].sort())
})
