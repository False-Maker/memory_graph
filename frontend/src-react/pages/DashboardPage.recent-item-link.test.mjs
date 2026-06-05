import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const dashboardPageFile = new URL('./DashboardPage.jsx', import.meta.url)

test('dashboard recent items keep direct links to memory detail routes', async () => {
  const source = await readFile(dashboardPageFile, 'utf8')

  assert.match(source, /data-testid=\{DASHBOARD_SMOKE_TEST_IDS\.recentItemLink\}/)
  assert.match(source, /to=\{`\/memories\/\$\{encodeURIComponent\(memory\.id\)\}`\}/)
  assert.match(source, /data-testid=\{DASHBOARD_SMOKE_TEST_IDS\.viewAllLink\}/)
  assert.match(source, /<Link to=\"\/memories\" className=\"dashboard-link-button\"/)
})
