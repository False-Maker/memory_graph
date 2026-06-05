export const IMPORT_SMOKE_TEST_IDS = {
  diagnosticsCard: 'import-diagnostics-card',
  diagnosticsSummary: 'import-diagnostics-summary',
  diagnosticsRefreshButton: 'import-diagnostics-refresh',
}

export function getImportSmokeTestId(key) {
  return IMPORT_SMOKE_TEST_IDS[key] || null
}
