import test from 'node:test'
import assert from 'node:assert/strict'

import { buildCommunitiesHashHref } from './SearchPage.community-links.js'

test('buildCommunitiesHashHref returns encoded communities hash url', () => {
  assert.equal(buildCommunitiesHashHref('comm-1'), '/communities#comm-1')
  assert.equal(buildCommunitiesHashHref('  comm alpha/beta  '), '/communities#comm%20alpha%2Fbeta')
})

test('buildCommunitiesHashHref returns null for missing id', () => {
  assert.equal(buildCommunitiesHashHref(''), null)
  assert.equal(buildCommunitiesHashHref('   '), null)
  assert.equal(buildCommunitiesHashHref(null), null)
  assert.equal(buildCommunitiesHashHref(undefined), null)
})

