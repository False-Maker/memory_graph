import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const graphApiFile = new URL('./graph.js', import.meta.url)

test('graphApi only exposes backend-supported methods', async () => {
  const source = await readFile(graphApiFile, 'utf8')
  const exportedMethods = [...source.matchAll(/^\s{2}(\w+):/gm)].map((match) => match[1]).sort()

  assert.deepEqual(exportedMethods, [
    'getEntities',
    'getEntity',
    'getNeighbors',
    'getRelationships',
    'getStats'
  ])
})

test('graphApi does not reintroduce removed graph contract methods', async () => {
  const source = await readFile(graphApiFile, 'utf8')
  const forbiddenMethods = [
    'createEntity',
    'updateEntity',
    'deleteEntity',
    'getLayout',
    'getPath'
  ]

  for (const method of forbiddenMethods) {
    assert.equal(
      source.includes(`${method}:`),
      false,
      `${method} should not be exposed by graphApi`
    )
  }
})

test('graphApi paths match the backend graph routes in use', async () => {
  const source = await readFile(graphApiFile, 'utf8')

  assert.match(source, /\/graph\/stats/)
  assert.match(source, /\/graph\/entities/)
  assert.match(source, /\/graph\/relationships/)
  assert.match(source, /\/graph\/entities\/\$\{entityId\}\/neighbors/)
})
