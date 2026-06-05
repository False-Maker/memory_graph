import test from 'node:test'

import {
  assertFocusedRealSmokeGroupSchemaContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeDashboardSchemaContract,
  DASHBOARD_SCHEMA_CASES_BY_TASK_ID,
} from './focused-real-smoke-dashboard-schema-assertions.mjs'

test('dashboard-adjacent focused real smoke scripts keep stable summary/http schema keys', async () => {
  await assertFocusedRealSmokeGroupSchemaContracts({
    groupName: 'dashboard-adjacent',
    casesByTaskId: DASHBOARD_SCHEMA_CASES_BY_TASK_ID,
    label: 'dashboard-adjacent schema cases',
    missingQaScriptLabel: 'dashboard',
    assertContract: assertFocusedRealSmokeDashboardSchemaContract,
  })
})
