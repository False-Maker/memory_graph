import test from 'node:test'
import assert from 'node:assert/strict'

import {
  OFFICIAL_COLLECTOR_SMOKE_CASES,
  buildOfficialCollectorMatrixSummary,
  getOfficialCollectorMatrixEvidencePaths,
  getOfficialCollectorSmokeCase,
} from './t61-official-collector-matrix-helpers.mjs'

test('official collector smoke cases stay on the current public support boundary', () => {
  assert.deepEqual(
    OFFICIAL_COLLECTOR_SMOKE_CASES.map((item) => item.collectorType),
    ['windsurf', 'claude_code', 'aider']
  )
  assert.equal(getOfficialCollectorSmokeCase('windsurf')?.supportTier, 'official')
  assert.equal(getOfficialCollectorSmokeCase('cline'), null)
})

test('official collector evidence paths use stable task-61 filenames', () => {
  const paths = getOfficialCollectorMatrixEvidencePaths('/tmp/evidence')

  assert.equal(paths.summary, '/tmp/evidence/task-61-official-collector-matrix-summary.txt')
  assert.equal(paths.json, '/tmp/evidence/task-61-official-collector-matrix-summary.json')
  assert.equal(paths.backendLog, '/tmp/evidence/task-61-official-collector-matrix-backend.log')
  assert.equal(paths.http, '/tmp/evidence/task-61-official-collector-matrix-http.json')
})

test('official collector matrix summary reports rows and counts', () => {
  const summary = buildOfficialCollectorMatrixSummary(
    [
      {
        collectorType: 'windsurf',
        label: 'official-windsurf',
        supportTier: 'official',
        status: 'passed',
        processedCount: 1,
        detail: 'status=running',
      },
      {
        collectorType: 'claude_code',
        label: 'official-claude-code',
        supportTier: 'official',
        status: 'failed',
        processedCount: 0,
        detail: 'status=down',
      },
    ],
    {
      generatedAt: '2026-04-17T10:00:00Z',
      source: 'qa:real-stack-smoke:collectors:official',
      backendBaseUrl: 'http://127.0.0.1:38261',
    }
  )

  assert.match(summary, /collector=windsurf/)
  assert.match(summary, /collector=claude_code/)
  assert.match(summary, /passed_count=1/)
  assert.match(summary, /failed_count=1/)
})
