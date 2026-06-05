import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const searchPageFile = new URL('./SearchPage.jsx', import.meta.url)

test('search page keeps source and result community links on distinct selectors', async () => {
  const source = await readFile(searchPageFile, 'utf8')

  assert.match(source, /data-testid=\{SEARCH_SMOKE_TEST_IDS\.sourceCommunityLink\}/)
  assert.match(source, /data-testid=\{SEARCH_SMOKE_TEST_IDS\.communityLink\}/)
  assert.equal((source.match(/SEARCH_SMOKE_TEST_IDS\.sourceCommunityLink/g) || []).length, 1)
  assert.equal((source.match(/SEARCH_SMOKE_TEST_IDS\.communityLink/g) || []).length, 1)
})

test('search page keeps source and result community links on their intended cards', async () => {
  const source = await readFile(searchPageFile, 'utf8')

  assert.match(
    source,
    /data-testid=\{SEARCH_SMOKE_TEST_IDS\.memorySourceItem\}[\s\S]*data-testid=\{SEARCH_SMOKE_TEST_IDS\.sourceCommunityLink\}[\s\S]*data-testid=\{SEARCH_SMOKE_TEST_IDS\.sourceDetailToggle\}/
  )
  assert.match(
    source,
    /data-testid=\{SEARCH_SMOKE_TEST_IDS\.communitySourceItem\}[\s\S]*data-testid=\{SEARCH_SMOKE_TEST_IDS\.communityLink\}/
  )
})
