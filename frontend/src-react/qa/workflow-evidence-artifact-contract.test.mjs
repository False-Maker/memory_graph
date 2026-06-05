import test from 'node:test'
import assert from 'node:assert/strict'
import path from 'node:path'
import {
  collectFocusedSmokeWorkflowQaScripts,
} from './workflow-focused-real-smoke-contract-test-helpers.mjs'
const SCRIPT_EVIDENCE_BASENAME_PATTERN = /\btask-[A-Za-z0-9-]+\.(?:txt|json|png|log)\b/g

function extractEvidenceBasenames(scriptSource) {
  return new Set(scriptSource.match(SCRIPT_EVIDENCE_BASENAME_PATTERN) || [])
}

test('focused smoke workflow artifact paths exactly match evidence filenames referenced by their qa scripts', async () => {
  const jobs = await collectFocusedSmokeWorkflowQaScripts()
  let checkedJobs = 0

  for (const { job, qaScriptRelativePath, qaScriptSource } of jobs) {
    if (job.artifactPaths.length === 0) continue
    checkedJobs += 1
    const evidenceBasenames = [...extractEvidenceBasenames(qaScriptSource)].sort()
    const workflowBasenames = [...new Set(job.artifactPaths.map((artifactPath) => path.basename(artifactPath)))].sort()
    const missingInWorkflow = evidenceBasenames.filter((basename) => !workflowBasenames.includes(basename))
    const extraInWorkflow = workflowBasenames.filter((basename) => !evidenceBasenames.includes(basename))

    assert.deepEqual(
      missingInWorkflow,
      [],
      `${job.jobId} does not upload all evidence files referenced by ${qaScriptRelativePath}: ${missingInWorkflow.join(', ')}`
    )
    assert.deepEqual(
      extraInWorkflow,
      [],
      `${job.jobId} uploads evidence files not referenced by ${qaScriptRelativePath}: ${extraInWorkflow.join(', ')}`
    )
  }

  assert.ok(checkedJobs > 0, 'expected at least one focused smoke workflow job to be checked')
})
