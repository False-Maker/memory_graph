import {
  assertFocusedRealSmokeEvidenceSampleCase,
  getFocusedRealSmokeTaskGroupTaskIds,
} from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSettingsImportDiagnosticsEvidenceAssertion,
} from './focused-real-smoke-evidence-assertion-helpers.mjs'

export const SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID = Object.freeze({
  'task-22': buildSettingsImportDiagnosticsEvidenceAssertion('task-22', {
    label: 'task-22 normalized',
    healthProvider: 'openai',
    fields: {
      secret_store_disabled: true,
      direct_put_status: 503,
      direct_put_code: 'secure_secret_store_unavailable',
      initial_diagnostics_status: 'unhealthy',
      initial_provider_ok: false,
      browser_put_count: 1,
      final_openai_base_url: 'https://open.bigmodel.cn/api/coding/paas/v4',
      final_openai_model: 'glm-4.7',
      final_diagnostics_status: 'unhealthy',
      final_provider_ok: false,
      initial_provider: 'openai',
      initial_secret_storage_type: 'environment_only',
      initial_secret_storage_available: false,
      direct_secret_put_success: false,
      direct_secret_put_code: 'secure_secret_store_unavailable',
      direct_secret_storage_type: 'environment_only',
      initial_diagnostics_provider_ok: false,
      initial_task_chain_status: 'not_configured',
      final_provider: 'openai',
      final_openai_base_url_http: 'https://open.bigmodel.cn/api/coding/paas/v4',
      final_openai_model_http: 'glm-4.7',
      final_secret_storage_type: 'environment_only',
      final_secret_storage_available: false,
      final_diagnostics_provider_ok: false,
      final_task_chain_status: 'not_configured',
      final_recent_failure_components: ['provider'],
    },
  }),
  'task-23': buildSettingsImportDiagnosticsEvidenceAssertion('task-23', {
    label: 'task-23 normalized',
    healthProvider: 'ollama',
    fields: {
      diagnostics_status: 'healthy',
      provider_ok: true,
      task_chain_status: 'degraded',
      task_chain_configured_sources: 1,
      task_chain_conflicts: 1,
      recent_failures_count: 1,
      fake_ollama_tag_requests_positive: true,
      diagnostics_provider: 'ollama',
      diagnostics_provider_ok: true,
      task_chain_status_http: 'degraded',
      task_chain_configured_sources_http: 1,
      task_chain_source_labels: ['Workspace Notes'],
      task_chain_source_statuses: ['degraded'],
      task_chain_conflicts_http: 1,
      recent_failure_components: ['task_chain'],
    },
  }),
})

export const SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTION_TASK_IDS = Object.freeze(
  getFocusedRealSmokeTaskGroupTaskIds('settings-import-focused')
)

export function assertSettingsImportEvidenceSample(taskId, normalized) {
  assertFocusedRealSmokeEvidenceSampleCase(
    taskId,
    normalized,
    SETTINGS_IMPORT_EVIDENCE_SAMPLE_ASSERTIONS_BY_TASK_ID,
    'settings-import evidence sample assertion'
  )
}
