import test from 'node:test'
import {
  assertHighSignalFocusedRealSmokeValueContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeValueContract,
  VALUE_CONTRACT_CASES_BY_TASK_ID,
} from './focused-real-smoke-value-assertions.mjs'

test('release-critical focused real smoke scripts keep stable high-signal evidence value bindings', async () => {
  await assertHighSignalFocusedRealSmokeValueContracts({
    casesByTaskId: VALUE_CONTRACT_CASES_BY_TASK_ID,
    label: 'release-critical high-signal value cases',
    assertContract: assertFocusedRealSmokeValueContract,
  })
})
