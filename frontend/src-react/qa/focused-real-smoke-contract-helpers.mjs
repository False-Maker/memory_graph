import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

import {
  HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
  getHighSignalFocusedRealSmokeContractCase,
  getReleaseCriticalFocusedRealSmokeContractCase,
} from './focused-real-smoke-contract-case-registry.mjs'
import {
  FOCUSED_REAL_SMOKE_TASK_GROUPS,
  getFocusedRealSmokeEvidenceFiles,
  getFocusedRealSmokeWorkflowJob,
} from './focused-real-smoke-task-registry.mjs'
import { TASK_CASES } from './focused-real-smoke-fresh-evidence-compare.mjs'

export const QA_DIR_URL = new URL('./', import.meta.url)
export const EVIDENCE_DIR_URL = new URL('../../../.sisyphus/evidence/', import.meta.url)

export async function readFocusedRealSmokeEvidenceJson(fileName) {
  return JSON.parse(await readFile(new URL(fileName, EVIDENCE_DIR_URL), 'utf8'))
}

export async function readFocusedRealSmokeTaskEvidence(taskId) {
  const evidenceFiles = getFocusedRealSmokeEvidenceFiles(taskId)
  assert.ok(evidenceFiles, `Missing focused smoke evidence files for ${taskId}`)

  return {
    summary: await readFocusedRealSmokeEvidenceJson(evidenceFiles.summaryFile),
    http: await readFocusedRealSmokeEvidenceJson(evidenceFiles.httpFile),
  }
}

export function normalizeFocusedRealSmokeTaskEvidence(taskId, evidence) {
  const taskCase = TASK_CASES[taskId]
  assert.ok(taskCase, `Missing focused smoke compare task case for ${taskId}`)
  return taskCase.normalize(evidence)
}

export async function readNormalizedFocusedRealSmokeTaskEvidence(taskId) {
  return normalizeFocusedRealSmokeTaskEvidence(taskId, await readFocusedRealSmokeTaskEvidence(taskId))
}

export function expectedFocusedRealSmokeCommand(taskId) {
  const workflowJob = getFocusedRealSmokeWorkflowJob(taskId)
  assert.ok(workflowJob, `Missing focused smoke workflow job for ${taskId}`)
  return `npm --prefix frontend run ${workflowJob.runScript}`
}

export function assertFocusedRealSmokeSummaryPassed(taskId, summary) {
  assert.equal(summary.status, 'passed')
  assert.equal(summary.command, expectedFocusedRealSmokeCommand(taskId))
}

async function readFocusedRealSmokeQaScriptSource(taskId, {
  getContractCase,
  missingCaseLabel,
  missingQaScriptLabel,
} = {}) {
  const contractCase = getContractCase(taskId)
  assert.ok(contractCase, `Missing ${missingCaseLabel} for ${taskId}`)
  assert.ok(contractCase.qaScriptFile, `Missing ${missingQaScriptLabel} for ${taskId}`)
  return readFile(new URL(contractCase.qaScriptFile, QA_DIR_URL), 'utf8')
}

export async function readHighSignalFocusedRealSmokeQaScriptSource(taskId) {
  return readFocusedRealSmokeQaScriptSource(taskId, {
    getContractCase: getHighSignalFocusedRealSmokeContractCase,
    missingCaseLabel: 'high-signal focused smoke contract case',
    missingQaScriptLabel: 'qaScriptFile for high-signal focused smoke contract case',
  })
}

export async function readReleaseCriticalFocusedRealSmokeQaScriptSource(taskId) {
  return readFocusedRealSmokeQaScriptSource(taskId, {
    getContractCase: getReleaseCriticalFocusedRealSmokeContractCase,
    missingCaseLabel: 'release-critical focused smoke contract case',
    missingQaScriptLabel: 'qaScriptFile for release-critical focused smoke contract case',
  })
}

