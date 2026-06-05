import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  buildProviderSmokeFailureHint,
  buildQaRuntimeEnv,
  buildProviderSmokeHint,
  buildProviderSmokeEnv,
  getProviderPreflightError,
  parseProviderSmokeArgs,
  resetProviderSmokeEvidenceFiles,
  writeProviderSmokeEvidence,
} from './t15-provider-real-stack-smoke-helpers.mjs'
import { loadProviderProbe } from './t15-provider-probe.mjs'

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url))
const TARGET_SCRIPT = path.resolve(SCRIPT_DIR, 't14-real-stack-smoke.mjs')
const REPO_ROOT = path.resolve(process.cwd(), '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function runProviderPreflight(provider, overrides = {}, qaEnv = process.env) {
  const probe = await loadProviderProbe(overrides)
  const error = getProviderPreflightError(provider, probe, overrides, qaEnv)
  if (error) {
    throw new Error(error)
  }
}

function summarizeChildFile(raw, maxLines = 4) {
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

function extractSummaryHint(provider) {
  const raw = readOptionalFile(path.join(EVIDENCE_DIR, `task-15-provider-smoke-${provider}-summary.txt`))
  const match = raw.match(/^hint=(.*)$/m)
  return match ? match[1] : ''
}

async function main() {
  const { provider, overrides } = parseProviderSmokeArgs(process.argv.slice(2))
  const generatedAt = new Date().toISOString()
  const qaEnv = buildQaRuntimeEnv(process.env)
  await resetProviderSmokeEvidenceFiles(EVIDENCE_DIR, provider)

  try {
    await runProviderPreflight(provider, overrides, qaEnv)
  } catch (error) {
    const hint = buildProviderSmokeHint(provider, overrides)
    await writeProviderSmokeEvidence(EVIDENCE_DIR, provider, {
      status: 'preflight_failed',
      generatedAt,
      overrides,
      error: error.stack || error.message || String(error),
      hint,
    })
    throw error
  }

  const env = buildProviderSmokeEnv(provider, qaEnv, overrides)
  let childExitCode = ''
  const childSummaryPath = path.join(EVIDENCE_DIR, 'task-14-real-smoke-summary.txt')
  const childErrorPath = path.join(EVIDENCE_DIR, 'task-14-real-smoke-error.txt')

  try {
    await new Promise((resolve, reject) => {
      const child = spawn(process.execPath, [TARGET_SCRIPT], {
        cwd: process.cwd(),
        env,
        stdio: 'inherit',
        shell: false
      })

      child.on('exit', (code) => {
        childExitCode = code ?? ''
        if (code === 0) {
          resolve()
          return
        }
        reject(new Error(`Provider smoke failed for ${provider} with exit code ${code}`))
      })

      child.on('error', reject)
    })

    await writeProviderSmokeEvidence(EVIDENCE_DIR, provider, {
      status: 'passed',
      generatedAt,
      overrides,
      childExitCode,
      childSummaryExcerpt: summarizeChildFile(readOptionalFile(childSummaryPath)),
    })
  } catch (error) {
    const childSummaryExcerpt = summarizeChildFile(readOptionalFile(childSummaryPath))
    const childErrorExcerpt = summarizeChildFile(readOptionalFile(childErrorPath))
    const hint = buildProviderSmokeFailureHint(
      provider,
      overrides,
      [childErrorExcerpt, error.stack || error.message || String(error)].filter(Boolean).join('\n')
    )
    await writeProviderSmokeEvidence(EVIDENCE_DIR, provider, {
      status: 'failed',
      generatedAt,
      overrides,
      childExitCode,
      childSummaryExcerpt,
      childErrorExcerpt,
      error: error.stack || error.message || String(error),
      hint,
    })
    throw error
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  try {
    const { provider, overrides } = parseProviderSmokeArgs(process.argv.slice(2))
    process.stderr.write(`${extractSummaryHint(provider) || buildProviderSmokeHint(provider, overrides)}\n`)
  } catch {
    // no-op
  }
  process.exit(1)
})
