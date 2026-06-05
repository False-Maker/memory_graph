import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const communitiesPageFile = new URL('./CommunitiesPage.jsx', import.meta.url)

test('community summary action explicitly requests regeneration', async () => {
  const source = await readFile(communitiesPageFile, 'utf8')
  assert.match(source, /summarizeCommunity\(selectedCommunity\.id,\s*\{\s*regenerate:\s*true\s*\}\)/)
})
