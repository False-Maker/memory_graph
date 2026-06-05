import test from 'node:test'
import assert from 'node:assert/strict'

import {
  collectFocusedSmokeWorkflowQaScripts,
  mapFocusedSmokeJobsByComparedTaskId,
  readFocusedSmokeWorkflowJobs,
  readFrontendPackageScripts,
  readWorkflowQaScriptSource,
  resolveWorkflowQaScriptPath,
} from './workflow-focused-real-smoke-contract-test-helpers.mjs'

test('readFrontendPackageScripts returns main frontend script map', async () => {
  const scripts = await readFrontendPackageScripts()
  assert.equal(typeof scripts['test:mainline-contract'], 'string')
  assert.equal(typeof scripts['qa:real-stack-smoke:search:navigation'], 'string')
})

test('mapFocusedSmokeJobsByComparedTaskId indexes compare task ids', async () => {
  const jobs = await readFocusedSmokeWorkflowJobs()
  const jobsByTask = mapFocusedSmokeJobsByComparedTaskId(jobs)

  assert.equal(jobsByTask.get('task-24')?.realSmokeRunScript, 'qa:real-stack-smoke:search:navigation')
  assert.equal(jobsByTask.get('task-45')?.realSmokeRunScript, 'qa:real-stack-smoke:dashboard:recent-memory:failure')
})

test('resolveWorkflowQaScriptPath and readWorkflowQaScriptSource resolve qa script sources', async () => {
  const scripts = await readFrontendPackageScripts()
  const qaScriptPath = resolveWorkflowQaScriptPath('qa:real-stack-smoke:search:navigation', scripts)
  assert.equal(qaScriptPath, 'src-react/qa/t24-search-navigation-real-smoke.mjs')

  const resolved = await readWorkflowQaScriptSource('qa:real-stack-smoke:search:navigation', scripts)
  assert.equal(resolved?.qaScriptRelativePath, 'src-react/qa/t24-search-navigation-real-smoke.mjs')
  assert.match(resolved?.qaScriptSource ?? '', /task-24-search-navigation-real-summary\.json/)
})

test('collectFocusedSmokeWorkflowQaScripts returns workflow jobs with resolved qa script sources', async () => {
  const qaScripts = await collectFocusedSmokeWorkflowQaScripts()
  assert.ok(qaScripts.length > 0)
  assert.ok(qaScripts.some(({ job, qaScriptRelativePath }) => (
    job.realSmokeRunScript === 'qa:real-stack-smoke:search:navigation'
    && qaScriptRelativePath === 'src-react/qa/t24-search-navigation-real-smoke.mjs'
  )))
})
