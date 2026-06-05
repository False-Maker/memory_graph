import { spawn } from 'node:child_process'
import path from 'node:path'

import {
  evaluateRemoteDoctorEvidence,
  loadRemoteDoctorEvidence,
  parseRemoteDoctorArgs,
} from './t17-provider-remote-doctor-helpers.mjs'
import { getProviderReadinessEvidencePaths } from './t15-provider-real-stack-smoke-helpers.mjs'

const FRONTEND_ROOT = process.cwd()
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function runRefreshStep(scriptPath, scopeArgs) {
  await new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [scriptPath, ...scopeArgs], {
      cwd: FRONTEND_ROOT,
      env: process.env,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
    })

    child.stdout.resume()
    child.stderr.resume()
    child.on('exit', () => resolve())
    child.on('error', reject)
  })
}

async function main() {
  const { refresh, providers, evidenceSuffix, scopeArgs } = parseRemoteDoctorArgs(process.argv.slice(2))
  if (refresh) {
    await runRefreshStep('src-react/qa/t15-provider-readiness.mjs', scopeArgs)
    await runRefreshStep('src-react/qa/t16-provider-matrix-smoke.mjs', scopeArgs)
  }

  const evidence = loadRemoteDoctorEvidence(EVIDENCE_DIR, evidenceSuffix)
  const expectedReadinessEvidenceRef = path.relative(
    REPO_ROOT,
    getProviderReadinessEvidencePaths(EVIDENCE_DIR, evidenceSuffix).json
  )
  const report = evaluateRemoteDoctorEvidence({
    readiness: evidence.readiness,
    matrix: evidence.matrix,
    providers,
    evidenceSuffix,
    expectedReadinessEvidenceRef,
    loadIssues: evidence.issues,
  })

  process.stdout.write(`${report.line}\n`)
  process.exitCode = report.exitCode
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exit(1)
})
