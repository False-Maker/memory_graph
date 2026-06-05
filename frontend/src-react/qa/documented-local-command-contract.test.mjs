import test from 'node:test'
import assert from 'node:assert/strict'
import {
  CORE_PRODUCT_DOCS,
  FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE,
  WORKFLOW_FILE,
  findMissingLocalCommandTargets,
} from './documented-contract-test-helpers.mjs'

test('product docs only reference existing local python/bash/pytest targets', async () => {
  const docs = CORE_PRODUCT_DOCS

  for (const [label, fileUrl] of docs) {
    const result = await findMissingLocalCommandTargets(fileUrl)
    assert.ok(result.totalReferences > 0, `${label} should reference at least one local command target`)
    assert.deepEqual(
      result.missingScripts,
      [],
      `${label} references missing local scripts: ${result.missingScripts.join(', ')}`
    )
    assert.deepEqual(
      result.missingPytestTargets,
      [],
      `${label} references missing pytest targets: ${result.missingPytestTargets.join(', ')}`
    )
  }
})

test('contract guard workflow only references existing local python/bash/pytest targets', async () => {
  const primaryResult = await findMissingLocalCommandTargets(WORKFLOW_FILE)
  const reusableResult = await findMissingLocalCommandTargets(FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE)
  const result = {
    totalReferences: primaryResult.totalReferences + reusableResult.totalReferences,
    missingScripts: [...primaryResult.missingScripts, ...reusableResult.missingScripts],
    missingPytestTargets: [...primaryResult.missingPytestTargets, ...reusableResult.missingPytestTargets],
  }
  assert.ok(result.totalReferences > 0, 'contract guard workflows should reference at least one local command target')
  assert.deepEqual(
    result.missingScripts,
    [],
    `contract guard workflows reference missing local scripts: ${result.missingScripts.join(', ')}`
  )
  assert.deepEqual(
    result.missingPytestTargets,
    [],
    `contract guard workflows reference missing pytest targets: ${result.missingPytestTargets.join(', ')}`
  )
})
