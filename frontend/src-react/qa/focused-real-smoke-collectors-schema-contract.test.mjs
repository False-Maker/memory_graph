import test from 'node:test'

import { assertFocusedRealSmokeGroupSchemaContracts } from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeCollectorsSchemaContract,
  COLLECTORS_FOCUSED_SCHEMA_CASES_BY_TASK_ID,
} from './focused-real-smoke-collectors-schema-assertions.mjs'

test('collectors-focused focused real smoke scripts keep stable summary/http schema keys', async () => {
  await assertFocusedRealSmokeGroupSchemaContracts({
    groupName: 'collectors-focused',
    casesByTaskId: COLLECTORS_FOCUSED_SCHEMA_CASES_BY_TASK_ID,
    label: 'collectors-focused schema cases',
    missingQaScriptLabel: 'collectors-focused',
    assertContract: assertFocusedRealSmokeCollectorsSchemaContract,
  })
})
