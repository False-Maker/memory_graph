import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const dashboardPageFile = new URL('./DashboardPage.jsx', import.meta.url)

test('dashboard stat cards keep stable navigation targets', async () => {
  const source = await readFile(dashboardPageFile, 'utf8')

  assert.match(source, /key:\s*'entities'[\s\S]*?to:\s*'\/graph'/)
  assert.match(source, /key:\s*'relationships'[\s\S]*?to:\s*'\/graph'/)
  assert.match(source, /key:\s*'memories'[\s\S]*?to:\s*'\/memories'/)
  assert.match(source, /key:\s*'communities'[\s\S]*?to:\s*'\/communities'/)
  assert.match(source, /className="dashboard-stat-card dashboard-stat-card--link"/)
})

test('dashboard operator summary cards link into diagnostics tabs', async () => {
  const source = await readFile(dashboardPageFile, 'utf8')

  assert.match(source, /testId:\s*DASHBOARD_SMOKE_TEST_IDS\.operatorCardQueryRuns/)
  assert.match(source, /testId:\s*DASHBOARD_SMOKE_TEST_IDS\.operatorCardRuntime/)
  assert.match(source, /testId:\s*DASHBOARD_SMOKE_TEST_IDS\.operatorCardFailures/)
  assert.match(source, /testId:\s*DASHBOARD_SMOKE_TEST_IDS\.operatorCardMcp/)
  assert.match(source, /data-testid=\{card\.testId\}/)
  assert.match(source, /buildDiagnosticsHref\(\{ tab: 'query-runs' \}\)/)
  assert.match(source, /buildDiagnosticsHref\(\{ tab: 'runtime' \}\)/)
  assert.match(source, /buildDiagnosticsHref\(\{ tab: 'failures' \}\)/)
  assert.match(source, /buildDiagnosticsHref\(\{ tab: 'mcp' \}\)/)
})
