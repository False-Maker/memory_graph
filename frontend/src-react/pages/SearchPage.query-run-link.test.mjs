import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const searchPageFile = new URL('./SearchPage.jsx', import.meta.url)

test('search page exposes trace link to diagnostics when query run id is available', async () => {
  const source = await readFile(searchPageFile, 'utf8')

  assert.match(source, /graphRagQueryWithMeta/)
  assert.match(source, /setQueryRunMeta\(/)
  assert.match(source, /data-testid=\{SEARCH_SMOKE_TEST_IDS\.queryRunLink\}/)
  assert.match(source, /buildDiagnosticsHref\(\{ tab: 'query-runs', runId: queryRunMeta\.runId \}\)/)
})
