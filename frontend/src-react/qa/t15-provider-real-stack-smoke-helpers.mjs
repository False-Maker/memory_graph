import fs from 'node:fs'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'

import { SUPPORTED_PROVIDERS } from './t14-real-stack-smoke-helpers.mjs'

export const PROVIDER_SMOKE_PROVIDERS = ['openai', 'anthropic', 'ollama']
const PROVIDER_PROFILE_OVERRIDES = {
  openai: {
    bigmodel: {
      baseUrl: 'https://open.bigmodel.cn/api/coding/paas/v4',
      model: 'glm-4.7',
      apiKeyEnv: 'OPENAI_API_KEY,BIGMODEL_API_KEY',
    },
  },
  anthropic: {
    bigmodel: {
      baseUrl: 'https://open.bigmodel.cn/api/anthropic',
      model: 'GLM-4.7',
      apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
    },
  },
}

export function normalizeProviderArg(value) {
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : ''
  if (!SUPPORTED_PROVIDERS.has(normalized)) {
    throw new Error(`Provider must be one of ${Array.from(SUPPORTED_PROVIDERS).join(', ')}`)
  }
  return normalized
}

function normalizeOptionalCliValue(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

function normalizeEvidenceSuffix(value) {
  const normalized = normalizeOptionalCliValue(value)
  if (!normalized) {
    return ''
  }

  return normalized
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

function buildEvidenceFileName(baseName, evidenceSuffix, extension) {
  const normalizedSuffix = normalizeEvidenceSuffix(evidenceSuffix)
  return normalizedSuffix
    ? `${baseName}-${normalizedSuffix}.${extension}`
    : `${baseName}.${extension}`
}

function readDotenvPairs(dotenvPath) {
  if (!fs.existsSync(dotenvPath)) {
    return {}
  }

  const pairs = {}
  for (const rawLine of fs.readFileSync(dotenvPath, 'utf8').split('\n')) {
    let line = rawLine.trim()
    if (!line || line.startsWith('#')) {
      continue
    }

    if (line.startsWith('export ')) {
      line = line.slice('export '.length).trim()
    }

    const equalsIndex = line.indexOf('=')
    if (equalsIndex === -1) {
      continue
    }

    const key = line.slice(0, equalsIndex).trim()
    if (!key) {
      continue
    }

    let value = line.slice(equalsIndex + 1).trim()
    if (value.length >= 2 && value[0] === value[value.length - 1] && [`'`, '"'].includes(value[0])) {
      value = value.slice(1, -1)
    }

    pairs[key] = value
  }

  return pairs
}

function splitCandidateEnvNames(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildApiKeyHintText(apiKeyEnv) {
  const envNames = splitCandidateEnvNames(apiKeyEnv)
  if (envNames.length === 0) {
    return ''
  }
  if (envNames.length === 1) {
    return `export ${envNames[0]}=<token>`
  }
  return `set one of ${envNames.join(' or ')} in the current shell or .env`
}

function buildApiKeySourceHint(apiKeyEnv) {
  const envNames = splitCandidateEnvNames(apiKeyEnv)
  if (envNames.length === 0) {
    return 'the configured token'
  }
  if (envNames.length === 1) {
    return envNames[0]
  }
  return `one of ${envNames.join(' or ')}`
}

export function buildQaRuntimeEnv(baseEnv = process.env, cwd = process.cwd()) {
  const mergedEnv = { ...baseEnv }
  const candidateDotenvPaths = [
    path.resolve(cwd, '.env'),
    path.resolve(cwd, '..', '.env'),
  ]

  for (const dotenvPath of candidateDotenvPaths) {
    const pairs = readDotenvPairs(dotenvPath)
    for (const [key, value] of Object.entries(pairs)) {
      if (!(key in mergedEnv)) {
        mergedEnv[key] = value
      }
    }
  }

  return mergedEnv
}

export function buildProviderSmokeArgv(provider, overrides = {}) {
  const normalizedProvider = normalizeProviderArg(provider)
  const args = []

  if (normalizedProvider === 'openai') {
    if (normalizeOptionalCliValue(overrides.baseUrl)) {
      args.push('--base-url', normalizeOptionalCliValue(overrides.baseUrl))
    }
    if (normalizeOptionalCliValue(overrides.model)) {
      args.push('--model', normalizeOptionalCliValue(overrides.model))
    }
    if (normalizeOptionalCliValue(overrides.apiKeyEnv)) {
      args.push('--api-key-env', normalizeOptionalCliValue(overrides.apiKeyEnv))
    }
    return args
  }

  if (normalizedProvider === 'anthropic') {
    if (normalizeOptionalCliValue(overrides.baseUrl)) {
      args.push('--base-url', normalizeOptionalCliValue(overrides.baseUrl))
    }
    if (normalizeOptionalCliValue(overrides.model)) {
      args.push('--model', normalizeOptionalCliValue(overrides.model))
    }
    if (normalizeOptionalCliValue(overrides.apiKeyEnv)) {
      args.push('--api-key-env', normalizeOptionalCliValue(overrides.apiKeyEnv))
    }
    return args
  }

  if (normalizeOptionalCliValue(overrides.url)) {
    args.push('--url', normalizeOptionalCliValue(overrides.url))
  }
  if (normalizeOptionalCliValue(overrides.model)) {
    args.push('--model', normalizeOptionalCliValue(overrides.model))
  }

  return args
}

export function getProviderSmokeCommand(provider, overrides = {}) {
  const baseCommand = `npm --prefix frontend run qa:real-stack-smoke:${normalizeProviderArg(provider)}`
  const providerArgs = buildProviderSmokeArgv(provider, overrides)
  if (providerArgs.length === 0) {
    return baseCommand
  }
  return `${baseCommand} -- ${providerArgs.join(' ')}`
}

export function resolveProviderProfileOverrides(provider, profile) {
  const normalizedProvider = normalizeProviderArg(provider)
  const normalizedProfile = normalizeOptionalCliValue(profile)
  if (!normalizedProfile) {
    return {}
  }

  const profileOverrides = PROVIDER_PROFILE_OVERRIDES[normalizedProvider]?.[normalizedProfile]
  if (!profileOverrides) {
    throw new Error(`Unsupported ${normalizedProvider} QA profile: ${normalizedProfile}`)
  }

  return { ...profileOverrides }
}

export function parseProviderList(value) {
  const normalized = normalizeOptionalCliValue(value)
  if (!normalized) {
    return [...PROVIDER_SMOKE_PROVIDERS]
  }

  return Array.from(new Set(
    normalized
      .split(',')
      .map((item) => normalizeProviderArg(item))
  ))
}

export function parseProviderScopeArgs(argv = []) {
  const providerOverrides = {}
  let providers = [...PROVIDER_SMOKE_PROVIDERS]
  let evidenceSuffix = ''

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]

    if (arg === '--openai-profile') {
      providerOverrides.openai = resolveProviderProfileOverrides('openai', argv[index + 1])
      index += 1
      continue
    }

    if (arg === '--anthropic-profile') {
      providerOverrides.anthropic = resolveProviderProfileOverrides('anthropic', argv[index + 1])
      index += 1
      continue
    }

    if (arg === '--providers') {
      providers = parseProviderList(argv[index + 1])
      index += 1
      continue
    }

    if (arg === '--evidence-suffix') {
      evidenceSuffix = normalizeEvidenceSuffix(argv[index + 1])
      index += 1
      continue
    }

    throw new Error(`Unknown provider scope argument: ${arg}`)
  }

  return {
    providerOverrides,
    providers,
    evidenceSuffix,
  }
}

export function parseProviderProfileArgs(argv = []) {
  return parseProviderScopeArgs(argv).providerOverrides
}

export function getProviderSmokeEvidencePaths(evidenceDir, provider) {
  const normalizedProvider = normalizeProviderArg(provider)
  return {
    summary: path.join(evidenceDir, `task-15-provider-smoke-${normalizedProvider}-summary.txt`),
    error: path.join(evidenceDir, `task-15-provider-smoke-${normalizedProvider}-error.txt`),
  }
}

export function getProviderReadinessEvidencePaths(evidenceDir, evidenceSuffix = '') {
  return {
    summary: path.join(evidenceDir, buildEvidenceFileName('task-15-provider-readiness', evidenceSuffix, 'txt')),
    json: path.join(evidenceDir, buildEvidenceFileName('task-15-provider-readiness', evidenceSuffix, 'json')),
  }
}

export function getProviderMatrixEvidencePaths(evidenceDir, evidenceSuffix = '') {
  return {
    summary: path.join(evidenceDir, buildEvidenceFileName('task-16-provider-matrix-summary', evidenceSuffix, 'txt')),
    json: path.join(evidenceDir, buildEvidenceFileName('task-16-provider-matrix-summary', evidenceSuffix, 'json')),
  }
}

export function getProviderMatrixLogPath(evidenceDir, provider, evidenceSuffix = '') {
  const normalizedProvider = normalizeProviderArg(provider)
  const normalizedSuffix = normalizeEvidenceSuffix(evidenceSuffix)
  const baseName = normalizedSuffix
    ? `task-16-provider-matrix-${normalizedSuffix}-${normalizedProvider}`
    : `task-16-provider-matrix-${normalizedProvider}`
  return path.join(evidenceDir, `${baseName}.log`)
}

export async function resetProviderSmokeEvidenceFiles(evidenceDir, provider) {
  await mkdir(evidenceDir, { recursive: true })
  const paths = getProviderSmokeEvidencePaths(evidenceDir, provider)
  await Promise.all([
    rm(paths.summary, { force: true }),
    rm(paths.error, { force: true }),
  ])
  return paths
}

export async function writeProviderSmokeEvidence(evidenceDir, provider, payload) {
  const paths = getProviderSmokeEvidencePaths(evidenceDir, provider)
  const summary = buildProviderSmokeSummary({ provider, ...payload })
  await writeFile(paths.summary, summary, 'utf8')

  const errorText = payload.error ? `${payload.error}\n` : ''
  if (errorText) {
    await writeFile(paths.error, errorText, 'utf8')
  } else if (fs.existsSync(paths.error)) {
    await rm(paths.error, { force: true })
  }

  return paths
}

export function resolveApiKeyEnvValue(overrides = {}, env = process.env) {
  const mergedEnv = buildQaRuntimeEnv(env)
  const envNames = splitCandidateEnvNames(normalizeOptionalCliValue(overrides.apiKeyEnv))
  if (envNames.length === 0) {
    return null
  }

  for (const envName of envNames) {
    const candidate = normalizeOptionalCliValue(mergedEnv?.[envName])
    if (candidate) {
      return candidate
    }
  }

  return null
}

export function parseProviderSmokeArgs(argv = []) {
  let provider = null
  const overrides = {}

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index]

    if (arg === '--provider') {
      provider = argv[index + 1]
      index += 1
      continue
    }

    if (arg === '--model') {
      overrides.model = argv[index + 1]
      index += 1
      continue
    }

    if (arg === '--url') {
      overrides.url = argv[index + 1]
      index += 1
      continue
    }

    if (arg === '--base-url') {
      overrides.baseUrl = argv[index + 1]
      index += 1
      continue
    }

    if (arg === '--api-key-env') {
      overrides.apiKeyEnv = argv[index + 1]
      index += 1
      continue
    }

    if (!arg.startsWith('--') && provider === null) {
      provider = arg
      continue
    }

    throw new Error(`Unknown provider smoke argument: ${arg}`)
  }

  return {
    provider: normalizeProviderArg(provider),
    overrides: {
      model: normalizeOptionalCliValue(overrides.model),
      url: normalizeOptionalCliValue(overrides.url),
      baseUrl: normalizeOptionalCliValue(overrides.baseUrl),
      apiKeyEnv: normalizeOptionalCliValue(overrides.apiKeyEnv),
    }
  }
}

