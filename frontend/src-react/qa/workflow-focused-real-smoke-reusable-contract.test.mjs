import test from 'node:test'
import assert from 'node:assert/strict'

import {
  parseFocusedRealSmokeReusableWorkflow,
  readFocusedRealSmokeReusableWorkflowSource,
} from './workflow-focused-real-smoke-helpers.mjs'

test('shared focused real smoke reusable workflow keeps the standard environment and shared action chain', async () => {
  const workflowSource = await readFocusedRealSmokeReusableWorkflowSource()
  const workflow = parseFocusedRealSmokeReusableWorkflow(workflowSource)

  assert.equal(workflow.runsOn, 'ubuntu-latest')
  assert.equal(workflow.timeoutMinutes, '25')
  assert.equal(workflow.playwrightBrowsersPath, '0')
  assert.equal(workflow.usesCheckout, true)
  assert.equal(workflow.usesSetupNode, true)
  assert.equal(workflow.usesSetupPython, true)
  assert.equal(workflow.installsFrontendDependencies, true)
  assert.equal(workflow.installsPythonDependencies, true)
  assert.equal(workflow.installsPlaywright, true)
  assert.equal(workflow.usesSharedCompareAction, true)
  assert.equal(workflow.usesSharedUploadAction, true)
})
