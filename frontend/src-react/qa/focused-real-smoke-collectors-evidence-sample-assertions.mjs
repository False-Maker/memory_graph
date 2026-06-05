import assert from 'node:assert/strict'

import {
  assertFocusedRealSmokeEvidenceSampleCase,
  getFocusedRealSmokeTaskGroupTaskIds,
} from './focused-real-smoke-contract-helpers.mjs'

export const COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID = Object.freeze({
  'task-61': (evidence) => {
    assert.equal(evidence.command, 'npm --prefix frontend run qa:real-stack-smoke:collectors:official')
    assert.equal(evidence.status, 'passed')
    assert.equal(evidence.health_status, 'healthy')
    assert.equal(evidence.start_status, 'started')
    assert.equal(evidence.stop_status, 'stopped')
    assert.deepEqual(
      evidence.task_statuses,
      [
        { collector: 'windsurf', support_tier: 'official', status: 'passed' },
        { collector: 'claude_code', support_tier: 'official', status: 'passed' },
        { collector: 'aider', support_tier: 'official', status: 'passed' },
      ]
    )
    assert.deepEqual(
      evidence.processed_counts,
      [
        { collector: 'windsurf', processed_count: 1 },
        { collector: 'claude_code', processed_count: 1 },
        { collector: 'aider', processed_count: 1 },
      ]
    )
    assert.equal(evidence.passed_count, 3)
    assert.equal(evidence.failed_count, 0)
  },
})

export const COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS = Object.freeze(
  getFocusedRealSmokeTaskGroupTaskIds('collectors-focused')
)

export function assertCollectorsFocusedEvidenceSample(taskId, normalized) {
  assertFocusedRealSmokeEvidenceSampleCase(
    taskId,
    normalized,
    COLLECTORS_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    'collectors-focused evidence sample assertion'
  )
}
