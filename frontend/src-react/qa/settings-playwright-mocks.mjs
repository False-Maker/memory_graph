const DEFAULT_SETTINGS_CONFIG = Object.freeze({
  llm_provider: 'openai',
  embedding_model: 'text-embedding-3-large',
  graph_backend: 'NetworkX + SQLite',
  vector_store_type: 'faiss',
  app_host: 'localhost',
  app_port: 8000,
  openai_base_url: 'https://api.openai.com/v1',
  openai_model: 'gpt-4o',
  openai_api_key_configured: true,
  anthropic_base_url: 'https://api.anthropic.com',
  anthropic_model: 'claude-sonnet-4-20250514',
  anthropic_api_key_configured: false,
  ollama_url: 'http://localhost:11434',
  ollama_model: 'qwen2.5:14b',
  secret_storage: {
    available: true,
    storage_type: 'system_keyring',
    backend: 'keyring.backends.SecretService.Keyring',
    message: 'API keys will be stored in the system keyring and kept out of config/settings.yaml.',
    fallback_env_vars: ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY'],
  },
})

function resolvePayload(payloadOrBuilder) {
  return typeof payloadOrBuilder === 'function' ? payloadOrBuilder() : payloadOrBuilder
}

export function buildSettingsConfigPayload(overrides = {}) {
  return {
    ...DEFAULT_SETTINGS_CONFIG,
    ...overrides,
  }
}

export function buildSettingsConfigUpdateSuccessPayload() {
  return {
    success: true,
    message: 'Configuration saved to settings.yaml',
  }
}

export function buildHealthyRuntimeDiagnosticsPayload({
  generatedAt = '2026-04-03T13:00:00Z',
  currentProvider = 'openai',
  providers = { openai: true },
  indexedDocuments = 5,
  storedDocuments = indexedDocuments,
} = {}) {
  return {
    status: 'healthy',
    generated_at: generatedAt,
    checks: {
      config: { ok: true },
      provider: {
        ok: true,
        current_provider: currentProvider,
        providers,
        provider_errors: {},
        current_error: null,
      },
      sqlite: { ok: true },
      vector_store: {
        ok: true,
        state: {
          indexed_documents: indexedDocuments,
          stored_documents: storedDocuments,
          dimension_mismatch: false,
        },
      },
    },
    task_chain: {
      status: 'not_configured',
      configured_sources: 0,
      sources: [],
      detail: null,
    },
    recent_failures: [],
  }
}

export async function registerSettingsConfigRoute(
  page,
  {
    getPayload = buildSettingsConfigPayload(),
    onPut = null,
    putPayload = buildSettingsConfigUpdateSuccessPayload(),
  } = {}
) {
  await page.route('**/api/v1/config', async (route) => {
    const request = route.request()
    if (request.method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(resolvePayload(getPayload)),
      })
      return
    }

    if (request.method() === 'PUT' && typeof onPut === 'function') {
      const payload = request.postDataJSON()
      await onPut(payload, { route, request })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(resolvePayload(putPayload)),
      })
      return
    }

    await route.fallback()
  })
}

export async function registerHealthyRuntimeDiagnosticsRoute(
  page,
  options = {}
) {
  await page.route('**/api/v1/diagnostics/runtime', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildHealthyRuntimeDiagnosticsPayload(options)),
    })
  })
}
