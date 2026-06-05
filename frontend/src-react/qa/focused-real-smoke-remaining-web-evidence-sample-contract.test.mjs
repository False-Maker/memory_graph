import test from 'node:test'

import {
  assertFocusedRealSmokeGroupEvidenceSamples,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertRemainingWebFocusedEvidenceSample,
  REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-remaining-web-evidence-sample-assertions.mjs'

test('remaining-web-focused committed evidence samples keep stable semantic contracts', async () => {
  await assertFocusedRealSmokeGroupEvidenceSamples({
    groupName: 'remaining-web-focused',
    assertionTaskIds: REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    assertionsByTaskId: REMAINING_WEB_FOCUSED_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    mapLabel: 'remaining-web-focused evidence sample assertion map',
    driftMessage: 'remaining-web-focused evidence sample assertions drifted from the task group',
    assertEvidenceSample: assertRemainingWebFocusedEvidenceSample,
  })
})
