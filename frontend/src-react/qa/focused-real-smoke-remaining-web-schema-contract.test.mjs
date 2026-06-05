import test from 'node:test'

import {
  assertFocusedRealSmokeGroupSchemaContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeRemainingWebSchemaContract,
  REMAINING_WEB_SCHEMA_CASES_BY_TASK_ID,
} from './focused-real-smoke-remaining-web-schema-assertions.mjs'

test('remaining-web-focused focused real smoke scripts keep stable summary/http schema keys', async () => {
  await assertFocusedRealSmokeGroupSchemaContracts({
    groupName: 'remaining-web-focused',
    casesByTaskId: REMAINING_WEB_SCHEMA_CASES_BY_TASK_ID,
    label: 'remaining-web schema cases',
    missingQaScriptLabel: 'remaining-web',
    assertContract: assertFocusedRealSmokeRemainingWebSchemaContract,
  })
})
