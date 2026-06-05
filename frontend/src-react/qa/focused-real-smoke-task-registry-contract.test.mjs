import test from 'node:test'
import assert from 'node:assert/strict'

import { TASK_CASES } from './focused-real-smoke-fresh-evidence-compare.mjs'
import {
  getFocusedRealSmokeEvidenceFiles,
  FOCUSED_REAL_SMOKE_TASK_GROUPS,
  FOCUSED_REAL_SMOKE_WORKFLOW_JOBS,
  RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
} from './focused-real-smoke-task-registry.mjs'
import {
  assertMappedUniqueValues,
  assertSortedUniqueValuesMatch,
  assertUniqueValues,
} from './focused-real-smoke-registry-test-helpers.mjs'

test('focused real smoke task registry stays unique and compare helper covers every release-critical task', () => {
  for (const [groupName, taskIds] of Object.entries(FOCUSED_REAL_SMOKE_TASK_GROUPS)) {
    assertUniqueValues(taskIds, `${groupName} task ids`)
  }

  assertSortedUniqueValuesMatch(
    Object.keys(TASK_CASES),
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
    'focused smoke task registry drifted from compare helper task coverage'
  )

  assertMappedUniqueValues(
    FOCUSED_REAL_SMOKE_WORKFLOW_JOBS,
    (job) => job.jobId,
    'focused smoke workflow metadata job ids'
  )
  assertSortedUniqueValuesMatch(
    FOCUSED_REAL_SMOKE_WORKFLOW_JOBS.map((job) => job.taskId),
    RELEASE_CRITICAL_FOCUSED_REAL_SMOKE_TASK_IDS,
    'focused smoke workflow metadata drifted from release-critical task registry'
  )

  for (const job of FOCUSED_REAL_SMOKE_WORKFLOW_JOBS) {
    assert.deepEqual(getFocusedRealSmokeEvidenceFiles(job.taskId), {
      summaryFile: `${job.evidencePrefix}-summary.json`,
      httpFile: `${job.evidencePrefix}-http.json`,
    })
  }
})
