import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import fs from 'node:fs'
import path from 'node:path'

import {
  buildProviderSmokeArgv,
  buildQaRuntimeEnv,
  getProviderMatrixEvidencePaths,
  getProviderMatrixLogPath,
  getProviderReadinessEvidencePaths,
  buildProviderReadinessRows,
  buildProviderSmokeHint,
  getProviderSmokeCommand,
  parseProviderScopeArgs,
  resetProviderSmokeEvidenceFiles,
  writeProviderReadinessEvidence,
  writeProviderSmokeEvidence,
} from './t15-provider-real-stack-smoke-helpers.mjs'
import { loadProviderConnectionProbe, loadProviderProbe } from './t15-provider-probe.mjs'
import {
  buildProviderMatrixSummary,
  extractSummaryField,
} from './t16-provider-matrix-helpers.mjs'

const FRONTEND_ROOT = process.cwd()
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

function resolveCommand(command) {
  if (process.platform === 'win32' && command === 'npm') {
    return 'npm.cmd'
  }
  return command
}

function getProviderSummaryPath(provider) {
  return path.join(EVIDENCE_DIR, `task-15-provider-smoke-${provider}-summary.txt`)
}

function summarizeText(raw, maxLines = 4) {
  if (typeof raw !== 'string' || !raw.trim()) {
    return ''
  }

  return raw
    .trim()
    .split('\n')
    .slice(0, maxLines)
    .join(' | ')
}

function readOptionalFile(filePath) {
  try {
    return fs.readFileSync(filePath, 'utf8')
  } catch {
    return ''
  }
}

async function runProvider(provider, overrides = {}, qaEnv = process.env, evidenceSuffix = '') {
  const command = getProviderSmokeCommand(provider, overrides)
  const logChunks = []
  const providerArgs = buildProviderSmokeArgv(provider, overrides)
  const npmArgs = providerArgs.length > 0
    ? ['run', `qa:real-stack-smoke:${provider}`, '--', ...providerArgs]
    : ['run', `qa:real-stack-smoke:${provider}`]

  const exitCode = await new Promise((resolve, reject) => {
    const child = spawn(resolveCommand('npm'), npmArgs, {
      cwd: FRONTEND_ROOT,
      env: qaEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
    })

    child.stdout.on('data', (chunk) => {
      logChunks.push(String(chunk))
    })
    child.stderr.on('data', (chunk) => {
      logChunks.push(String(chunk))
    })

    child.on('exit', (code) => resolve(code ?? 1))
    child.on('error', reject)
  })

  const logPath = getProviderMatrixLogPath(EVIDENCE_DIR, provider, evidenceSuffix)
  await writeFile(logPath, logChunks.join(''), 'utf8')

  const summaryPath = getProviderSummaryPath(provider)
  const summaryRaw = readOptionalFile(summaryPath)
  const summaryStatus = extractSummaryField(summaryRaw, 'status')
  const summaryReason = extractSummaryField(summaryRaw, 'error') || extractSummaryField(summaryRaw, 'child_error_excerpt')
  const hint = extractSummaryField(summaryRaw, 'hint') || buildProviderSmokeHint(provider, overrides)

  let status = 'failed'
  if (exitCode === 0) {
    status = 'passed'
  } else if (summaryStatus === 'preflight_failed') {
    status = 'blocked'
  }

  process.stdout.write(`[matrix] ${provider}: ${status}\n`)

  return {
    provider,
    status,
    readiness: status === 'blocked' ? 'blocked' : 'ready',
    reason: status === 'passed' ? '' : summaryReason,
    exitCode,
    command,
    hint: status === 'passed' ? '' : hint,
    evidence: path.relative(REPO_ROOT, summaryPath),
    log: path.relative(REPO_ROOT, logPath),
    summaryExcerpt: summarizeText(summaryRaw),
  }
}