export function buildProviderSmokeEnv(provider, baseEnv = {}, overrides = {}) {
  const normalizedProvider = normalizeProviderArg(provider)
  const apiKeyOverride = resolveApiKeyEnvValue(overrides, baseEnv)
  const env = {
    ...baseEnv,
    T14_EXPECT_PROVIDER: normalizedProvider,
    T14_OVERRIDE_PROVIDER: normalizedProvider,
    T14_REQUIRE_CURRENT_PROVIDER_SUCCESS: 'true',
  }

  if (normalizedProvider === 'openai') {
    if (apiKeyOverride) {
      env.T14_OVERRIDE_OPENAI_API_KEY = apiKeyOverride
    }
    if (normalizeOptionalCliValue(overrides.baseUrl)) {
      env.T14_OVERRIDE_OPENAI_BASE_URL = normalizeOptionalCliValue(overrides.baseUrl)
    }
    if (normalizeOptionalCliValue(overrides.model)) {
      env.T14_OVERRIDE_OPENAI_MODEL = normalizeOptionalCliValue(overrides.model)
    }
  } else if (normalizedProvider === 'anthropic') {
    if (apiKeyOverride) {
      env.T14_OVERRIDE_ANTHROPIC_API_KEY = apiKeyOverride
    }
    if (normalizeOptionalCliValue(overrides.baseUrl)) {
      env.T14_OVERRIDE_ANTHROPIC_BASE_URL = normalizeOptionalCliValue(overrides.baseUrl)
    }
    if (normalizeOptionalCliValue(overrides.model)) {
      env.T14_OVERRIDE_ANTHROPIC_MODEL = normalizeOptionalCliValue(overrides.model)
    }
  } else if (normalizedProvider === 'ollama') {
    if (normalizeOptionalCliValue(overrides.url)) {
      env.T14_OVERRIDE_OLLAMA_URL = normalizeOptionalCliValue(overrides.url)
    }
    if (normalizeOptionalCliValue(overrides.model)) {
      env.T14_OVERRIDE_OLLAMA_MODEL = normalizeOptionalCliValue(overrides.model)
    }
  }

  return env
}

