export const SEARCH_SMOKE_TEST_IDS = {
  page: 'search-page',
  form: 'search-form',
  queryInput: 'search-query-input',
  submitButton: 'search-submit-button',
  validationError: 'search-validation-error',
  loadingPanel: 'search-loading-panel',
  errorPanel: 'search-error-panel',
  emptyPanel: 'search-empty-panel',
  resultsGrid: 'search-results-grid',
  queryRunLink: 'search-query-run-link',
  memorySourcesCard: 'search-memory-sources-card',
  memorySourceItem: 'search-memory-source-item',
  memoryLink: 'search-memory-link',
  sourceCommunityLink: 'search-source-community-link',
  communityLink: 'search-community-link',
  sourceDetailToggle: 'search-source-detail-toggle',
  sourceDetailPanel: 'search-source-detail-panel',
  sourceDetailState: 'search-source-detail-state',
  communitiesCard: 'search-communities-card',
  communitySourceItem: 'search-community-source-item',
}

export function getSearchSmokeTestId(key) {
  return SEARCH_SMOKE_TEST_IDS[key] || null
}
