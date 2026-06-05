import test from 'node:test'
import assert from 'node:assert/strict'

import {
  extractDocumentCommandsFromSource,
  collectPytestTargetsFromSource,
  globPatternToRegExp,
} from './documented-contract-test-helpers.mjs'

test('extractDocumentCommandsFromSource parses frontend and sidecar npm run commands', () => {
  const commands = extractDocumentCommandsFromSource(`
npm --prefix frontend run build
npm --prefix frontend/api run build
`)

  assert.deepEqual(commands, [
    { prefix: 'frontend', script: 'build' },
    { prefix: 'frontend/api', script: 'build' },
  ])
})

test('collectPytestTargetsFromSource extracts concrete pytest targets', () => {
  const targets = collectPytestTargetsFromSource(`
python -m pytest tests/test_config.py tests/test_secret_store.py --maxfail=1
`)

  assert.deepEqual(targets, [
    'tests/test_config.py',
    'tests/test_secret_store.py',
  ])
})

test('globPatternToRegExp supports wildcard pytest patterns', () => {
  const pattern = globPatternToRegExp('tests/test_*api*.py')
  assert.equal(pattern.test('tests/test_main_api.py'), true)
  assert.equal(pattern.test('tests/test_config.py'), false)
})
