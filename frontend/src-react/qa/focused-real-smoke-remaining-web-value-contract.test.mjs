import test from 'node:test'

import {
  assertFocusedRealSmokeGroupValueContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeRemainingWebValueContract,
  REMAINING_WEB_VALUE_CASES_BY_TASK_ID,
} from './focused-real-smoke-remaining-web-value-assertions.mjs'

test('remaining-web-focused focused real smoke scripts keep stable value bindings', async () => {
  await assertFocusedRealSmokeGroupValueContracts({
    groupName: 'remaining-web-focused',
    casesByTaskId: REMAINING_WEB_VALUE_CASES_BY_TASK_ID,
    label: 'remaining-web value cases',
    missingQaScriptLabel: 'remaining-web',
    assertContract: assertFocusedRealSmokeRemainingWebValueContract,
  })
})
