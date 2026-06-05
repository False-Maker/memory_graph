import test from 'node:test'

import {
  assertFocusedRealSmokeGroupSchemaContracts,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertFocusedRealSmokeSettingsImportSchemaContract,
  SETTINGS_IMPORT_SCHEMA_CASES_BY_TASK_ID,
} from './focused-real-smoke-settings-import-schema-assertions.mjs'

test('settings-import-focused focused real smoke scripts keep stable summary/http schema keys', async () => {
  await assertFocusedRealSmokeGroupSchemaContracts({
    groupName: 'settings-import-focused',
    casesByTaskId: SETTINGS_IMPORT_SCHEMA_CASES_BY_TASK_ID,
    label: 'settings-import schema cases',
    missingQaScriptLabel: 'settings-import',
    assertContract: assertFocusedRealSmokeSettingsImportSchemaContract,
  })
})
