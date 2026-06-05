import path from 'node:path'

import {
  buildQaRuntimeEnv,
  buildProviderReadinessRows,
  buildProviderReadinessSummary,
  parseProviderScopeArgs,
  writeProviderReadinessEvidence,
} from './t15-provider-real-stack-smoke-helpers.mjs'
import { loadProviderConnectionProbe, loadProviderProbe } from './t15-provider-probe.mjs'

const REPO_ROOT = path.resolve(process.cwd(), '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function main() {
  const generatedAt = new Date().toISOString()
  const { providerOverrides, providers, evidenceSuffix } = parseProviderScopeArgs(process.argv.slice(2))
  const qaEnv = buildQaRuntimeEnv(process.env)
  const probe = await loadProviderProbe()
  const preflightRows = buildProviderReadinessRows(probe, providerOverrides, qaEnv, {}, providers)
  const remoteProviders = preflightRows.filter((row) => row.ready).map((row) => row.provider)
  const connectionProbe = await loadProviderConnectionProbe(providerOverrides, qaEnv, remoteProviders)
  const rows = buildProviderReadinessRows(probe, providerOverrides, qaEnv, connectionProbe, providers)
  await writeProviderReadinessEvidence(EVIDENCE_DIR, rows, {
    generatedAt,
    source: 'qa:real-stack-smoke:readiness',
    providerScope: providers.join(','),
    evidenceSuffix,
  })
  process.stdout.write(
    buildProviderReadinessSummary(rows, {
      generatedAt,
      source: 'qa:real-stack-smoke:readiness',
      providerScope: providers.join(','),
    })
  )
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exit(1)
})
