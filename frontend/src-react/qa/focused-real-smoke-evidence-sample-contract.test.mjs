import test from 'node:test'

import {
  HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
} from './focused-real-smoke-contract-case-registry.mjs'
import {
  assertFocusedRealSmokeSummaryPassed,
  readFocusedRealSmokeTaskEvidence,
} from './focused-real-smoke-contract-helpers.mjs'
import { assertFocusedRealSmokeEvidenceSample } from './focused-real-smoke-evidence-sample-assertions.mjs'

test('release-critical committed evidence samples keep stable semantic contracts', async () => {
  for (const taskId of HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS) {
    const { summary } = await readFocusedRealSmokeTaskEvidence(taskId)
    assertFocusedRealSmokeSummaryPassed(taskId, summary)
    assertFocusedRealSmokeEvidenceSample(taskId, await readFocusedRealSmokeTaskEvidence(taskId))
  }
})
