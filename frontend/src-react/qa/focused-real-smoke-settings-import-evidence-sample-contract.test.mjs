import test from 'node:test'

import {
  assertFocusedRealSmokeGroupEvidenceSamples,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  assertSettingsImportEvidenceSample,
  SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
  SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
} from './focused-real-smoke-settings-import-evidence-sample-assertions.mjs'

test('settings-import-focused committed evidence samples keep stable semantic contracts', async () => {
  await assertFocusedRealSmokeGroupEvidenceSamples({
    groupName: 'settings-import-focused',
    assertionTaskIds: SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS,
    assertionsByTaskId: SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    mapLabel: 'settings-import-focused evidence sample assertion map',
    driftMessage: 'settings-import-focused evidence sample assertions drifted from the task group',
    assertEvidenceSample: assertSettingsImportEvidenceSample,
  })
})