export function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function extractBracedBlock(source, marker, { markerOffset = 0, objectSearch = '{' } = {}) {
  const markerIndex = source.indexOf(marker, markerOffset)
  assert.notEqual(markerIndex, -1, `Marker not found: ${marker}`)

  const objectStart = source.indexOf(objectSearch, markerIndex)
  assert.notEqual(objectStart, -1, `Object start not found after marker: ${marker}`)

  let depth = 0
  let inSingleQuote = false
  let inDoubleQuote = false
  let inTemplate = false
  let escaped = false

  for (let index = objectStart; index < source.length; index += 1) {
    const char = source[index]

    if (escaped) {
      escaped = false
      continue
    }

    if (char === '\\') {
      escaped = true
      continue
    }

    if (!inDoubleQuote && !inTemplate && char === '\'') {
      inSingleQuote = !inSingleQuote
      continue
    }

    if (!inSingleQuote && !inTemplate && char === '"') {
      inDoubleQuote = !inDoubleQuote
      continue
    }

    if (!inSingleQuote && !inDoubleQuote && char === '`') {
      inTemplate = !inTemplate
      continue
    }

    if (inSingleQuote || inDoubleQuote || inTemplate) continue

    if (char === '{') {
      depth += 1
    } else if (char === '}') {
      depth -= 1
      if (depth === 0) {
        return source.slice(objectStart, index + 1)
      }
    }
  }

  throw new Error(`Unterminated object block after marker: ${marker}`)
}

export function assertObjectHasKeys(block, keys, label) {
  for (const key of keys) {
    assert.match(
      block,
      new RegExp(`\\b${escapeRegExp(key)}\\s*:`),
      `${label} is missing key ${key}`
    )
  }
}

export function getFocusedRealSmokeTaskGroupTaskIds(groupName) {
  const taskIds = FOCUSED_REAL_SMOKE_TASK_GROUPS[groupName]
  assert.ok(taskIds, `Missing focused real smoke task group ${groupName}`)
  return [...taskIds].sort()
}

export function assertFocusedRealSmokeTaskIdCoverage(casesByTaskId, expectedTaskIds, label) {
  assert.deepEqual(
    Object.keys(casesByTaskId).sort(),
    [...expectedTaskIds].sort(),
    `${label} drifted from expected task ids`
  )
}

export function assertFocusedRealSmokeSchemaCase(taskId, qaScriptFile, source, casesByTaskId, label) {
  const schemaCase = casesByTaskId[taskId]
  assert.ok(schemaCase, `Missing ${label} for ${taskId}`)

  const summaryPayloadBlock = extractBracedBlock(source, 'const summaryPayload =')
  assertObjectHasKeys(summaryPayloadBlock, schemaCase.summaryKeys, `${qaScriptFile} summaryPayload`)

  const httpMarker = source.indexOf('-http.json')
  assert.notEqual(httpMarker, -1, `${qaScriptFile} should write an http.json evidence file`)
  const httpPayloadBlock = extractBracedBlock(source, 'JSON.stringify({', {
    markerOffset: httpMarker,
  })
  assertObjectHasKeys(httpPayloadBlock, schemaCase.httpKeys, `${qaScriptFile} http.json payload`)
}

export function assertFocusedRealSmokeValueCase(
  taskId,
  qaScriptFile,
  source,
  casesByTaskId,
  {
    missingCaseLabel = 'value contract case',
    missingBindingLabel = 'expected evidence binding',
  } = {}
) {
  const valueCase = casesByTaskId[taskId]
  assert.ok(valueCase, `Missing ${missingCaseLabel} for ${taskId}`)

  for (const pattern of valueCase.patterns) {
    assert.match(source, pattern, `${qaScriptFile} is missing ${missingBindingLabel}: ${pattern}`)
  }
}

export function assertFocusedRealSmokeEvidenceSampleCase(taskId, evidence, assertionsByTaskId, label) {
  const assertion = assertionsByTaskId[taskId]
  assert.ok(assertion, `Missing ${label} for ${taskId}`)
  assertion(evidence)
}

async function assertFocusedRealSmokeScriptContracts({
  taskIds,
  casesByTaskId,
  label,
  readSource,
  resolveQaScriptFile,
  assertContract,
} = {}) {
  assertFocusedRealSmokeTaskIdCoverage(casesByTaskId, taskIds, label)

  for (const taskId of taskIds) {
    const qaScriptFile = resolveQaScriptFile(taskId)
    const source = await readSource(taskId)
    assertContract(taskId, qaScriptFile, source)
  }
}

