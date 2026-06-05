import assert from 'node:assert/strict'

export function assertUniqueValues(values, label) {
  assert.equal(
    new Set(values).size,
    values.length,
    `${label} contains duplicate values`
  )
}

export function assertMappedUniqueValues(items, mapper, label) {
  assertUniqueValues(items.map(mapper), label)
}

export function assertSortedUniqueValuesMatch(actualValues, expectedValues, label) {
  assert.deepEqual(
    [...new Set(actualValues)].sort(),
    [...expectedValues].sort(),
    label
  )
}
