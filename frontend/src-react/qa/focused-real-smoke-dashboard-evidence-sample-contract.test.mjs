import test from 'node:test'

import {
  assertFocusedRealSmokeGroupEvidenceSamples,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertDashboardAdjacentEvidenceSample,
  DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-dashboard-evidence-sample-assertions.mjs'

test('dashboard-adjacent committed evidence samples keep stable semantic contracts', async () => {
  await assertFocusedRealSmokeGroupEvidenceSamples({
    groupName: 'dashboard-adjacent',
    assertionTaskIds: DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    assertionsByTaskId: DASHBOARD_ADJACENT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    mapLabel: 'dashboard-adjacent evidence sample assertion map',
    driftMessage: 'dashboard-adjacent evidence sample assertions drifted from the dashboard task group',
    assertEvidenceSample: assertDashboardAdjacentEvidenceSample,
  })
})