async function buildBlockedProviderRow(readinessRow, generatedAt) {
  const logPath = getProviderMatrixLogPath(EVIDENCE_DIR, readinessRow.provider, readinessRow.evidenceSuffix)
  const overrides = readinessRow.overrides || {}
  const command = readinessRow.command || getProviderSmokeCommand(readinessRow.provider, overrides)
  const smokeStatus = readinessRow.remote_check === 'failed' ? 'readiness_failed' : 'preflight_failed'

  await resetProviderSmokeEvidenceFiles(EVIDENCE_DIR, readinessRow.provider)
  await writeProviderSmokeEvidence(EVIDENCE_DIR, readinessRow.provider, {
    status: smokeStatus,
    generatedAt,
    overrides,
    error: readinessRow.reason,
    hint: readinessRow.hint,
  })
  await writeFile(
    logPath,
    [
      `[matrix] ${readinessRow.provider}: blocked`,
      readinessRow.reason ? `reason=${readinessRow.reason}` : '',
      readinessRow.hint ? `hint=${readinessRow.hint}` : '',
      `command=${command}`,
      'skipped_provider_smoke=true',
      '',
    ]
      .filter(Boolean)
      .join('\n'),
    'utf8'
  )

  const summaryPath = getProviderSummaryPath(readinessRow.provider)
  const summaryRaw = readOptionalFile(summaryPath)
  process.stdout.write(`[matrix] ${readinessRow.provider}: blocked\n`)

  return {
    provider: readinessRow.provider,
    status: 'blocked',
    readiness: 'blocked',
    reason: readinessRow.reason || '',
    exitCode: 1,
    command,
    hint: readinessRow.hint || buildProviderSmokeHint(readinessRow.provider, overrides),
    evidence: path.relative(REPO_ROOT, summaryPath),
    log: path.relative(REPO_ROOT, logPath),
    summaryExcerpt: summarizeText(summaryRaw),
  }
}

async function main() {
  const generatedAt = new Date().toISOString()
  const { providerOverrides, providers, evidenceSuffix } = parseProviderScopeArgs(process.argv.slice(2))
  const qaEnv = buildQaRuntimeEnv(process.env)
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const readinessProbe = await loadProviderProbe()
  const preflightRows = buildProviderReadinessRows(readinessProbe, providerOverrides, qaEnv, {}, providers)
  const remoteProviders = preflightRows.filter((row) => row.ready).map((row) => row.provider)
  const connectionProbe = await loadProviderConnectionProbe(providerOverrides, qaEnv, remoteProviders)
  const readinessRows = buildProviderReadinessRows(readinessProbe, providerOverrides, qaEnv, connectionProbe, providers).map((row) => ({
    ...row,
    overrides: providerOverrides[row.provider] || {},
    evidenceSuffix,
  }))
  await writeProviderReadinessEvidence(EVIDENCE_DIR, readinessRows, {
    generatedAt,
    source: 'qa:real-stack-smoke:matrix',
    providerScope: providers.join(','),
    evidenceSuffix,
  })

  const readinessByProvider = new Map(readinessRows.map((row) => [row.provider, row]))
  const rows = []

  for (const provider of providers) {
    const readinessRow = readinessByProvider.get(provider)
    if (readinessRow?.ready === false) {
      rows.push(await buildBlockedProviderRow(readinessRow, generatedAt))
      continue
    }
    rows.push(await runProvider(provider, providerOverrides[provider] || {}, qaEnv, evidenceSuffix))
  }

  const matrixEvidencePaths = getProviderMatrixEvidencePaths(EVIDENCE_DIR, evidenceSuffix)
  const readinessEvidencePaths = getProviderReadinessEvidencePaths(EVIDENCE_DIR, evidenceSuffix)
  const summary = buildProviderMatrixSummary(rows, {
    generatedAt,
    source: 'qa:real-stack-smoke:matrix',
    readinessEvidence: path.relative(REPO_ROOT, readinessEvidencePaths.json),
    providerScope: providers.join(','),
  })
  await writeFile(matrixEvidencePaths.summary, summary, 'utf8')
  await writeFile(
    matrixEvidencePaths.json,
    `${JSON.stringify({
      generated_at: generatedAt,
      readiness_evidence: path.relative(REPO_ROOT, readinessEvidencePaths.json),
      provider_scope: providers.join(','),
      evidence_suffix: evidenceSuffix,
      providers: rows,
      counts: {
        passed: rows.filter((row) => row.status === 'passed').length,
        blocked: rows.filter((row) => row.status === 'blocked').length,
        failed: rows.filter((row) => row.status === 'failed').length,
      }
    }, null, 2)}\n`,
    'utf8'
  )
  process.stdout.write(summary)

  const hasHardFailure = rows.some((row) => row.status === 'failed')
  process.exitCode = hasHardFailure ? 1 : 0
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exit(1)
})
