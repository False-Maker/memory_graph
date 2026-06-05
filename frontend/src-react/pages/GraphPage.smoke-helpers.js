export const GRAPH_SMOKE_TEST_IDS = {
  page: 'graph-page',
  toolbar: 'graph-toolbar',
  refreshButton: 'graph-refresh-button',
  layoutSelect: 'graph-layout-select',
  loadingOverlay: 'graph-loading-overlay',
  errorOverlay: 'graph-error-overlay',
  emptyOverlay: 'graph-empty-overlay',
  node: 'graph-node',
  detailPanel: 'graph-detail-panel',
}

export function getGraphSmokeTestId(key) {
  return GRAPH_SMOKE_TEST_IDS[key] || null
}
