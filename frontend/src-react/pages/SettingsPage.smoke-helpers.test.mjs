import test from 'node:test'
import assert from 'node:assert/strict'

import { getSettingsSmokeTestId, SETTINGS_SMOKE_TEST_IDS } from './SettingsPage.smoke-helpers.js'

test('settings smoke ids expose stable selectors', () => {
  assert.equal(getSettingsSmokeTestId('globalErrorAlert'), 'settings-global-error-alert')
  assert.equal(getSettingsSmokeTestId('diagnosticsSection'), 'settings-diagnostics-section')
  assert.equal(getSettingsSmokeTestId('diagnosticsSummary'), 'settings-diagnostics-summary')
  assert.equal(getSettingsSmokeTestId('secretStorageStatus'), 'settings-secret-storage-status')
  assert.equal(getSettingsSmokeTestId('exportButton'), 'settings-export-button')
  assert.equal(getSettingsSmokeTestId('reindexResult'), 'settings-reindex-result')
})

test('unknown settings smoke ids return null', () => {
  assert.equal(getSettingsSmokeTestId('missingKey'), null)
})

test('settings smoke ids stay unique', () => {
  const values = Object.values(SETTINGS_SMOKE_TEST_IDS)
  assert.equal(new Set(values).size, values.length)
})
