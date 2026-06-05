import path from 'node:path'
import { writeFile } from 'node:fs/promises'

import { applyBrowserLibEnv, buildBrowserLibDir } from './settings-playwright-runtime.mjs'

function normalizeOptionalValue(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : ''
}

export function buildPlaywrightBrowserEnv(frontendRoot, env = process.env) {
  return applyBrowserLibEnv(buildBrowserLibDir(frontendRoot), env)
}

export async function launchPlaywrightBrowser(browserType, frontendRoot, options = {}) {
  const { env = process.env, ...launchOptions } = options
  return await browserType.launch({
    ...launchOptions,
    env: buildPlaywrightBrowserEnv(frontendRoot, env),
  })
}

export function collectPlaywrightArtifacts(results = [], extraArtifacts = []) {
  const normalizedResults = Array.isArray(results) ? results : []
  const collected = normalizedResults.flatMap((item) => {
    if (Array.isArray(item?.artifacts)) {
      return item.artifacts
    }
    return normalizeOptionalValue(item?.artifact) ? [item.artifact] : []
  })

  return [...collected, ...extraArtifacts]
    .map((item) => normalizeOptionalValue(item))
    .filter(Boolean)
}

export function buildPlaywrightSmokeSummaryText({
  generatedAt,
  status = 'passed',
  baseUrl = '',
  results = [],
  extraArtifacts = [],
  extraSummaryFields = {},
}) {
  const lines = []

  if (normalizeOptionalValue(generatedAt)) {
    lines.push(`generated_at=${normalizeOptionalValue(generatedAt)}`)
  }
  lines.push(`status=${normalizeOptionalValue(status) || 'passed'}`)

  if (normalizeOptionalValue(baseUrl)) {
    lines.push(`base_url=${normalizeOptionalValue(baseUrl)}`)
  }

  for (const [key, value] of Object.entries(extraSummaryFields || {})) {
    lines.push(`${key}=${normalizeOptionalValue(value)}`)
  }

  const normalizedResults = Array.isArray(results) ? results : []
  lines.push(`scenario_count=${normalizedResults.length}`)
  lines.push(`scenarios=${normalizedResults.map((item) => normalizeOptionalValue(item?.scenario)).filter(Boolean).join(',')}`)
  lines.push(`artifacts=${collectPlaywrightArtifacts(normalizedResults, extraArtifacts).join(',')}`)

  return `${lines.join('\n')}\n`
}

export async function writePlaywrightSmokeEvidence({
  evidenceDir,
  summaryFileName,
  jsonFileName,
  generatedAt,
  status = 'passed',
  baseUrl = '',
  results = [],
  extraArtifacts = [],
  extraSummaryFields = {},
  extraJsonFields = {},
}) {
  const summaryText = buildPlaywrightSmokeSummaryText({
    generatedAt,
    status,
    baseUrl,
    results,
    extraArtifacts,
    extraSummaryFields,
  })
  const payload = {
    generated_at: normalizeOptionalValue(generatedAt),
    status: normalizeOptionalValue(status) || 'passed',
    base_url: normalizeOptionalValue(baseUrl),
    scenarios: Array.isArray(results) ? results : [],
    artifacts: collectPlaywrightArtifacts(results, extraArtifacts),
    ...extraJsonFields,
  }

  await writeFile(path.join(evidenceDir, summaryFileName), summaryText, 'utf8')
  await writeFile(path.join(evidenceDir, jsonFileName), `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
}
