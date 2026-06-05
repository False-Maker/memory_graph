export const DIAGNOSTICS_SMOKE_TEST_IDS = {
  page: 'diagnostics-page',
  refreshButton: 'diagnostics-refresh-button',
  tabOverview: 'diagnostics-tab-overview',
  tabQueryRuns: 'diagnostics-tab-query-runs',
  tabRuntime: 'diagnostics-tab-runtime',
  tabMcp: 'diagnostics-tab-mcp',
  tabFailures: 'diagnostics-tab-failures',
  summarySection: 'diagnostics-summary-section',
  queryRunsSection: 'diagnostics-query-runs-section',
  queryRunItem: 'diagnostics-query-run-item',
  queryRunDetail: 'diagnostics-query-run-detail',
  runtimeSection: 'diagnostics-runtime-section',
  mcpSection: 'diagnostics-mcp-section',
  failuresSection: 'diagnostics-failures-section',
  failureItem: 'diagnostics-failure-item',
}

export function getDiagnosticsSmokeTestId(key) {
  return DIAGNOSTICS_SMOKE_TEST_IDS[key] || null
}
