import test from 'node:test'
import assert from 'node:assert/strict'
import {
  collectFocusedSmokeWorkflowQaScripts,
} from './workflow-focused-real-smoke-contract-test-helpers.mjs'

test('focused smoke qa scripts keep the minimum summary/http evidence content contract', async () => {
  const jobs = await collectFocusedSmokeWorkflowQaScripts()
  let checkedJobs = 0

  for (const { job, qaScriptRelativePath, qaScriptSource } of jobs) {
    checkedJobs += 1

    assert.match(
      qaScriptSource,
      /const\s+summaryPayload\s*=\s*\{/,
      `${job.jobId} is missing summaryPayload in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /generated_at\s*:/,
      `${job.jobId} is missing summaryPayload.generated_at in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /command\s*:/,
      `${job.jobId} is missing summaryPayload.command in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /status\s*:\s*['"]passed['"]/,
      `${job.jobId} is missing summaryPayload.status=passed in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /const\s+summaryText\s*=\s*\[/,
      `${job.jobId} is missing summaryText in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /generated_at=\$\{summaryPayload\.generated_at\}/,
      `${job.jobId} is missing generated_at summary line in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /command=\$\{summaryPayload\.command\}/,
      `${job.jobId} is missing command summary line in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /status=\$\{summaryPayload\.status\}/,
      `${job.jobId} is missing status summary line in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /summary\.txt/,
      `${job.jobId} is missing summary.txt evidence output in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /summary\.json/,
      `${job.jobId} is missing summary.json evidence output in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /http\.json/,
      `${job.jobId} is missing http.json evidence output in ${qaScriptRelativePath}`
    )
    assert.match(
      qaScriptSource,
      /process\.stdout\.write\(/,
      `${job.jobId} is missing final summary stdout emission in ${qaScriptRelativePath}`
    )
  }

  assert.ok(checkedJobs > 0, 'expected at least one focused smoke qa script to be checked')
})
