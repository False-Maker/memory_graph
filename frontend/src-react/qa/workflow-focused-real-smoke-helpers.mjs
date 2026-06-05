import { readFile } from 'node:fs/promises'

export const WORKFLOW_FILE = new URL('../../../.github/workflows/contract-guards.yml', import.meta.url)
export const FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE = new URL(
  '../../../.github/workflows/focused-real-smoke-reusable.yml',
  import.meta.url
)
export const REAL_SMOKE_RUN_PATTERN = /run:\s+npm --prefix frontend run (qa:real-stack-smoke(?:[:A-Za-z0-9_-]+)?)/
export const COMPARE_RUN_PATTERN = /run:\s+npm --prefix frontend run qa:focused-real-smoke:compare -- --task (task-\d+) --baseline-dir \/tmp\/committed-evidence --fresh-dir \.sisyphus\/evidence/
export const PRESERVE_COPY_PATTERN = /cp \.sisyphus\/evidence\/(task-\d+)-[A-Za-z0-9-]+-(summary|http)\.json/
export const SHARED_COMPARE_ACTION_PATH = './.github/actions/focused-real-smoke-compare'
export const SHARED_UPLOAD_ACTION_PATH = './.github/actions/focused-real-smoke-upload'
export const SHARED_FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_PATH = './.github/workflows/focused-real-smoke-reusable.yml'
const ACTION_USES_PATTERN = /uses:\s+\.\/\.github\/actions\/focused-real-smoke-compare/
const UPLOAD_ACTION_USES_PATTERN = /uses:\s+\.\/\.github\/actions\/focused-real-smoke-upload/
const REUSABLE_WORKFLOW_USES_PATTERN = /uses:\s+\.\/\.github\/workflows\/focused-real-smoke-reusable\.yml/

export async function readContractGuardsWorkflowSource() {
  return readFile(WORKFLOW_FILE, 'utf8')
}

export async function readFocusedRealSmokeReusableWorkflowSource() {
  return readFile(FOCUSED_REAL_SMOKE_REUSABLE_WORKFLOW_FILE, 'utf8')
}

export function extractTaskIdFromArtifactPath(artifactPath) {
  const match = artifactPath.match(/(task-\d+)-/)
  return match?.[1] ?? null
}

export function extractTaskIdFromEvidencePrefix(evidencePrefix) {
  const match = String(evidencePrefix || '').match(/^(task-\d+)-/)
  return match?.[1] ?? null
}

export function extractTaskIdsFromArtifactPaths(artifactPaths) {
  return [...new Set(artifactPaths.map((artifactPath) => extractTaskIdFromArtifactPath(artifactPath)).filter(Boolean))].sort()
}

function buildStandardArtifactPaths({ evidencePrefix, includeSeed = true, includeDefaultPng = true, extraPaths = [] }) {
  const paths = [
    `.sisyphus/evidence/${evidencePrefix}-summary.txt`,
    `.sisyphus/evidence/${evidencePrefix}-summary.json`,
    `.sisyphus/evidence/${evidencePrefix}-http.json`,
    `.sisyphus/evidence/${evidencePrefix}-error.txt`,
    `.sisyphus/evidence/${evidencePrefix}-backend.log`,
  ]

  if (includeSeed) {
    paths.push(`.sisyphus/evidence/${evidencePrefix}-seed.json`)
  }

  if (includeDefaultPng) {
    paths.push(`.sisyphus/evidence/${evidencePrefix}.png`)
  }

  return [...paths, ...extraPaths]
}

function indentationLength(line) {
  return line.match(/^\s*/)?.[0]?.length ?? 0
}

