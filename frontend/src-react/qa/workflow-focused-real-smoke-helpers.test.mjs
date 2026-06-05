import test from 'node:test'
import assert from 'node:assert/strict'

import {
  parseFocusedRealSmokeReusableWorkflow,
  parseFocusedSmokeWorkflowJobs,
} from './workflow-focused-real-smoke-helpers.mjs'

test('parseFocusedSmokeWorkflowJobs handles shared upload action fields and extra paths from synthetic workflow', () => {
  const jobs = parseFocusedSmokeWorkflowJobs(`
  sample-job:
    steps:
      - name: Upload evidence
        uses: ./.github/actions/focused-real-smoke-upload
        with:
          artifact-name: sample-evidence
          evidence-prefix: task-99-sample-real
          include-seed: false
          include-default-png: false
          extra-paths: |
            .sisyphus/evidence/task-99-custom-a.txt
            .sisyphus/evidence/task-99-custom-b.txt
`)

  assert.equal(jobs.length, 1)
  assert.equal(jobs[0].artifactName, 'sample-evidence')
  assert.equal(jobs[0].usesSharedUploadAction, true)
  assert.deepEqual(jobs[0].artifactPaths, [
    '.sisyphus/evidence/task-99-sample-real-summary.txt',
    '.sisyphus/evidence/task-99-sample-real-summary.json',
    '.sisyphus/evidence/task-99-sample-real-http.json',
    '.sisyphus/evidence/task-99-sample-real-error.txt',
    '.sisyphus/evidence/task-99-sample-real-backend.log',
    '.sisyphus/evidence/task-99-custom-a.txt',
    '.sisyphus/evidence/task-99-custom-b.txt',
  ])
})

test('parseFocusedSmokeWorkflowJobs handles reusable workflow artifact and compare inputs from synthetic workflow', () => {
  const jobs = parseFocusedSmokeWorkflowJobs(`
  sample-job:
    uses: ./.github/workflows/focused-real-smoke-reusable.yml
    with:
      artifact-name: sample-evidence
      evidence-prefix: task-24-search-navigation-real
      run-script: qa:real-stack-smoke:search:navigation
      task-id: task-24
      include-seed: "true"
      include-default-png: "false"
      extra-paths: |
        .sisyphus/evidence/task-24-extra.log

`)

  assert.equal(jobs.length, 1)
  assert.equal(jobs[0].usesSharedReusableWorkflow, true)
  assert.equal(jobs[0].usesSharedCompareAction, true)
  assert.equal(jobs[0].usesSharedUploadAction, true)
  assert.equal(jobs[0].realSmokeRunScript, 'qa:real-stack-smoke:search:navigation')
  assert.deepEqual(jobs[0].compareTaskIds, ['task-24'])
  assert.deepEqual(jobs[0].artifactPaths, [
    '.sisyphus/evidence/task-24-search-navigation-real-summary.txt',
    '.sisyphus/evidence/task-24-search-navigation-real-summary.json',
    '.sisyphus/evidence/task-24-search-navigation-real-http.json',
    '.sisyphus/evidence/task-24-search-navigation-real-error.txt',
    '.sisyphus/evidence/task-24-search-navigation-real-backend.log',
    '.sisyphus/evidence/task-24-search-navigation-real-seed.json',
    '.sisyphus/evidence/task-24-extra.log',
  ])
})

test('parseFocusedRealSmokeReusableWorkflow reads reusable workflow booleans from source', () => {
  const workflow = parseFocusedRealSmokeReusableWorkflow(`
name: sample
jobs:
  qa:
    runs-on: ubuntu-latest
    timeout-minutes: 25
    env:
      PLAYWRIGHT_BROWSERS_PATH: 0
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
      - uses: actions/setup-python@v5
      - run: npm --prefix frontend ci
      - run: python -m pip install -r requirements.txt
      - run: npx --prefix frontend playwright install --with-deps chromium
      - uses: ./.github/actions/focused-real-smoke-compare
      - uses: ./.github/actions/focused-real-smoke-upload
`)

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
