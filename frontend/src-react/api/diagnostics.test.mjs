import test from 'node:test'
import assert from 'node:assert/strict'

import { buildDiagnosticsQuery } from './diagnostics.helpers.js'

test('buildDiagnosticsQuery keeps stable supported query params only', () => {
  assert.equal(
    buildDiagnosticsQuery({
      limit: 20,
      status: 'failed',
      strategy: 'global',
      layer_used: 'l3',
      session_id: 'session-1',
    }),
    '?limit=20&status=failed&strategy=global&layer_used=l3&session_id=session-1'
  )

  assert.equal(buildDiagnosticsQuery({}), '')
})
