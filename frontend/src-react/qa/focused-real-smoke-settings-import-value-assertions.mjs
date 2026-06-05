import { assertFocusedRealSmokeValueCase } from './focused-real-smoke-contract-helpers.mjs'
import {
  buildSettingsImportDiagnosticsValuePatterns,
} from './focused-real-smoke-settings-import-diagnostics-contract-helpers.mjs'

export const SETTINGS_IMPORT_VALUE_CASES_BY_TASK_ID = Object.freeze({
  'task-22': {
    patterns: buildSettingsImportDiagnosticsValuePatterns({
      statusPattern: /initial_diagnostics_status:\s*httpEvidence\.diagnosticsResponse\.json\?\.status/,
      providerOkPattern: /initial_provider_ok:\s*httpEvidence\.diagnosticsResponse\.json\?\.checks\?\.provider\?\.ok/,
      patterns: [
      /secret_store_env:\s*\{\s*\[DISABLE_SECRET_STORE_ENV\]: '1',\s*\[SETTINGS_PATH_ENV\]: configPath,\s*\}/s,
      /direct_put_status:\s*httpEvidence\.directSaveResponse\.statusCode/,
      /direct_put_code:\s*httpEvidence\.directSaveResponse\.json\?\.code/,
      /browser_put_count:\s*browserEvidence\.putCount/,
      /final_openai_base_url:\s*finalConfig\.json\?\.openai_base_url/,
      /final_openai_model:\s*finalConfig\.json\?\.openai_model/,
      ...buildSettingsImportDiagnosticsValuePatterns({
        statusPattern: /final_diagnostics_status:\s*finalDiagnostics\.json\?\.status/,
        providerOkPattern: /final_provider_ok:\s*finalDiagnostics\.json\?\.checks\?\.provider\?\.ok/,
      }),
      /initial_config:\s*httpEvidence\.configResponse\.json/,
      /direct_secret_put:\s*httpEvidence\.directSaveResponse\.json/,
      /initial_diagnostics:\s*httpEvidence\.diagnosticsResponse\.json/,
      /final_config:\s*finalConfig\.json/,
      /final_diagnostics:\s*finalDiagnostics\.json/,
      ],
    }),
  },
  'task-23': {
    patterns: buildSettingsImportDiagnosticsValuePatterns({
      statusPattern: /diagnostics_status:\s*httpEvidence\.diagnostics\.json\?\.status/,
      providerOkPattern: /provider_ok:\s*httpEvidence\.diagnostics\.json\?\.checks\?\.provider\?\.ok/,
      taskChainStatusPattern: /task_chain_status:\s*httpEvidence\.diagnostics\.json\?\.task_chain\?\.status/,
      configuredSourcesPattern: /task_chain_configured_sources:\s*httpEvidence\.diagnostics\.json\?\.task_chain\?\.configured_sources/,
      conflictsPattern: /task_chain_conflicts:\s*httpEvidence\.diagnostics\.json\?\.task_chain\?\.sources\?\.\[0\]\?\.conflicts/,
      recentFailuresCountPattern: /recent_failures_count:\s*Array\.isArray\(httpEvidence\.diagnostics\.json\?\.recent_failures\)/,
      patterns: [
      /sync_sources_path:\s*taskChainFixture\.syncSourcesPath/,
      /state_path:\s*taskChainFixture\.statePath/,
      /fake_ollama_tag_requests:\s*browserEvidence\.fakeOllamaTagRequests/,
      /diagnostics:\s*httpEvidence\.diagnostics\.json/,
      ],
    }),
  },
})

export function assertFocusedRealSmokeSettingsImportValueContract(taskId, qaScriptFile, source) {
  assertFocusedRealSmokeValueCase(taskId, qaScriptFile, source, SETTINGS_IMPORT_VALUE_CASES_BY_TASK_ID, {
    missingCaseLabel: 'settings-import value contract case',
    missingBindingLabel: 'expected settings-import evidence binding',
  })
}