function parseBooleanWorkflowInput(rawValue) {
  return rawValue.replace(/['"]/g, '') === 'true'
}

function collectIndentedBlock(lines, startIndex, parentIndent) {
  const values = []
  let nextIndex = startIndex + 1

  for (; nextIndex < lines.length; nextIndex += 1) {
    const line = lines[nextIndex]
    if (!line.trim()) break
    if (indentationLength(line) <= parentIndent) break
    values.push(line.trim())
  }

  return {
    values,
    nextIndex,
  }
}

function isActionStepBoundary(line) {
  return /^\s*$/.test(line) || /^      - name: /.test(line) || /^  [a-z0-9-]+:$/.test(line)
}

function applyCompareActionFields(target, line, onRunScript) {
  const taskIdMatch = line.match(/task-id:\s+(task-\d+)/)
  if (taskIdMatch) {
    target.taskId = taskIdMatch[1]
  }

  const runScriptMatch = line.match(/run-script:\s+(qa:real-stack-smoke(?:[:A-Za-z0-9_-]+)?)/)
  if (runScriptMatch) {
    target.runScript = runScriptMatch[1]
    if (onRunScript) onRunScript(runScriptMatch[1])
  }

  const evidencePrefixMatch = line.match(/evidence-prefix:\s+([A-Za-z0-9-]+)/)
  if (evidencePrefixMatch) {
    target.evidencePrefix = evidencePrefixMatch[1]
  }
}

function applyArtifactWorkflowFields(target, line) {
  const artifactNameMatch = line.match(/artifact-name:\s+([A-Za-z0-9._-]+)/)
  if (artifactNameMatch) {
    target.artifactName = artifactNameMatch[1]
  }

  const evidencePrefixMatch = line.match(/evidence-prefix:\s+([A-Za-z0-9-]+)/)
  if (evidencePrefixMatch) {
    target.evidencePrefix = evidencePrefixMatch[1]
  }

  const includeSeedMatch = line.match(/include-seed:\s+(true|false|['"][^'"]+['"])/)
  if (includeSeedMatch) {
    target.includeSeed = parseBooleanWorkflowInput(includeSeedMatch[1])
  }

  const includeDefaultPngMatch = line.match(/include-default-png:\s+(true|false|['"][^'"]+['"])/)
  if (includeDefaultPngMatch) {
    target.includeDefaultPng = parseBooleanWorkflowInput(includeDefaultPngMatch[1])
  }
}

function consumeExtraPathsLiteral(target, lines, index, line) {
  if (!/extra-paths:\s+\|$/.test(line)) return index
  const { values, nextIndex } = collectIndentedBlock(lines, index, indentationLength(line))
  target.extraPaths.push(...values)
  return nextIndex - 1
}

function createEmptyJob(jobId) {
  return {
    jobId,
    realSmokeRunScript: null,
    compareTaskIds: [],
    artifactName: null,
    artifactPaths: [],
    preservedEvidenceByTask: new Map(),
    preservedTaskIds: [],
    usesSharedCompareAction: false,
    usesSharedUploadAction: false,
    usesSharedReusableWorkflow: false,
  }
}

function finalizeCompareAction(currentJob, currentActionJob) {
  if (!currentJob || !currentActionJob?.taskId) return
  currentJob.compareTaskIds.push(currentActionJob.taskId)
  if (!currentJob.preservedEvidenceByTask.has(currentActionJob.taskId)) {
    currentJob.preservedEvidenceByTask.set(currentActionJob.taskId, new Set(['summary', 'http']))
  }
}

function finalizeUploadAction(currentJob, currentUploadAction) {
  if (!currentJob || !currentUploadAction?.evidencePrefix) return
  currentJob.artifactName = currentUploadAction.artifactName ?? currentJob.artifactName
  currentJob.artifactPaths.push(
    ...buildStandardArtifactPaths({
      evidencePrefix: currentUploadAction.evidencePrefix,
      includeSeed: currentUploadAction.includeSeed,
      includeDefaultPng: currentUploadAction.includeDefaultPng,
      extraPaths: currentUploadAction.extraPaths,
    })
  )
}

function finalizeReusableWorkflowCall(currentJob, currentReusableWorkflowCall) {
  if (!currentJob || !currentReusableWorkflowCall) return

  currentJob.usesSharedCompareAction = true
  currentJob.usesSharedUploadAction = true
  currentJob.artifactName = currentReusableWorkflowCall.artifactName ?? currentJob.artifactName

  if (currentReusableWorkflowCall.runScript) {
    currentJob.realSmokeRunScript = currentReusableWorkflowCall.runScript
  }

  if (currentReusableWorkflowCall.taskId) {
    currentJob.compareTaskIds.push(currentReusableWorkflowCall.taskId)
    if (!currentJob.preservedEvidenceByTask.has(currentReusableWorkflowCall.taskId)) {
      currentJob.preservedEvidenceByTask.set(currentReusableWorkflowCall.taskId, new Set(['summary', 'http']))
    }
  }

  if (currentReusableWorkflowCall.evidencePrefix) {
    currentJob.artifactPaths.push(
      ...buildStandardArtifactPaths({
        evidencePrefix: currentReusableWorkflowCall.evidencePrefix,
        includeSeed: currentReusableWorkflowCall.includeSeed,
        includeDefaultPng: currentReusableWorkflowCall.includeDefaultPng,
        extraPaths: currentReusableWorkflowCall.extraPaths,
      })
    )
  }
}

function finalizeJob(currentJob, currentActionJob, currentUploadAction, currentReusableWorkflowCall) {
  if (!currentJob) return null

  finalizeCompareAction(currentJob, currentActionJob)
  finalizeUploadAction(currentJob, currentUploadAction)
  finalizeReusableWorkflowCall(currentJob, currentReusableWorkflowCall)

  currentJob.compareTaskIds = [...new Set(currentJob.compareTaskIds)].sort()
  currentJob.preservedTaskIds = [...currentJob.preservedEvidenceByTask.keys()].sort()
  return currentJob
}

export function parseFocusedSmokeWorkflowJobs(source) {
  const lines = source.split('\n')
  const jobs = []
  let currentJob = null
  let currentActionJob = null
  let currentUploadAction = null
  let currentReusableWorkflowCall = null

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index]
    const jobMatch = line.match(/^  ([a-z0-9-]+):$/)

    if (jobMatch) {
      const finalizedJob = finalizeJob(currentJob, currentActionJob, currentUploadAction, currentReusableWorkflowCall)
      if (finalizedJob) {
        jobs.push(finalizedJob)
      }
      currentJob = createEmptyJob(jobMatch[1])
      currentActionJob = null
      currentUploadAction = null
      currentReusableWorkflowCall = null
      continue
    }

    if (!currentJob) continue

    if (ACTION_USES_PATTERN.test(line)) {
      currentJob.usesSharedCompareAction = true
      currentActionJob = {
        taskId: null,
        runScript: null,
        evidencePrefix: null,
      }
      continue
    }

    if (UPLOAD_ACTION_USES_PATTERN.test(line)) {
      currentJob.usesSharedUploadAction = true
      currentUploadAction = {
        artifactName: null,
        evidencePrefix: null,
        includeSeed: true,
        includeDefaultPng: true,
        extraPaths: [],
      }
      continue
    }

    if (REUSABLE_WORKFLOW_USES_PATTERN.test(line)) {
      currentJob.usesSharedReusableWorkflow = true
      currentReusableWorkflowCall = {
        artifactName: null,
        evidencePrefix: null,
        runScript: null,
        taskId: null,
        includeSeed: true,
        includeDefaultPng: true,
        extraPaths: [],
      }
      continue
    }

    if (currentActionJob) {
      applyCompareActionFields(currentActionJob, line, (runScript) => {
        currentJob.realSmokeRunScript = runScript
      })

      if (isActionStepBoundary(line)) {
        finalizeCompareAction(currentJob, currentActionJob)
        currentActionJob = null
      }
    }

    if (currentUploadAction) {
      applyArtifactWorkflowFields(currentUploadAction, line)
      currentJob.artifactName = currentUploadAction.artifactName ?? currentJob.artifactName
      index = consumeExtraPathsLiteral(currentUploadAction, lines, index, line)

      if (isActionStepBoundary(line)) {
        finalizeUploadAction(currentJob, currentUploadAction)
        currentUploadAction = null
      }
    }

    if (currentReusableWorkflowCall) {
      applyArtifactWorkflowFields(currentReusableWorkflowCall, line)
      applyCompareActionFields(currentReusableWorkflowCall, line)
      index = consumeExtraPathsLiteral(currentReusableWorkflowCall, lines, index, line)

      if (/^\s*$/.test(line)) {
        finalizeReusableWorkflowCall(currentJob, currentReusableWorkflowCall)
        currentReusableWorkflowCall = null
      }
    }

    const realSmokeRunMatch = line.match(REAL_SMOKE_RUN_PATTERN)
    if (realSmokeRunMatch) {
      currentJob.realSmokeRunScript = realSmokeRunMatch[1]
    }

    const compareRunMatch = line.match(COMPARE_RUN_PATTERN)
    if (compareRunMatch) {
      currentJob.compareTaskIds.push(compareRunMatch[1])
    }

    const preserveCopyMatch = line.match(PRESERVE_COPY_PATTERN)
    if (preserveCopyMatch) {
      const [, taskId, evidenceKind] = preserveCopyMatch
      if (!currentJob.preservedEvidenceByTask.has(taskId)) {
        currentJob.preservedEvidenceByTask.set(taskId, new Set())
      }
      currentJob.preservedEvidenceByTask.get(taskId).add(evidenceKind)
    }

    if (/^\s+path:\s+\|$/.test(line)) {
      for (let artifactIndex = index + 1; artifactIndex < lines.length; artifactIndex += 1) {
        const artifactLine = lines[artifactIndex]
        if (!/^\s{12}\S/.test(artifactLine)) break
        currentJob.artifactPaths.push(artifactLine.trim())
      }
    }
  }

  const finalizedJob = finalizeJob(currentJob, currentActionJob, currentUploadAction, currentReusableWorkflowCall)
  if (finalizedJob) {
    jobs.push(finalizedJob)
  }

  return jobs
}

export function parseFocusedRealSmokeReusableWorkflow(source) {
  return {
    runsOn: source.match(/runs-on:\s+([^\n]+)/)?.[1]?.trim() ?? null,
    timeoutMinutes: source.match(/timeout-minutes:\s+(\d+)/)?.[1] ?? null,
    playwrightBrowsersPath: source.match(/PLAYWRIGHT_BROWSERS_PATH:\s+([^\n]+)/)?.[1]?.trim() ?? null,
    usesCheckout: /uses:\s+actions\/checkout@v4/.test(source),
    usesSetupNode: /uses:\s+actions\/setup-node@v4/.test(source),
    usesSetupPython: /uses:\s+actions\/setup-python@v5/.test(source),
    installsFrontendDependencies: /run:\s+npm --prefix frontend ci/.test(source),
    installsPythonDependencies: /run:\s+python -m pip install -r requirements\.txt/.test(source),
    installsPlaywright: /run:\s+npx --prefix frontend playwright install --with-deps chromium/.test(source),
    usesSharedCompareAction: ACTION_USES_PATTERN.test(source),
    usesSharedUploadAction: UPLOAD_ACTION_USES_PATTERN.test(source),
  }
}
