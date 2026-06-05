import {
  createTaskCase,
  normalizeHealth,
} from './helpers.mjs'
import {
  buildSettingsImportDiagnosticsNormalizeFragment,
} from '../focused-real-smoke-settings-import-diagnostics-contract-helpers.mjs'

export const SETTINGS_IMPORT_TASK_CASES = {
  'task-22': createTaskCase('task-22', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        secret_store_disabled: summary.secret_store_env?.MEMORY_GRAPH_DISABLE_SECURE_SECRET_STORE === '1',
        direct_put_status: summary.direct_put_status ?? null,
        direct_put_code: summary.direct_put_code ?? null,
        initial_diagnostics_status: summary.initial_diagnostics_status ?? null,
        initial_provider_ok: summary.initial_provider_ok ?? null,
        browser_put_count: summary.browser_put_count ?? null,
        final_openai_base_url: summary.final_openai_base_url ?? null,
        final_openai_model: summary.final_openai_model ?? null,
        final_diagnostics_status: summary.final_diagnostics_status ?? null,
        final_provider_ok: summary.final_provider_ok ?? null,
        health: normalizeHealth(http.health),
        initial_provider: http.initial_config?.llm_provider ?? null,
        initial_secret_storage_type: http.initial_config?.secret_storage?.storage_type ?? null,
        initial_secret_storage_available: http.initial_config?.secret_storage?.available ?? null,
        direct_secret_put_success: http.direct_secret_put?.success ?? null,
        direct_secret_put_code: http.direct_secret_put?.code ?? null,
        direct_secret_storage_type: http.direct_secret_put?.secret_storage?.storage_type ?? null,
        ...buildSettingsImportDiagnosticsNormalizeFragment({
          summary,
          diagnostics: http.initial_diagnostics,
          summaryStatusKey: 'initial_diagnostics_status',
          summaryProviderOkKey: 'initial_provider_ok',
          providerOkField: 'initial_diagnostics_provider_ok',
          taskChainStatusField: 'initial_task_chain_status',
        }),
        final_provider: http.final_config?.llm_provider ?? null,
        final_openai_base_url_http: http.final_config?.openai_base_url ?? null,
        final_openai_model_http: http.final_config?.openai_model ?? null,
        final_secret_storage_type: http.final_config?.secret_storage?.storage_type ?? null,
        final_secret_storage_available: http.final_config?.secret_storage?.available ?? null,
        ...buildSettingsImportDiagnosticsNormalizeFragment({
          summary,
          diagnostics: http.final_diagnostics,
          summaryStatusKey: 'final_diagnostics_status',
          summaryProviderOkKey: 'final_provider_ok',
          providerOkField: 'final_diagnostics_provider_ok',
          taskChainStatusField: 'final_task_chain_status',
          recentFailureComponentsField: 'final_recent_failure_components',
        }),
      }
    },
  }),
  'task-23': createTaskCase('task-23', {
    normalize({ summary, http }) {
      return {
        command: summary.command ?? null,
        status: summary.status ?? null,
        diagnostics_status: summary.diagnostics_status ?? null,
        provider_ok: summary.provider_ok ?? null,
        task_chain_status: summary.task_chain_status ?? null,
        task_chain_configured_sources: summary.task_chain_configured_sources ?? null,
        task_chain_conflicts: summary.task_chain_conflicts ?? null,
        recent_failures_count: summary.recent_failures_count ?? null,
        fake_ollama_tag_requests_positive: Number(summary.fake_ollama_tag_requests) >= 1,
        health: normalizeHealth(http.health),
        ...buildSettingsImportDiagnosticsNormalizeFragment({
          summary,
          diagnostics: http.diagnostics,
          summaryStatusKey: 'diagnostics_status',
          summaryProviderOkKey: 'provider_ok',
          providerField: 'diagnostics_provider',
          providerOkField: 'diagnostics_provider_ok',
          taskChainStatusField: 'task_chain_status_http',
          configuredSourcesField: 'task_chain_configured_sources_http',
          sourceLabelsField: 'task_chain_source_labels',
          sourceStatusesField: 'task_chain_source_statuses',
          conflictsField: 'task_chain_conflicts_http',
          recentFailureComponentsField: 'recent_failure_components',
        }),
      }
    },
  }),
}
