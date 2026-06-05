import fs from 'node:fs'
import path from 'node:path'

import {
  getProviderMatrixEvidencePaths,
  getProviderReadinessEvidencePaths,
  parseProviderScopeArgs,
} from './t15-provider-real-stack-smoke-helpers.mjs'

export const REMOTE_DOCTOR_DEFAULT_SCOPE_ARGS = [
  '--providers', 'openai,anthropic',
  '--openai-profile', 'bigmodel',
  '--anthropic-profile', 'bigmodel',
  '--evidence-suffix', 'remote',
]

export const REMOTE_DOCTOR_EXIT_CODES = {
  green: 0,
  red: 1,
  error: 2,
}

function normalizeToken(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

function normalizeProviderName(value) {
  return normalizeToken(value).toLowerCase()
}

function sortTokens(values = []) {
  return [...values].sort((left, right) => left.localeCompare(right))
}

function formatTokenList(values = []) {
  return values.length > 0 ? values.join(',') : '-'
}

function readJsonEvidence(filePath, missingIssue, invalidIssue) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf8'))
  } catch (error) {
    if (error && typeof error === 'object' && error.code === 'ENOENT') {
      return { __doctorIssue: `${missingIssue}:${path.basename(filePath)}` }
    }
    return { __doctorIssue: `${invalidIssue}:${path.basename(filePath)}` }
  }
}

function arraysMatchMembers(expected = [], actual = []) {
  if (expected.length !== actual.length) {
    return false
  }

  return expected.every((value, index) => value === actual[index])
}

function buildErrorReport({
  providers,
  evidenceSuffix,
  generatedAt = '',
  issues = [],
}) {
  const report = {
    status: 'error',
    exitCode: REMOTE_DOCTOR_EXIT_CODES.error,
    providerScope: providers.join(','),
    evidenceSuffix: normalizeToken(evidenceSuffix) || '-',
    generatedAt: normalizeToken(generatedAt) || '-',
    issues,
  }

  report.line = [
    `remote_doctor=${report.status}`,
    `exit_code=${report.exitCode}`,
    `provider_scope=${report.providerScope || '-'}`,
    `evidence_suffix=${report.evidenceSuffix}`,
    `generated_at=${report.generatedAt}`,
    `issues=${formatTokenList(report.issues)}`,
  ].join(' ')

  return report
}

function validateCounts(payload, expectedCounts, prefix) {
  const issues = []
  if (!payload || typeof payload !== 'object' || typeof payload.counts !== 'object' || payload.counts === null) {
    return issues
  }

  for (const [field, expectedValue] of Object.entries(expectedCounts)) {
    if (!Object.prototype.hasOwnProperty.call(payload.counts, field)) {
      continue
    }

    if (payload.counts[field] !== expectedValue) {
      issues.push(`${prefix}_${field}_count_mismatch:${payload.counts[field]}!=${expectedValue}`)
    }
  }

  return issues
}

function normalizeProviderRows(payload, issuePrefix) {
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.providers)) {
    return {
      rows: [],
      providers: [],
      issues: [`${issuePrefix}_providers_missing`],
    }
  }

  const issues = []
  const providers = payload.providers.map((row, index) => {
    const provider = normalizeProviderName(row?.provider)
    if (!provider) {
      issues.push(`${issuePrefix}_provider_missing_at:${index}`)
    }
    return provider
  })

  return {
    rows: payload.providers,
    providers,
    issues,
  }
}

export function parseRemoteDoctorArgs(argv = []) {
  const scopeArgs = [...REMOTE_DOCTOR_DEFAULT_SCOPE_ARGS]
  let refresh = false

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]
    if (arg === '--refresh') {
      refresh = true
      continue
    }
    scopeArgs.push(arg)
  }

  return {
    refresh,
    scopeArgs,
    ...parseProviderScopeArgs(scopeArgs),
  }
}

