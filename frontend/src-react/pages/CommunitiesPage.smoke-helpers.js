export const COMMUNITIES_SMOKE_TEST_IDS = {
  page: 'communities-page',
  toolbar: 'communities-toolbar',
  detectButton: 'communities-detect-button',
  refreshButton: 'communities-refresh-button',
  hierarchyToggle: 'communities-hierarchy-toggle',
  hierarchyPanel: 'communities-hierarchy-panel',
  actionFeedback: 'communities-action-feedback',
  listPanel: 'communities-list-panel',
  listStatePanel: 'communities-list-state-panel',
  card: 'communities-card',
  detailPanel: 'communities-detail-panel',
  lineageSection: 'communities-lineage-section',
  lineageAncestorsError: 'communities-lineage-ancestors-error',
  lineageDescendantsError: 'communities-lineage-descendants-error',
  entitiesSection: 'communities-entities-section',
  entitiesError: 'communities-entities-error',
  relationshipsSection: 'communities-relationships-section',
  relationshipsError: 'communities-relationships-error',
  summarizeButton: 'communities-summarize-button',
}

export function getCommunitiesSmokeTestId(key) {
  return COMMUNITIES_SMOKE_TEST_IDS[key] || null
}
