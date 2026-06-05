import { FOCUSED_REAL_SMOKE_WORKFLOW_JOBS } from './focused-real-smoke-task-registry.mjs'

export const FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_START = '  # BEGIN generated focused real smoke jobs'
export const FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_END = '  # END generated focused real smoke jobs'

function normalizeFocusedRealSmokeWorkflowJob(job) {
  return {
    includeSeed: true,
    includeDefaultPng: true,
    extraPaths: [],
    ...job,
  }
}

export function getNormalizedFocusedRealSmokeWorkflowJobs() {
  return FOCUSED_REAL_SMOKE_WORKFLOW_JOBS.map((job) => normalizeFocusedRealSmokeWorkflowJob(job))
}

function renderBooleanWorkflowInput(value) {
  return value ? "'true'" : "'false'"
}

function renderFocusedRealSmokeWorkflowJob(job) {
  const normalizedJob = normalizeFocusedRealSmokeWorkflowJob(job)
  const lines = [
    `  ${normalizedJob.jobId}:`,
    '    uses: ./.github/workflows/focused-real-smoke-reusable.yml',
    '    with:',
    `      artifact-name: ${normalizedJob.artifactName}`,
    `      evidence-prefix: ${normalizedJob.evidencePrefix}`,
    `      run-script: ${normalizedJob.runScript}`,
    `      task-id: ${normalizedJob.taskId}`,
  ]

  if (!normalizedJob.includeSeed) {
    lines.push(`      include-seed: ${renderBooleanWorkflowInput(normalizedJob.includeSeed)}`)
  }

  if (!normalizedJob.includeDefaultPng) {
    lines.push(`      include-default-png: ${renderBooleanWorkflowInput(normalizedJob.includeDefaultPng)}`)
  }

  if (normalizedJob.extraPaths.length > 0) {
    lines.push('      extra-paths: |')
    for (const extraPath of normalizedJob.extraPaths) {
      lines.push(`        ${extraPath}`)
    }
  }

  return lines.join('\n')
}

export function renderFocusedRealSmokeWorkflowBlock() {
  return [
    FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_START,
    getNormalizedFocusedRealSmokeWorkflowJobs().map((job) => renderFocusedRealSmokeWorkflowJob(job)).join('\n\n'),
    FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_END,
  ].join('\n')
}

export function extractFocusedRealSmokeWorkflowBlock(source) {
  const startIndex = source.indexOf(FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_START)
  const endIndex = source.indexOf(FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_END)

  if (startIndex === -1 || endIndex === -1 || endIndex < startIndex) {
    throw new Error('Focused real smoke workflow markers are missing or out of order')
  }

  return source.slice(startIndex, endIndex + FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_END.length).trimEnd()
}

export function replaceFocusedRealSmokeWorkflowBlock(source) {
  const startIndex = source.indexOf(FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_START)
  const endIndex = source.indexOf(FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_END)

  if (startIndex === -1 || endIndex === -1 || endIndex < startIndex) {
    throw new Error('Focused real smoke workflow markers are missing or out of order')
  }

  return `${source.slice(0, startIndex)}${renderFocusedRealSmokeWorkflowBlock()}${source.slice(
    endIndex + FOCUSED_REAL_SMOKE_WORKFLOW_BLOCK_END.length
  )}`
}
