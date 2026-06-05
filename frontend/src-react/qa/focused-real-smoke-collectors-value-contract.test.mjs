import test from 'node:test'

import { assertFocusedRealSmokeGroupValueContracts } from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeCollectorsValueContract,
  COLLECTORS_FOCUSED_VALUE_CASES_BY_TASK_ID,
} from './focused-real-smoke-collectors-value-assertions.mjs'

test('collectors-focused focused real smoke scripts keep stable value bindings', async () => {
  await assertFocusedRealSmokeGroupValueContracts({
    groupName: 'collectors-focused',
    casesByTaskId: COLLECTORS_FOCUSED_VALUE_CASES_BY_TASK_ID,
    label: 'collectors-focused value cases',
    missingQaScriptLabel: 'collectors-focused',
    assertContract: assertFocusedRealSmokeCollectorsValueContract,
  })
})
