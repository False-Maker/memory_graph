import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildInboxSmokeSummaryLines,
  normalizeInboxSmokeResult
} from './t14-real-stack-smoke-inbox-helpers.mjs'

test('normalizeInboxSmokeResult keeps passed status and unique checks', () => {
  assert.deepEqual(
    normalizeInboxSmokeResult({
      status: 'passed',
      checks: [' inbox_page_loaded ', 'inbox_page_loaded', 'directory_form_visible']
    }),
    {
      status: 'passed',
      checks: ['inbox_page_loaded', 'directory_form_visible'],
      note: ''
    }
  )
})

test('normalizeInboxSmokeResult falls back to failed status', () => {
  assert.deepEqual(
    normalizeInboxSmokeResult({
      status: 'unknown',
      checks: null
    }),
    {
      status: 'failed',
      checks: [],
      note: ''
    }
  )
})

test('buildInboxSmokeSummaryLines renders stable defaults', () => {
  assert.deepEqual(
    buildInboxSmokeSummaryLines({
      status: 'failed',
      checks: [],
      note: 'not_executed'
    }),
    [
      'inbox_smoke=failed',
      'inbox_smoke_checks=none',
      'inbox_smoke_note=not_executed'
    ]
  )
})

