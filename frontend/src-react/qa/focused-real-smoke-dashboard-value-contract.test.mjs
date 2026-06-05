import test from 'node:test'

import {
  assertFocusedRealSmokeGroupValueContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeDashboardValueContract,
  DASHBOARD_VALUE_CASES_BY_TASK_ID,
} from './focused-real-smoke-dashboard-value-assertions.mjs'

test('dashboard-adjacent focused real smoke scripts keep stable value bindings', async () => {
  await assertFocusedRealSmokeGroupValueContracts({
    groupName: 'dashboard-adjacent',
    casesByTaskId: DASHBOARD_VALUE_CASES_BY_TASK_ID,
    label: 'dashboard-adjacent value cases',
    missingQaScriptLabel: 'dashboard',
    assertContract: assertFocusedRealSmokeDashboardValueContract,
  })
})
