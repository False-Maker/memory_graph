import test from 'node:test'
import assert from 'node:assert/strict'

import { getImportSmokeTestId, IMPORT_SMOKE_TEST_IDS } from './ImportPage.smoke-helpers.js'

test('import smoke ids expose stable selectors', () => {
  assert.equal(getImportSmokeTestId('diagnosticsCard'), 'import-diagnostics-card')
  assert.equal(getImportSmokeTestId('diagnosticsSummary'), 'import-diagnostics-summary')
  assert.equal(getImportSmokeTestId('diagnosticsRefreshButton'), 'import-diagnostics-refresh')
})

test('unknown import smoke ids return null', () => {
  assert.equal(getImportSmokeTestId('missing'), null)
})

test('import smoke ids stay unique', () => {
  const values = Object.values(IMPORT_SMOKE_TEST_IDS)
  assert.equal(new Set(values).size, values.length)
})
