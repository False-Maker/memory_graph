import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, readFile } from 'node:fs/promises'

import {
  buildPlaywrightSmokeSummaryText,
  collectPlaywrightArtifacts,
  writePlaywrightSmokeEvidence,
} from './playwright-smoke-runtime.mjs'

test('collectPlaywrightArtifacts supports artifact and artifacts fields', () => {
  assert.deepEqual(
    collectPlaywrightArtifacts(
      [
        { scenario: 'a', artifact: 'a.png' },
        { scenario: 'b', artifacts: ['b.png', 'c.log'] },
      ],
      ['preview.log']
    ),
    ['a.png', 'b.png', 'c.log', 'preview.log']
  )
})

test('buildPlaywrightSmokeSummaryText keeps stable summary ordering', () => {
  assert.equal(
    buildPlaywrightSmokeSummaryText({
      generatedAt: '2026-04-08T02:00:00.000Z',
      status: 'passed',
      baseUrl: 'http://127.0.0.1:4174',
      results: [{ scenario: 'happy_path', artifact: 'happy.png' }],
      extraArtifacts: ['preview.log'],
      extraSummaryFields: { alerts: 'success' },
    }),
    [
      'generated_at=2026-04-08T02:00:00.000Z',
      'status=passed',
      'base_url=http://127.0.0.1:4174',
      'alerts=success',
      'scenario_count=1',
      'scenarios=happy_path',
      'artifacts=happy.png,preview.log',
      '',
    ].join('\n')
  )
})

test('writePlaywrightSmokeEvidence writes both summary text and json payload', async () => {
  const evidenceDir = await mkdtemp(path.join(os.tmpdir(), 'playwright-smoke-evidence-'))

  await writePlaywrightSmokeEvidence({
    evidenceDir,
    summaryFileName: 'summary.txt',
    jsonFileName: 'summary.json',
    generatedAt: '2026-04-08T02:00:00.000Z',
    status: 'passed',
    baseUrl: 'http://127.0.0.1:4174',
    results: [{ scenario: 'warning_path', artifact: 'warning.png', alert: 'warning' }],
    extraArtifacts: ['preview.log'],
    extraSummaryFields: { alerts: 'warning' },
    extraJsonFields: { alerts: ['warning'] },
  })

  const summaryText = await readFile(path.join(evidenceDir, 'summary.txt'), 'utf8')
  const summaryJson = JSON.parse(await readFile(path.join(evidenceDir, 'summary.json'), 'utf8'))

  assert.match(summaryText, /scenario_count=1/)
  assert.match(summaryText, /artifacts=warning\.png,preview\.log/)
  assert.equal(summaryJson.base_url, 'http://127.0.0.1:4174')
  assert.deepEqual(summaryJson.artifacts, ['warning.png', 'preview.log'])
  assert.deepEqual(summaryJson.alerts, ['warning'])
})
