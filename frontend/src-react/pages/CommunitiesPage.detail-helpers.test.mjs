import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildCommunityHash,
  buildInitialFacetData,
  buildInitialFacetErrors,
  buildInitialFacetLoading,
  hasAnyFacetContent,
  normalizeCommunityIdFromHash,
  normalizeFacetPayload,
} from './CommunitiesPage.detail-helpers.js'

test('normalizeCommunityIdFromHash and buildCommunityHash are reversible for basic IDs', () => {
  assert.equal(normalizeCommunityIdFromHash('#community-1'), 'community-1')
  assert.equal(buildCommunityHash('community-1'), '#community-1')
  assert.equal(normalizeCommunityIdFromHash(buildCommunityHash('comm/2')), 'comm/2')
})

test('initial facet builders return all expected keys', () => {
  assert.deepEqual(buildInitialFacetData(), {
    entities: [],
    relationships: [],
    ancestors: [],
    descendants: [],
  })
  assert.deepEqual(buildInitialFacetLoading(), {
    entities: false,
    relationships: false,
    ancestors: false,
    descendants: false,
  })
  assert.deepEqual(buildInitialFacetErrors(), {
    entities: null,
    relationships: null,
    ancestors: null,
    descendants: null,
  })
})

test('normalizeFacetPayload and hasAnyFacetContent handle mixed payloads', () => {
  assert.deepEqual(normalizeFacetPayload('entities', [{ id: 'e1' }]), [{ id: 'e1' }])
  assert.deepEqual(normalizeFacetPayload('entities', { entities: [{ id: 'e2' }] }), [{ id: 'e2' }])
  assert.deepEqual(normalizeFacetPayload('entities', { bad: true }), [])

  assert.equal(
    hasAnyFacetContent({
      entities: [],
      relationships: [{ id: 'r1' }],
      ancestors: [],
      descendants: [],
    }),
    true
  )
  assert.equal(hasAnyFacetContent(buildInitialFacetData()), false)
})

