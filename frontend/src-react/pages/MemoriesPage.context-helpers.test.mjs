import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCommunitiesHashHref,
  buildInitialMemoryContext,
  hasMemoryContextContent,
  normalizeMemoryContextPayload,
} from './MemoriesPage.context-helpers.js'

test('buildCommunitiesHashHref encodes community ids', () => {
  assert.equal(buildCommunitiesHashHref('comm-1'), '/communities#comm-1')
  assert.equal(buildCommunitiesHashHref(' comm alpha/beta '), '/communities#comm%20alpha%2Fbeta')
  assert.equal(buildCommunitiesHashHref(''), null)
})

test('normalizeMemoryContextPayload falls back to empty lists', () => {
  assert.deepEqual(buildInitialMemoryContext(), { entities: [], communities: [] })
  assert.deepEqual(normalizeMemoryContextPayload(null), { entities: [], communities: [] })
  assert.deepEqual(normalizeMemoryContextPayload({ entities: [{ id: 'e-1' }] }), {
    entities: [{ id: 'e-1' }],
    communities: [],
  })
})

test('hasMemoryContextContent detects entity or community data', () => {
  assert.equal(hasMemoryContextContent(buildInitialMemoryContext()), false)
  assert.equal(hasMemoryContextContent({ entities: [{ id: 'e-1' }], communities: [] }), true)
  assert.equal(hasMemoryContextContent({ entities: [], communities: [{ id: 'c-1' }] }), true)
})
