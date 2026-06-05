import test from 'node:test'
import assert from 'node:assert/strict'

import {
  assertMappedUniqueValues,
  assertSortedUniqueValuesMatch,
  assertUniqueValues,
} from './focused-real-smoke-registry-test-helpers.mjs'

test('assertUniqueValues accepts unique values and rejects duplicates', () => {
  assert.doesNotThrow(() => {
    assertUniqueValues(['a', 'b', 'c'], 'sample ids')
  })

  assert.throws(
    () => assertUniqueValues(['a', 'b', 'a'], 'sample ids'),
    /sample ids contains duplicate values/
  )
})

test('assertMappedUniqueValues checks uniqueness after mapping', () => {
  assert.doesNotThrow(() => {
    assertMappedUniqueValues([{ id: 'a' }, { id: 'b' }], (item) => item.id, 'sample item ids')
  })

  assert.throws(
    () => assertMappedUniqueValues([{ id: 'a' }, { id: 'a' }], (item) => item.id, 'sample item ids'),
    /sample item ids contains duplicate values/
  )
})

test('assertSortedUniqueValuesMatch compares sorted unique sets', () => {
  assert.doesNotThrow(() => {
    assertSortedUniqueValuesMatch(['b', 'a', 'a'], ['a', 'b'], 'sample coverage')
  })

  assert.throws(
    () => assertSortedUniqueValuesMatch(['a', 'c'], ['a', 'b'], 'sample coverage'),
    /sample coverage/
  )
})
