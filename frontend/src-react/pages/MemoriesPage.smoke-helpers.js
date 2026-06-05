export const MEMORIES_SMOKE_TEST_IDS = {
  page: 'memories-page',
  activeFilter: 'memories-filter-active',
  archivedFilter: 'memories-filter-archived',
  allFilter: 'memories-filter-all',
  prevPageButton: 'memories-prev-page-button',
  nextPageButton: 'memories-next-page-button',
  pageLabel: 'memories-page-label',
  statePanel: 'memories-state-panel',
  list: 'memories-list',
  item: 'memories-item',
  itemViewButton: 'memories-item-view-button',
  itemArchiveButton: 'memories-item-archive-button',
  itemDeleteButton: 'memories-item-delete-button',
  detailPanel: 'memories-detail-panel',
  detailState: 'memories-detail-state',
  detailLifecycleValue: 'memories-detail-lifecycle-value',
  detailArchiveButton: 'memories-detail-archive-button',
  detailDeleteButton: 'memories-detail-delete-button',
  detailCloseButton: 'memories-detail-close-button',
  communitiesSection: 'memories-communities-section',
  entitiesSection: 'memories-entities-section',
  communityLink: 'memories-community-link',
}

export function getMemoriesSmokeTestId(key) {
  return MEMORIES_SMOKE_TEST_IDS[key] || null
}
