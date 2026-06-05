import test from 'node:test'
import {
  assertHighSignalFocusedRealSmokeSchemaContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeSchemaContract,
  SCHEMA_CASES_BY_TASK_ID,
} from './focused-real-smoke-schema-assertions.mjs'

test('release-critical focused real smoke scripts keep stable summary/http schema keys', async () => {
  await assertHighSignalFocusedRealSmokeSchemaContracts({
    casesByTaskId: SCHEMA_CASES_BY_TASK_ID,
    label: 'release-critical high-signal schema cases',
    assertContract: assertFocusedRealSmokeSchemaContract,
  })
})