export async function assertFocusedRealSmokeGroupSchemaContracts({
  groupName,
  casesByTaskId,
  label,
  missingQaScriptLabel,
  assertContract,
} = {}) {
  const taskIds = getFocusedRealSmokeTaskGroupTaskIds(groupName)
  await assertFocusedRealSmokeScriptContracts({
    taskIds,
    casesByTaskId,
    label,
    readSource: readReleaseCriticalFocusedRealSmokeQaScriptSource,
    resolveQaScriptFile: (taskId) => {
      const contractCase = getReleaseCriticalFocusedRealSmokeContractCase(taskId)
      if (!contractCase?.qaScriptFile) {
        throw new Error(`Missing ${missingQaScriptLabel} qaScriptFile for ${taskId}`)
      }
      return contractCase.qaScriptFile
    },
    assertContract,
  })
}

export async function assertFocusedRealSmokeGroupValueContracts({
  groupName,
  casesByTaskId,
  label,
  missingQaScriptLabel,
  assertContract,
} = {}) {
  const taskIds = getFocusedRealSmokeTaskGroupTaskIds(groupName)
  await assertFocusedRealSmokeScriptContracts({
    taskIds,
    casesByTaskId,
    label,
    readSource: readReleaseCriticalFocusedRealSmokeQaScriptSource,
    resolveQaScriptFile: (taskId) => {
      const contractCase = getReleaseCriticalFocusedRealSmokeContractCase(taskId)
      if (!contractCase?.qaScriptFile) {
        throw new Error(`Missing ${missingQaScriptLabel} qaScriptFile for ${taskId}`)
      }
      return contractCase.qaScriptFile
    },
    assertContract,
  })
}

export async function assertFocusedRealSmokeGroupEvidenceSamples({
  groupName,
  assertionTaskIds,
  assertionsByTaskId,
  mapLabel,
  driftMessage,
  assertEvidenceSample,
} = {}) {
  assert.deepEqual(
    assertionTaskIds,
    getFocusedRealSmokeTaskGroupTaskIds(groupName),
    driftMessage
  )
  assertFocusedRealSmokeTaskIdCoverage(
    assertionsByTaskId,
    assertionTaskIds,
    mapLabel
  )

  for (const taskId of assertionTaskIds) {
    assertEvidenceSample(taskId, await readNormalizedFocusedRealSmokeTaskEvidence(taskId))
  }
}

export async function assertHighSignalFocusedRealSmokeSchemaContracts({
  casesByTaskId,
  label,
  assertContract,
} = {}) {
  await assertFocusedRealSmokeScriptContracts({
    taskIds: HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
    casesByTaskId,
    label,
    readSource: readHighSignalFocusedRealSmokeQaScriptSource,
    resolveQaScriptFile: (taskId) => {
      const contractCase = getHighSignalFocusedRealSmokeContractCase(taskId)
      assert.ok(contractCase?.qaScriptFile, `Missing qaScriptFile for high-signal focused smoke contract case ${taskId}`)
      return contractCase.qaScriptFile
    },
    assertContract,
  })
}

export async function assertHighSignalFocusedRealSmokeValueContracts({
  casesByTaskId,
  label,
  assertContract,
} = {}) {
  await assertFocusedRealSmokeScriptContracts({
    taskIds: HIGH_SIGNAL_FOCUSED_REAL_SMOKE_CONTRACT_TASK_IDS,
    casesByTaskId,
    label,
    readSource: readHighSignalFocusedRealSmokeQaScriptSource,
    resolveQaScriptFile: (taskId) => {
      const contractCase = getHighSignalFocusedRealSmokeContractCase(taskId)
      assert.ok(contractCase?.qaScriptFile, `Missing qaScriptFile for high-signal focused smoke contract case ${taskId}`)
      return contractCase.qaScriptFile
    },
    assertContract,
  })
}