export function getProviderPreflightError(provider, probe = {}, overrides = {}, env = process.env) {
  const normalizedProvider = normalizeProviderArg(provider)
  const apiKeyOverride = resolveApiKeyEnvValue(overrides, env)

  if (normalizedProvider === 'anthropic' && !apiKeyOverride && !probe?.anthropic?.apiKeyConfigured) {
    return 'Anthropic API key is not configured'
  }

  if (normalizedProvider === 'openai' && !apiKeyOverride && !probe?.openai?.apiKeyConfigured) {
    return 'OpenAI API key is not configured'
  }

  if (normalizedProvider === 'ollama' && probe?.ollama?.reachable === false) {
    return `Ollama endpoint is not reachable at ${normalizeOptionalCliValue(overrides.url) || probe?.ollama?.url || 'http://localhost:11434'}`
  }

  return null
}

export function buildProviderSmokeSummary({
  provider,
  status,
  generatedAt = '',
  hint = '',
  error = '',
  overrides = {},
  childExitCode = '',
  childSummaryExcerpt = '',
  childErrorExcerpt = '',
}) {
  const lines = [
    `provider=${normalizeProviderArg(provider)}`,
    `status=${status}`,
    `generated_at=${normalizeOptionalCliValue(generatedAt) || ''}`,
    `override_api_key_env=${normalizeOptionalCliValue(overrides.apiKeyEnv) || ''}`,
    `override_model=${normalizeOptionalCliValue(overrides.model) || ''}`,
    `override_url=${normalizeOptionalCliValue(overrides.url) || ''}`,
    `override_base_url=${normalizeOptionalCliValue(overrides.baseUrl) || ''}`,
    `child_exit_code=${childExitCode}`,
    `child_summary_excerpt=${childSummaryExcerpt}`,
    `child_error_excerpt=${childErrorExcerpt}`,
    `error=${error}`,
    `hint=${hint}`,
  ]

  return `${lines.join('\n')}\n`
}

