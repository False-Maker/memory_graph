export const DASHBOARD_SMOKE_TEST_IDS = {
  page: 'dashboard-page',
  statsGrid: 'dashboard-stats-grid',
  statsError: 'dashboard-stats-error',
  statEntities: 'dashboard-stat-entities',
  statRelationships: 'dashboard-stat-relationships',
  statMemories: 'dashboard-stat-memories',
  statCommunities: 'dashboard-stat-communities',
  operatorSection: 'dashboard-operator-section',
  operatorCardQueryRuns: 'dashboard-operator-card-query-runs',
  operatorCardRuntime: 'dashboard-operator-card-runtime',
  operatorCardFailures: 'dashboard-operator-card-failures',
  operatorCardMcp: 'dashboard-operator-card-mcp',
  recentSection: 'dashboard-recent-section',
  viewAllLink: 'dashboard-view-all-link',
  recentState: 'dashboard-recent-state',
  recentItem: 'dashboard-recent-item',
  recentItemLink: 'dashboard-recent-item-link',
}

export function getDashboardSmokeTestId(key) {
  return DASHBOARD_SMOKE_TEST_IDS[key] || null
}
