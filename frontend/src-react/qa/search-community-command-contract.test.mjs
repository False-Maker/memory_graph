import test from 'node:test'
import assert from 'node:assert/strict'
import {
  mapFocusedSmokeJobsByComparedTaskId,
  readFocusedSmokeWorkflowJobs,
  readFrontendPackageScripts,
} from './workflow-focused-real-smoke-contract-test-helpers.mjs'

test('search community source/result focused smoke aliases stay explicit and backwards compatible', async () => {
  const scripts = await readFrontendPackageScripts()

  assert.equal(
    scripts['qa:real-stack-smoke:search:source-community:stale-link'],
    'node src-react/qa/t39-search-community-stale-link-real-smoke.mjs'
  )
  assert.equal(
    scripts['qa:real-stack-smoke:search:community:stale-link'],
    'node src-react/qa/t39-search-community-stale-link-real-smoke.mjs'
  )
  assert.equal(
    scripts['qa:real-stack-smoke:search:result-community:data-failure'],
    'node src-react/qa/t42-search-community-data-failure-real-smoke.mjs'
  )
  assert.equal(
    scripts['qa:real-stack-smoke:search:community:data-failure'],
    'node src-react/qa/t42-search-community-data-failure-real-smoke.mjs'
  )
  assert.equal(
    scripts['qa:real-stack-smoke:search:result-community:summary:facet-failure'],
    'node src-react/qa/t44-search-community-summary-facet-failure-real-smoke.mjs'
  )
  assert.equal(
    scripts['qa:real-stack-smoke:search:community:summary:facet-failure'],
    'node src-react/qa/t44-search-community-summary-facet-failure-real-smoke.mjs'
  )
})

test('contract guard workflow runs the explicit search community source/result aliases', async () => {
  const jobsByTask = mapFocusedSmokeJobsByComparedTaskId(await readFocusedSmokeWorkflowJobs())

  assert.equal(jobsByTask.get('task-39')?.realSmokeRunScript, 'qa:real-stack-smoke:search:source-community:stale-link')
  assert.equal(jobsByTask.get('task-42')?.realSmokeRunScript, 'qa:real-stack-smoke:search:result-community:data-failure')
  assert.equal(
    jobsByTask.get('task-44')?.realSmokeRunScript,
    'qa:real-stack-smoke:search:result-community:summary:facet-failure'
  )
  assert.equal(jobsByTask.get('task-39')?.usesSharedReusableWorkflow, true)
  assert.equal(jobsByTask.get('task-42')?.usesSharedReusableWorkflow, true)
  assert.equal(jobsByTask.get('task-44')?.usesSharedReusableWorkflow, true)
})
