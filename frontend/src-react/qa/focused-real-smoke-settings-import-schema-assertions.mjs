import {
  assertFocusedRealSmokeSchemaCase,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSettingsImportDiagnosticsSummaryKeys,
} from './focused-real-smoke-settings-import-diagnostics-contract-helpers.mjs'

export const SETTINGS_IMPORT_SCHEMA_CASES_BY_TASK_ID = Object.freeze({
  'task-22': {
    summaryKeys: [
      'secret_store_env',
      'direct_put_status',
      'direct_put_code',
      ...buildSettingsImportDiagnosticsSummaryKeys({
        statusKey: 'initial_diagnostics_status',
        providerOkKey: 'initial_provider_ok',
      }),
      'browser_put_count',
      'final_openai_base_url',
      'final_openai_model',
      ...buildSettingsImportDiagnosticsSummaryKeys({
        statusKey: 'final_diagnostics_status',
        providerOkKey: 'final_provider_ok',
      }),
    ],
    httpKeys: ['health', 'initial_config', 'direct_secret_put', 'initial_diagnostics', 'final_config', 'final_diagnostics'],
  },
  'task-23': {
    summaryKeys: [
      'sync_sources_path',
      'state_path',
      ...buildSettingsImportDiagnosticsSummaryKeys({
        statusKey: 'diagnostics_status',
        providerOkKey: 'provider_ok',
        taskChainStatusKey: 'task_chain_status',
        configuredSourcesKey: 'task_chain_configured_sources',
        conflictsKey: 'task_chain_conflicts',
        recentFailuresCountKey: 'recent_failures_count',
      }),
      'fake_ollama_tag_requests',
    ],
    httpKeys: ['health', 'diagnostics'],
  },
})

export function assertFocusedRealSmokeSettingsImportSchemaContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeSchemaCase(
    taskId,
    qaScriptFile,
    source,
    SETTINGS_IMPORT_SCHEMA_CASES_BY_TASK_ID,
    'settings-import schema contract case'
  )
}
