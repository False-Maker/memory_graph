import test from 'node:test'
import assert from 'node:assert/strict'

import {
  extractFocusedRealSmokeWorkflowBlock,
  renderFocusedRealSmokeWorkflowBlock,
} from './focused-real-smoke-workflow-manifest.mjs'
import {
  FOCUSED_REAL_SMOKE_WORKFLOW_JOBS,
  RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
} from './focused-real-smoke-task-registry.mjs'
import {
  assertMappedUniqueValues,
  assertSortedUniqueValuesMatch,
} from './focused-real-smoke-registry-test-helpers.mjs'
import { readContractGuardsWorkflowSource } from './workflow-focused-real-smoke-helpers.mjs'

test('focused real smoke workflow manifest stays unique and aligned with release-critical compare coverage', () => {
  assertMappedUniqueValues(
    FOCUSED_REAL_SMOKE_WORKFLOW_JOBS,
    (job) => job.jobId,
    'focused smoke workflow manifest job ids'
  )
  assertMappedUniqueValues(
    FOCUSED_REAL_SMOKE_WORKFLOW_JOBS,
    (job) => job.taskId,
    'focused smoke workflow manifest task ids'
  )
  assertSortedUniqueValuesMatch(
    FOCUSED_REAL_SMOKE_WORKFLOW_JOBS.map((job) => job.taskId),
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
    'focused smoke workflow manifest drifted from release-critical compare coverage'
  )
})

test('contract guard workflow keeps the generated focused real smoke block in sync with the manifest', async () => {
  const workflowSource = await readContractGuardsWorkflowSource()

  assert.equal(extractFocusedRealSmokeWorkflowBlock(workflowSource), renderFocusedRealSmokeWorkflowBlock())
})