export function loadRemoteDoctorEvidence(evidenceDir, evidenceSuffix = 'remote') {
  const readinessPaths = getProviderReadinessEvidencePaths(evidenceDir, evidenceSuffix)
  const matrixPaths = getProviderMatrixEvidencePaths(evidenceDir, evidenceSuffix)
  const readiness = readJsonEvidence(
    readinessPaths.json,
    'missing_readiness_evidence',
    'invalid_readiness_evidence'
  )
  const matrix = readJsonEvidence(
    matrixPaths.json,
    'missing_matrix_evidence',
    'invalid_matrix_evidence'
  )

  const issues = []
  if (readiness?.__doctorIssue) {
    issues.push(readiness.__doctorIssue)
  }
  if (matrix?.__doctorIssue) {
    issues.push(matrix.__doctorIssue)
  }

  return {
    readinessPath: readinessPaths.json,
    matrixPath: matrixPaths.json,
    readiness: readiness?.__doctorIssue ? null : readiness,
    matrix: matrix?.__doctorIssue ? null : matrix,
    issues,
  }
}

export function evaluateRemoteDoctorEvidence({
  readiness,
  matrix,
  providers = [],
  evidenceSuffix = 'remote',
  expectedReadinessEvidenceRef = '',
  loadIssues = [],
}) {
  const expectedProviders = providers.map((provider) => normalizeProviderName(provider)).filter(Boolean)
  const sortedExpectedProviders = sortTokens(expectedProviders)
  const baseIssues = [...loadIssues]

  if (!readiness || !matrix) {
    const generatedAt = normalizeToken(matrix?.generated_at) || normalizeToken(readiness?.generated_at)
    return buildErrorReport({
      providers: expectedProviders,
      evidenceSuffix,
      generatedAt,
      issues: baseIssues,
    })
  }

  const readinessRows = normalizeProviderRows(readiness, 'readiness')
  const matrixRows = normalizeProviderRows(matrix, 'matrix')
  const issues = [
    ...baseIssues,
    ...readinessRows.issues,
    ...matrixRows.issues,
  ]
  const normalizedReadinessProviders = sortTokens(readinessRows.providers.filter(Boolean))
  const normalizedMatrixProviders = sortTokens(matrixRows.providers.filter(Boolean))
  const expectedScope = expectedProviders.join(',')
  const generatedAt = normalizeToken(matrix.generated_at) || normalizeToken(readiness.generated_at) || '-'

  if (normalizeToken(readiness.provider_scope) && normalizeToken(readiness.provider_scope) !== expectedScope) {
    issues.push(`readiness_provider_scope_mismatch:${normalizeToken(readiness.provider_scope)}`)
  }
  if (normalizeToken(matrix.provider_scope) && normalizeToken(matrix.provider_scope) !== expectedScope) {
    issues.push(`matrix_provider_scope_mismatch:${normalizeToken(matrix.provider_scope)}`)
  }
  if (!arraysMatchMembers(sortedExpectedProviders, normalizedReadinessProviders)) {
    issues.push(`readiness_provider_mismatch:${formatTokenList(normalizedReadinessProviders)}`)
  }
  if (!arraysMatchMembers(sortedExpectedProviders, normalizedMatrixProviders)) {
    issues.push(`matrix_provider_mismatch:${formatTokenList(normalizedMatrixProviders)}`)
  }
  if (normalizeToken(evidenceSuffix) !== normalizeToken(readiness.evidence_suffix)) {
    issues.push(`readiness_evidence_suffix_mismatch:${normalizeToken(readiness.evidence_suffix) || '-'}`)
  }
  if (normalizeToken(evidenceSuffix) !== normalizeToken(matrix.evidence_suffix)) {
    issues.push(`matrix_evidence_suffix_mismatch:${normalizeToken(matrix.evidence_suffix) || '-'}`)
  }
  if (
    normalizeToken(expectedReadinessEvidenceRef)
    && normalizeToken(matrix.readiness_evidence)
    && normalizeToken(matrix.readiness_evidence) !== normalizeToken(expectedReadinessEvidenceRef)
  ) {
    issues.push(`matrix_readiness_evidence_mismatch:${normalizeToken(matrix.readiness_evidence)}`)
  }

  const readinessBlockedProviders = readinessRows.rows
    .filter((row) => row?.ready !== true)
    .map((row) => normalizeProviderName(row?.provider))
    .filter(Boolean)
  const readinessReadyCount = readinessRows.rows.filter((row) => row?.ready === true).length
  const matrixPassedProviders = matrixRows.rows
    .filter((row) => row?.status === 'passed')
    .map((row) => normalizeProviderName(row?.provider))
    .filter(Boolean)
  const matrixBlockedProviders = matrixRows.rows
    .filter((row) => row?.status === 'blocked')
    .map((row) => normalizeProviderName(row?.provider))
    .filter(Boolean)
  const matrixFailedProviders = matrixRows.rows
    .filter((row) => row?.status === 'failed')
    .map((row) => normalizeProviderName(row?.provider))
    .filter(Boolean)

  for (const row of matrixRows.rows) {
    const provider = normalizeProviderName(row?.provider) || 'unknown'
    const status = normalizeToken(row?.status)
    const readinessState = normalizeToken(row?.readiness)

    if (!['passed', 'blocked', 'failed'].includes(status)) {
      issues.push(`matrix_unknown_status:${provider}:${status || '-'}`)
    }

    if (status === 'passed' && readinessState && readinessState !== 'ready') {
      issues.push(`matrix_readiness_mismatch:${provider}:${readinessState}`)
    }

    if (status === 'blocked' && readinessState && readinessState !== 'blocked') {
      issues.push(`matrix_readiness_mismatch:${provider}:${readinessState}`)
    }
  }

  issues.push(
    ...validateCounts(readiness, {
      ready: readinessReadyCount,
      blocked: readinessBlockedProviders.length,
    }, 'readiness'),
    ...validateCounts(matrix, {
      passed: matrixPassedProviders.length,
      blocked: matrixBlockedProviders.length,
      failed: matrixFailedProviders.length,
    }, 'matrix')
  )

  if (issues.length > 0) {
    return buildErrorReport({
      providers: expectedProviders,
      evidenceSuffix,
      generatedAt,
      issues: sortTokens(issues),
    })
  }

  const status = readinessBlockedProviders.length === 0 && matrixBlockedProviders.length === 0 && matrixFailedProviders.length === 0
    ? 'green'
    : 'red'
  const exitCode = REMOTE_DOCTOR_EXIT_CODES[status]
  const report = {
    status,
    exitCode,
    providerScope: expectedScope,
    evidenceSuffix: normalizeToken(evidenceSuffix) || '-',
    generatedAt,
    readinessReadyCount,
    readinessBlockedProviders: sortTokens(readinessBlockedProviders),
    matrixPassedCount: matrixPassedProviders.length,
    matrixBlockedProviders: sortTokens(matrixBlockedProviders),
    matrixFailedProviders: sortTokens(matrixFailedProviders),
  }

  report.line = [
    `remote_doctor=${report.status}`,
    `exit_code=${report.exitCode}`,
    `provider_scope=${report.providerScope || '-'}`,
    `evidence_suffix=${report.evidenceSuffix}`,
    `generated_at=${report.generatedAt}`,
    `readiness_ready=${report.readinessReadyCount}/${expectedProviders.length}`,
    `readiness_blocked=${formatTokenList(report.readinessBlockedProviders)}`,
    `matrix_passed=${report.matrixPassedCount}/${expectedProviders.length}`,
    `matrix_blocked=${formatTokenList(report.matrixBlockedProviders)}`,
    `matrix_failed=${formatTokenList(report.matrixFailedProviders)}`,
  ].join(' ')

  return report
}
