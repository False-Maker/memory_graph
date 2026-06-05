export const SUPPORTED_PROVIDERS = new Set(['openai', 'anthropic', 'ollama'])
export const CONFIG_OVERRIDE_ENV_TO_FIELD = {
  T14_OVERRIDE_OPENAI_API_KEY: 'openai_api_key',
  T14_OVERRIDE_OPENAI_BASE_URL: 'openai_base_url',
  T14_OVERRIDE_OPENAI_MODEL: 'openai_model',
  T14_OVERRIDE_ANTHROPIC_API_KEY: 'anthropic_api_key',
  T14_OVERRIDE_ANTHROPIC_BASE_URL: 'anthropic_base_url',
  T14_OVERRIDE_ANTHROPIC_MODEL: 'anthropic_model',
  T14_OVERRIDE_OLLAMA_URL: 'ollama_url',
  T14_OVERRIDE_OLLAMA_MODEL: 'ollama_model'
}

const DEFAULT_VISIBLE_CONFIG = {
  llm_provider: 'openai',
  openai_base_url: 'https://api.openai.com/v1',
  openai_model: 'gpt-4o',
  anthropic_base_url: 'https://api.anthropic.com',
  anthropic_model: 'claude-sonnet-4-20250514',
  ollama_url: 'http://localhost:11434',
  ollama_model: 'qwen2.5:14b'
}

const PROVIDER_FIELD_EXPECTATIONS = {
  openai: {
    summary: 'openai(base_url,model)',
    selectors: ['#settings-openai-base-url', '#settings-openai-model']
  },
  anthropic: {
    summary: 'anthropic(base_url,model)',
    selectors: ['#settings-anthropic-base-url', '#settings-anthropic-model']
  },
  ollama: {
    summary: 'ollama(url,model)',
    selectors: ['#settings-ollama-url', '#settings-ollama-model']
  }
}

export function parseRequireFlag(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase())
}

export function buildConnectionSummary(connectionJson) {
  if (!connectionJson || typeof connectionJson !== 'object') {
    return 'unknown'
  }

  const providerSummary = Object.entries(connectionJson.providers || {})
    .map(([name, status]) => `${name}=${status}`)
    .join(', ')

  return [
    `success=${connectionJson.success}`,
    providerSummary ? `providers(${providerSummary})` : 'providers(none)',
    `graph_store=${connectionJson.graph_store}`,
    `vector_store=${connectionJson.vector_store}`,
    connectionJson.current_error ? `current_error=${connectionJson.current_error}` : null,
    connectionJson.error ? `error=${connectionJson.error}` : null
  ]
    .filter(Boolean)
    .join(' | ')
}

function normalizeExpectedProvider(value) {
  const normalized = typeof value === 'string' ? value.trim().toLowerCase() : ''
  return normalized || null
}

function normalizeOptionalValue(value) {
  if (typeof value !== 'string') {
    return null
  }

  const normalized = value.trim()
  return normalized || null
}

export function buildConfigPayloadFromSettings(settingsJson) {
  return {
    llm_provider: resolveCurrentProvider(
      { llm_provider: settingsJson?.llm_provider ?? DEFAULT_VISIBLE_CONFIG.llm_provider }
    ),
    openai_base_url: normalizeOptionalValue(settingsJson?.openai_base_url) ?? DEFAULT_VISIBLE_CONFIG.openai_base_url,
    openai_model: normalizeOptionalValue(settingsJson?.openai_model) ?? DEFAULT_VISIBLE_CONFIG.openai_model,
    anthropic_base_url: normalizeOptionalValue(settingsJson?.anthropic_base_url) ?? DEFAULT_VISIBLE_CONFIG.anthropic_base_url,
    anthropic_model: normalizeOptionalValue(settingsJson?.anthropic_model) ?? DEFAULT_VISIBLE_CONFIG.anthropic_model,
    ollama_url: normalizeOptionalValue(settingsJson?.ollama_url) ?? DEFAULT_VISIBLE_CONFIG.ollama_url,
    ollama_model: normalizeOptionalValue(settingsJson?.ollama_model) ?? DEFAULT_VISIBLE_CONFIG.ollama_model
  }
}

export function buildOverrideConfigPayload(basePayload, env = {}) {
  const nextPayload = { ...basePayload }
  const changedFields = []

  const overrideProvider = normalizeExpectedProvider(env.T14_OVERRIDE_PROVIDER)
  if (overrideProvider) {
    if (!SUPPORTED_PROVIDERS.has(overrideProvider)) {
      throw new Error(`T14_OVERRIDE_PROVIDER must be one of ${Array.from(SUPPORTED_PROVIDERS).join(', ')}`)
    }
    if (nextPayload.llm_provider !== overrideProvider) {
      nextPayload.llm_provider = overrideProvider
      changedFields.push('llm_provider')
    }
  }

  for (const [envKey, field] of Object.entries(CONFIG_OVERRIDE_ENV_TO_FIELD)) {
    const overrideValue = normalizeOptionalValue(env[envKey])
    if (overrideValue && nextPayload[field] !== overrideValue) {
      nextPayload[field] = overrideValue
      changedFields.push(field)
    }
  }

  return {
    payload: nextPayload,
    changedFields,
    overrideApplied: changedFields.length > 0
  }
}

export function configPayloadEquals(left, right) {
  return JSON.stringify(left) === JSON.stringify(right)
}

export function resolveCurrentProvider(settingsJson, expectedProvider = null) {
  const provider = settingsJson?.llm_provider
  if (typeof provider !== 'string' || !SUPPORTED_PROVIDERS.has(provider)) {
    throw new Error(`GET /api/v1/config returned unsupported llm_provider=${provider}`)
  }

  const normalizedExpectedProvider = normalizeExpectedProvider(expectedProvider)
  if (!normalizedExpectedProvider) {
    return provider
  }

  if (!SUPPORTED_PROVIDERS.has(normalizedExpectedProvider)) {
    throw new Error(`T14_EXPECT_PROVIDER must be one of ${Array.from(SUPPORTED_PROVIDERS).join(', ')}`)
  }

  if (provider !== normalizedExpectedProvider) {
    throw new Error(`Expected llm_provider=${normalizedExpectedProvider}, got ${provider}`)
  }

  return provider
}

export function getProviderFieldExpectation(provider) {
  const expectation = PROVIDER_FIELD_EXPECTATIONS[provider]
  if (!expectation) {
    throw new Error(`Unsupported provider field expectation for ${provider}`)
  }
  return expectation
}

export function assertCurrentProviderConnection(connectionJson, provider, requireCurrentProviderSuccess = false) {
  const providerStatus = connectionJson?.providers?.current ?? connectionJson?.providers?.[provider]
  const providerError = connectionJson?.current_error
    || connectionJson?.provider_errors?.current
    || connectionJson?.provider_errors?.[provider]

  if (requireCurrentProviderSuccess && providerStatus !== true) {
    throw new Error(
      `Expected current provider ${provider} to connect successfully, got ${providerStatus}`
      + (providerError ? ` (${providerError})` : '')
    )
  }

  return providerStatus
}
