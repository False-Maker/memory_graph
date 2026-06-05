import test from 'node:test'

import {
  assertFocusedRealSmokeGroupValueContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeSettingsImportValueContract,
  SETTINGS_IMPORT_VALUE_CASES_BY_TASK_ID,
} from './focused-real-smoke-settings-import-value-assertions.mjs'

test('settings-import-focused focused real smoke scripts keep stable value bindings', async () => {
  await assertFocusedRealSmokeGroupValueContracts({
    groupName: 'settings-import-focused',
    casesByTaskId: SETTINGS_IMPORT_VALUE_CASES_BY_TASK_ID,
    label: 'settings-import value cases',
    missingQaScriptLabel: 'settings-import',
    assertContract: assertFocusedRealSmokeSettingsImportValueContract,
  })
})
