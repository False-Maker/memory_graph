import test from 'node:test'
import assert from 'node:assert/strict'

import { DIAGNOSTICS_SMOKE_TEST_IDS, getDiagnosticsSmokeTestId } from './DiagnosticsPage.smoke-helpers.js'

test('diagnostics smoke ids expose stable selectors', () => {
  assert.equal(getDiagnosticsSmokeTestId('page'), 'diagnostics-page')
  assert.equal(getDiagnosticsSmokeTestId('tabQueryRuns'), 'diagnostics-tab-query-runs')
  assert.equal(getDiagnosticsSmokeTestId('queryRunDetail'), 'diagnostics-query-run-detail')
  assert.equal(getDiagnosticsSmokeTestId('failuresSection'), 'diagnostics-failures-section')
})

test('diagnostics smoke ids stay unique', () => {
  const values = Object.values(DIAGNOSTICS_SMOKE_TEST_IDS)
  assert.equal(new Set(values).size, values.length)
})

test('unknown diagnostics smoke ids return null', () => {
  assert.equal(getDiagnosticsSmokeTestId('missing'), null)
})
