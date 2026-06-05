import test from 'node:test'
import assert from 'node:assert/strict'

import { DASHBOARD_SMOKE_TEST_IDS, getDashboardSmokeTestId } from './DashboardPage.smoke-helpers.js'

test('dashboard smoke ids expose stable selectors', () => {
  assert.equal(getDashboardSmokeTestId('page'), 'dashboard-page')
  assert.equal(getDashboardSmokeTestId('statEntities'), 'dashboard-stat-entities')
  assert.equal(getDashboardSmokeTestId('viewAllLink'), 'dashboard-view-all-link')
  assert.equal(getDashboardSmokeTestId('recentItem'), 'dashboard-recent-item')
  assert.equal(getDashboardSmokeTestId('recentItemLink'), 'dashboard-recent-item-link')
})

test('dashboard smoke ids stay unique', () => {
  const values = Object.values(DASHBOARD_SMOKE_TEST_IDS)
  assert.equal(new Set(values).size, values.length)
})

test('unknown dashboard smoke ids return null', () => {
  assert.equal(getDashboardSmokeTestId('missing'), null)
})
