import test from 'node:test'
import assert from 'node:assert/strict'

import { DASHBOARD_SMOKE_TEST_IDS, getDashboardSmokeTestId } from './DashboardPage.smoke-helpers.js'
import { COMMUNITIES_SMOKE_TEST_IDS, getCommunitiesSmokeTestId } from './CommunitiesPage.smoke-helpers.js'
import { DIAGNOSTICS_SMOKE_TEST_IDS, getDiagnosticsSmokeTestId } from './DiagnosticsPage.smoke-helpers.js'
import { getGraphSmokeTestId, GRAPH_SMOKE_TEST_IDS } from './GraphPage.smoke-helpers.js'
import { getMemoriesSmokeTestId, MEMORIES_SMOKE_TEST_IDS } from './MemoriesPage.smoke-helpers.js'
import { getSearchSmokeTestId, SEARCH_SMOKE_TEST_IDS } from './SearchPage.smoke-helpers.js'

test('dashboard/search/graph/communities/memories/diagnostics smoke ids expose stable selectors', () => {
  assert.equal(getDashboardSmokeTestId('statEntities'), 'dashboard-stat-entities')
  assert.equal(getDashboardSmokeTestId('operatorCardQueryRuns'), 'dashboard-operator-card-query-runs')
  assert.equal(getSearchSmokeTestId('queryInput'), 'search-query-input')
  assert.equal(getSearchSmokeTestId('queryRunLink'), 'search-query-run-link')
  assert.equal(getSearchSmokeTestId('sourceCommunityLink'), 'search-source-community-link')
  assert.equal(getSearchSmokeTestId('sourceDetailState'), 'search-source-detail-state')
  assert.equal(getGraphSmokeTestId('layoutSelect'), 'graph-layout-select')
  assert.equal(getCommunitiesSmokeTestId('summarizeButton'), 'communities-summarize-button')
  assert.equal(getCommunitiesSmokeTestId('listStatePanel'), 'communities-list-state-panel')
  assert.equal(getCommunitiesSmokeTestId('lineageAncestorsError'), 'communities-lineage-ancestors-error')
  assert.equal(getCommunitiesSmokeTestId('entitiesError'), 'communities-entities-error')
  assert.equal(getMemoriesSmokeTestId('itemArchiveButton'), 'memories-item-archive-button')
  assert.equal(getMemoriesSmokeTestId('detailLifecycleValue'), 'memories-detail-lifecycle-value')
  assert.equal(getMemoriesSmokeTestId('communitiesSection'), 'memories-communities-section')
  assert.equal(getMemoriesSmokeTestId('communityLink'), 'memories-community-link')
  assert.equal(getMemoriesSmokeTestId('nextPageButton'), 'memories-next-page-button')
  assert.equal(getDiagnosticsSmokeTestId('page'), 'diagnostics-page')
  assert.equal(getDiagnosticsSmokeTestId('queryRunDetail'), 'diagnostics-query-run-detail')
})

test('mainline smoke id helpers return null for unknown keys', () => {
  assert.equal(getDashboardSmokeTestId('missing'), null)
  assert.equal(getSearchSmokeTestId('missing'), null)
  assert.equal(getGraphSmokeTestId('missing'), null)
  assert.equal(getCommunitiesSmokeTestId('missing'), null)
  assert.equal(getMemoriesSmokeTestId('missing'), null)
  assert.equal(getDiagnosticsSmokeTestId('missing'), null)
})

test('mainline smoke ids stay unique across page surfaces', () => {
  const values = [
    ...Object.values(DASHBOARD_SMOKE_TEST_IDS),
    ...Object.values(SEARCH_SMOKE_TEST_IDS),
    ...Object.values(GRAPH_SMOKE_TEST_IDS),
    ...Object.values(COMMUNITIES_SMOKE_TEST_IDS),
    ...Object.values(MEMORIES_SMOKE_TEST_IDS),
    ...Object.values(DIAGNOSTICS_SMOKE_TEST_IDS),
  ]

  assert.equal(new Set(values).size, values.length)
})
