import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSettingsImportDiagnosticsEvidenceAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'
import {
  buildSettingsImportDiagnosticsNormalizeFragment,
  buildSettingsImportDiagnosticsSummaryKeys,
  buildSettingsImportDiagnosticsValuePatterns,
} from './focused-real-smoke-settings-import-diagnostics-contract-helpers.mjs'

test('buildSettingsImportDiagnosticsNormalizeFragment supports prefixed diagnostics snapshots', () => {
  const result = buildSettingsImportDiagnosticsNormalizeFragment({
    summary: {
      initial_diagnostics_status: 'unhealthy',
      initial_provider_ok: false,
    },
    diagnostics: {
      checks: {
        provider: { ok: false },
      },
      task_chain: { status: 'not_configured' },
    },
    summaryStatusKey: 'initial_diagnostics_status',
    summaryProviderOkKey: 'initial_provider_ok',
    providerOkField: 'initial_diagnostics_provider_ok',
    taskChainStatusField: 'initial_task_chain_status',
  })

  assert.deepEqual(result, {
    initial_diagnostics_status: 'unhealthy',
    initial_provider_ok: false,
    initial_diagnostics_provider_ok: false,
    initial_task_chain_status: 'not_configured',
  })
})

test('buildSettingsImportDiagnosticsSummaryKeys composes diagnostics summary key fragments', () => {
  const result = buildSettingsImportDiagnosticsSummaryKeys({
    statusKey: 'diagnostics_status',
    providerOkKey: 'provider_ok',
    taskChainStatusKey: 'task_chain_status',
    configuredSourcesKey: 'task_chain_configured_sources',
    conflictsKey: 'task_chain_conflicts',
    recentFailuresCountKey: 'recent_failures_count',
    extraKeys: ['fake_ollama_tag_requests'],
  })

  assert.deepEqual(result, [
    'diagnostics_status',
    'provider_ok',
    'task_chain_status',
    'task_chain_configured_sources',
    'task_chain_conflicts',
    'recent_failures_count',
    'fake_ollama_tag_requests',
  ])
})

test('buildSettingsImportDiagnosticsValuePatterns composes diagnostics regex fragments', () => {
  const result = buildSettingsImportDiagnosticsValuePatterns({
    statusPattern: /diagnostics_status:\s*httpEvidence\.diagnostics\.json\?\.status/,
    providerOkPattern: /provider_ok:\s*httpEvidence\.diagnostics\.json\?\.checks\?\.provider\?\.ok/,
    taskChainStatusPattern: /task_chain_status:\s*httpEvidence\.diagnostics\.json\?\.task_chain\?\.status/,
    patterns: [/diagnostics:\s*httpEvidence\.diagnostics\.json/],
  })

  assert.equal(result.length, 4)
  assert.match('diagnostics_status: httpEvidence.diagnostics.json?.status', result[0])
  assert.match('provider_ok: httpEvidence.diagnostics.json?.checks?.provider?.ok', result[1])
  assert.match('task_chain_status: httpEvidence.diagnostics.json?.task_chain?.status', result[2])
  assert.match('diagnostics: httpEvidence.diagnostics.json', result[3])
})

test('buildSettingsImportDiagnosticsEvidenceAssertion asserts health provider and configured fields', () => {
  const assertion = buildSettingsImportDiagnosticsEvidenceAssertion('task-settings-diagnostics', {
    label: 'task-settings-diagnostics normalized',
    healthProvider: 'ollama',
    fields: {
      diagnostics_status: 'healthy',
      provider_ok: true,
      task_chain_status: 'degraded',
      task_chain_configured_sources: 1,
    },
  })

  assert.doesNotThrow(() => {
    assertion({
      diagnostics_status: 'healthy',
      provider_ok: true,
      task_chain_status: 'degraded',
      task_chain_configured_sources: 1,
      health: { provider: 'ollama' },
    })
  })
})