export function buildProviderReadinessRows(
  probe = {},
  providerOverrides = {},
  env = process.env,
  connectionProbe = {},
  providers = PROVIDER_SMOKE_PROVIDERS
) {
  return providers.map((provider) => {
    const overrides = providerOverrides[provider] || {}
    const providerConnectionProbe = connectionProbe[provider] || {}
    const preflightError = getProviderPreflightError(provider, probe, overrides, env)
    const remoteError = normalizeOptionalCliValue(providerConnectionProbe.error) || ''
    const remoteFailure = preflightError ? '' : (providerConnectionProbe.checked && providerConnectionProbe.ok === false ? remoteError || `${provider} remote connection probe failed` : '')
    const error = preflightError || remoteFailure
    return {
      provider,
      ready: !error,
      reason: error || '',
      hint: error
        ? (preflightError
          ? buildProviderSmokeHint(provider, overrides)
          : buildProviderSmokeFailureHint(provider, overrides, remoteFailure))
        : '',
      command: getProviderSmokeCommand(provider, overrides),
      overrides,
      remote_check: preflightError
        ? 'skipped'
        : (providerConnectionProbe.checked ? (providerConnectionProbe.ok ? 'passed' : 'failed') : 'skipped'),
      remote_error: preflightError ? '' : remoteError,
    }
  })
}

