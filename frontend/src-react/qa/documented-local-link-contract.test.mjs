import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'

import {
  CORE_PRODUCT_DOCS_WITH_FOLLOWUP,
  collectLocalMarkdownLinks,
} from './documented-contract-test-helpers.mjs'

test('core product docs only reference existing local markdown link targets', async () => {
  const docs = CORE_PRODUCT_DOCS_WITH_FOLLOWUP

  for (const [label, fileUrl] of docs) {
    const links = await collectLocalMarkdownLinks(fileUrl)
    const missing = links.filter((target) => !existsSync(target))
    assert.deepEqual(
      missing,
      [],
      `${label} references missing local markdown targets: ${missing.join(', ')}`
    )
  }
})
