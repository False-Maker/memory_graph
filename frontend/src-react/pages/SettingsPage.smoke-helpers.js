export const SETTINGS_SMOKE_TEST_IDS = {
  globalErrorAlert: 'settings-global-error-alert',
  diagnosticsSection: 'settings-diagnostics-section',
  diagnosticsSummary: 'settings-diagnostics-summary',
  diagnosticsRefreshButton: 'settings-diagnostics-refresh',
  secretStorageStatus: 'settings-secret-storage-status',
  taskChainBlock: 'settings-task-chain-block',
  recentFailuresBlock: 'settings-recent-failures-block',
  exportBlock: 'settings-export-block',
  exportButton: 'settings-export-button',
  exportResult: 'settings-export-result',
  restoreDryRunBlock: 'settings-restore-dry-run-block',
  restoreDryRunFile: 'settings-restore-dry-run-file',
  restoreDryRunButton: 'settings-restore-dry-run-button',
  restoreDryRunResult: 'settings-restore-dry-run-result',
  reindexBlock: 'settings-reindex-block',
  reindexButton: 'settings-reindex-button',
  reindexResult: 'settings-reindex-result',
}

export function getSettingsSmokeTestId(key) {
  return SETTINGS_SMOKE_TEST_IDS[key] || null
}
