import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDiagnosticsHref,
  buildQueryRunsRequestParams,
  normalizeDiagnosticsTab,
  normalizeMcpStatus,
  normalizeOperatorSummary,
  normalizeQueryRunsResponse,
  normalizeRecentFailures,
} from './DiagnosticsPage.helpers.js'

test('normalizeDiagnosticsTab only accepts supported tabs', () => {
  assert.equal(normalizeDiagnosticsTab('query-runs'), 'query-runs')
  assert.equal(normalizeDiagnosticsTab(' MCP '), 'mcp')
  assert.equal(normalizeDiagnosticsTab('missing'), 'overview')
})

test('buildDiagnosticsHref keeps stable tab and optional run_id params', () => {
  assert.equal(buildDiagnosticsHref({ tab: 'query-runs', runId: 'qrun-1' }), '/diagnostics?tab=query-runs&run_id=qrun-1')
  assert.equal(buildDiagnosticsHref({ tab: 'runtime' }), '/diagnostics?tab=runtime')
})

test('normalizeOperatorSummary and normalizeMcpStatus keep stable object shapes', () => {
  assert.equal(normalizeOperatorSummary(null).status, 'unknown')
  assert.equal(normalizeMcpStatus(null).transport, 'unknown')
  assert.equal(normalizeMcpStatus({ transport: 'streamable-http', tools_count: 9 }).tools_count, 9)
})

test('normalizeQueryRunsResponse and normalizeRecentFailures keep stable list defaults', () => {
  assert.deepEqual(normalizeQueryRunsResponse(null), { runs: [], total: 0 })
  assert.equal(normalizeRecentFailures({ recent_failures: [{ component: 'provider', count: 2 }] })[0].count, 2)
})

test('buildQueryRunsRequestParams maps frontend filter state to API params', () => {
  assert.deepEqual(
    buildQueryRunsRequestParams({ status: 'failed', strategy: 'global', layerUsed: 'l3', sessionId: 'session-1', limit: 15 }),
    {
      limit: 15,
      status: 'failed',
      strategy: 'global',
      layerUsed: 'l3',
      sessionId: 'session-1',
    }
  )
})