export function buildProviderReadinessSummary(rows, meta = {}) {
  const lines = []

  if (normalizeOptionalCliValue(meta.generatedAt)) {
    lines.push(`generated_at=${normalizeOptionalCliValue(meta.generatedAt)}`)
  }
  if (normalizeOptionalCliValue(meta.source)) {
    lines.push(`source=${normalizeOptionalCliValue(meta.source)}`)
  }
  if (normalizeOptionalCliValue(meta.providerScope)) {
    lines.push(`provider_scope=${normalizeOptionalCliValue(meta.providerScope)}`)
  }
  if (lines.length > 0) {
    lines.push('')
  }

  for (const row of rows) {
    lines.push(`provider=${row.provider}`)
    lines.push(`ready=${row.ready ? 'true' : 'false'}`)
    lines.push(`remote_check=${row.remote_check || 'skipped'}`)
    lines.push(`remote_error=${row.remote_error || ''}`)
    lines.push(`reason=${row.reason}`)
    lines.push(`hint=${row.hint}`)
    lines.push(`command=${row.command}`)
    lines.push('')
  }

  lines.push(`ready_count=${rows.filter((row) => row.ready).length}`)
  lines.push(`blocked_count=${rows.filter((row) => !row.ready).length}`)

  return `${lines.join('\n')}\n`
}

export async function writeProviderReadinessEvidence(evidenceDir, rows, meta = {}) {
  await mkdir(evidenceDir, { recursive: true })
  const paths = getProviderReadinessEvidencePaths(evidenceDir, meta.evidenceSuffix)
  const payload = {
    generated_at: normalizeOptionalCliValue(meta.generatedAt) || '',
    source: normalizeOptionalCliValue(meta.source) || '',
    provider_scope: normalizeOptionalCliValue(meta.providerScope) || '',
    evidence_suffix: normalizeEvidenceSuffix(meta.evidenceSuffix),
    providers: rows,
    counts: {
      ready: rows.filter((row) => row.ready).length,
      blocked: rows.filter((row) => !row.ready).length,
    },
  }

  await writeFile(
    paths.summary,
    buildProviderReadinessSummary(rows, meta),
    'utf8'
  )
  await writeFile(
    paths.json,
    `${JSON.stringify(payload, null, 2)}\n`,
    'utf8'
  )

  return payload
}

export function buildProviderSmokeHint(provider, overrides = {}) {
  const normalizedProvider = normalizeProviderArg(provider)
  const apiKeyEnv = normalizeOptionalCliValue(overrides.apiKeyEnv)
  const apiKeyHint = buildApiKeyHintText(apiKeyEnv)

  if (normalizedProvider === 'anthropic') {
    return apiKeyEnv
      ? `Hint: ${apiKeyHint} before rerunning \`qa:real-stack-smoke:anthropic\`.`
      : 'Hint: configure a valid Anthropic API key before rerunning `qa:real-stack-smoke:anthropic`.'
  }

  if (normalizedProvider === 'ollama') {
    return `Hint: ensure Ollama is running at ${normalizeOptionalCliValue(overrides.url) || 'http://localhost:11434'} and the target model is available before rerunning \`qa:real-stack-smoke:ollama\`.`
  }

  return apiKeyEnv
    ? `Hint: ${apiKeyHint} before rerunning \`qa:real-stack-smoke:openai\`.`
    : 'Hint: ensure the OpenAI-compatible API key, base URL, and model are valid before rerunning `qa:real-stack-smoke:openai`.'
}

export function buildProviderSmokeFailureHint(provider, overrides = {}, failureText = '') {
  const normalizedProvider = normalizeProviderArg(provider)
  const text = String(failureText || '').toLowerCase()
  const apiKeySource = buildApiKeySourceHint(overrides.apiKeyEnv)

  if (
    text.includes('401')
    || text.includes('unauthorized')
    || text.includes('authentication')
    || text.includes('令牌已过期')
    || text.includes('验证不正确')
  ) {
    if (normalizedProvider === 'anthropic') {
      return `Hint: the Anthropic-compatible token from ${apiKeySource} was rejected by the upstream endpoint. Update the token and rerun \`qa:real-stack-smoke:anthropic\`.`
    }

    if (normalizedProvider === 'openai') {
      return `Hint: the OpenAI-compatible token from ${apiKeySource} was rejected by the upstream endpoint. Update the token and rerun \`qa:real-stack-smoke:openai\`.`
    }
  }

  if (text.includes('404') || text.includes('model not found')) {
    if (normalizedProvider === 'anthropic') {
      return 'Hint: the Anthropic-compatible model or base URL was rejected by the upstream endpoint. Check the model and base URL before rerunning `qa:real-stack-smoke:anthropic`.'
    }

    if (normalizedProvider === 'openai') {
      return 'Hint: the OpenAI-compatible model or base URL was rejected by the upstream endpoint. Check the model and base URL before rerunning `qa:real-stack-smoke:openai`.'
    }
  }

  return buildProviderSmokeHint(provider, overrides)
}
