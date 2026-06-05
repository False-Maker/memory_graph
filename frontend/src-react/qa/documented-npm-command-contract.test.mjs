import test from 'node:test'
import assert from 'node:assert/strict'
import {
  BASELINE_FILE,
  CORE_PRODUCT_DOCS,
  DEVELOPMENT_FILE,
  FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE,
  README_FILE,
  WORKFLOW_FILE,
  collectDocumentCommands,
  findMissingCommands,
  loadPackageScripts,
} from './documented-contract-test-helpers.mjs'

test('current product docs only reference npm run commands that exist in package scripts', async () => {
  const packageScriptsByPrefix = await loadPackageScripts()
  const docs = CORE_PRODUCT_DOCS

  for (const [label, fileUrl] of docs) {
    const commands = await collectDocumentCommands(fileUrl)
    assert.ok(commands.length > 0, `${label} should document at least one npm run command`)

    const missing = findMissingCommands(commands, packageScriptsByPrefix)
    assert.deepEqual(
      missing,
      [],
      `${label} references missing npm run commands: ${missing.map(({ prefix, script }) => `${prefix}:${script}`).join(', ')}`
    )
  }
})

test('contract guard workflow only invokes npm run commands that exist in package scripts', async () => {
  const packageScriptsByPrefix = await loadPackageScripts()
  const commands = [
    ...await collectDocumentCommands(WORKFLOW_FILE),
    ...await collectDocumentCommands(FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE),
  ]
  assert.ok(commands.length > 0, 'contract guard workflows should invoke at least one npm run command')

  const missing = findMissingCommands(commands, packageScriptsByPrefix)
  assert.deepEqual(
    missing,
    [],
    `contract guard workflows reference missing npm run commands: ${missing.map(({ prefix, script }) => `${prefix}:${script}`).join(', ')}`
  )
})
