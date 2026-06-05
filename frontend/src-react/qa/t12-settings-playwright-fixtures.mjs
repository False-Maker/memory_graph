import {
  buildSettingsConfigPayload,
  registerHealthyRuntimeDiagnosticsRoute,
  registerSettingsConfigRoute,
} from './settings-playwright-mocks.mjs'

async function registerT12CountedConfigFixture(page, state, {
  getPayload = buildSettingsConfigPayload(),
  validatePut = null,
  includeHealthyDiagnostics = true,
} = {}) {
  if (includeHealthyDiagnostics) {
    await registerHealthyRuntimeDiagnosticsRoute(page)
  }

  await registerSettingsConfigRoute(page, {
    getPayload,
    onPut: async (payload) => {
      state.putCount += 1
      await validatePut?.(payload)
    },
  })
}

export function buildT12SaveHappyPathDiagnosticsPayload() {
  return {
    status: 'unhealthy',
    generated_at: '2026-04-03T12:00:00Z',
    checks: {
      config: { ok: true },
      provider: {
        ok: false,
        current_provider: 'openai',
        providers: { openai: false, anthropic: false, ollama: true },
        provider_errors: { openai: 'mock provider timeout' },
        current_error: 'mock provider timeout'
      },
      sqlite: { ok: true },
      vector_store: {
        ok: true,
        state: { indexed_documents: 12, stored_documents: 14, dimension_mismatch: false }
      }
    },
    task_chain: {
      status: 'degraded',
      configured_sources: 1,
      detail: '1 sync source(s) need attention',
      sources: [
        {
          source_id: 'source-main',
          label: 'workspace-main',
          source_system: 'external',
          workspace_id: 'workspace-main',
          workspace_root: '/workspace/main',
          state_status: 'degraded',
          record_count: 12,
          conflicts: 2,
          deleted_records: 1,
          last_pulled_seq: 41,
          detail: '2 conflicted records require attention'
        }
      ]
    },
    recent_failures: [
      {
        component: 'provider',
        detail: 'mock provider timeout',
        source: 'runtime-diagnostics',
        last_seen_at: '2026-04-03T11:59:00Z',
        count: 3
      }
    ]
  }
}

export async function registerT12SaveHappyPathFixtures(page, state) {
  await page.route('**/api/v1/diagnostics/runtime', async (route) => {
    state.diagnosticsCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildT12SaveHappyPathDiagnosticsPayload()),
    })
  })

  await page.route('**/api/v1/config/test-connection', async (route) => {
    state.testConnectionCount += 1
    const payload = route.request().postDataJSON()
    if (payload.openai_base_url !== 'https://mock-override.example/v1') {
      throw new Error(`Expected unsaved openai_base_url in test payload, got ${payload.openai_base_url}`)
    }
    if (payload.openai_model !== 'glm-4.7-preview') {
      throw new Error(`Expected unsaved openai_model in test payload, got ${payload.openai_model}`)
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        providers: { openai: true, anthropic: false, ollama: true },
        graph_store: true,
        vector_store: true
      })
    })
  })

  await registerT12CountedConfigFixture(page, state, {
    includeHealthyDiagnostics: false,
    validatePut: async (payload) => {
      if (payload.openai_base_url !== 'https://open.bigmodel.cn/api/coding/paas/v4') {
        throw new Error(`Expected openai_base_url to be saved, got ${payload.openai_base_url}`)
      }
      if (payload.openai_model !== 'glm-4.7') {
        throw new Error(`Expected openai_model to be saved, got ${payload.openai_model}`)
      }
    },
  })
}

export async function registerT12ConnectionFailureFixtures(page) {
  await registerHealthyRuntimeDiagnosticsRoute(page)

  await registerSettingsConfigRoute(page, {
    getPayload: buildSettingsConfigPayload({
      openai_base_url: 'https://open.bigmodel.cn/api/coding/paas/v4',
    }),
  })

  await page.route('**/api/v1/config/test-connection', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        providers: { openai: false, anthropic: false, ollama: false },
        provider_errors: {
          current: 'mock connection failure',
          openai: 'mock connection failure'
        },
        graph_store: false,
        vector_store: false,
        current_error: 'mock connection failure'
      })
    })
  })
}

export async function registerT12AnthropicSaveFixtures(page, state) {
  await registerT12CountedConfigFixture(page, state, {
    getPayload: buildSettingsConfigPayload({
      llm_provider: 'anthropic',
      openai_api_key_configured: false,
      anthropic_api_key_configured: true,
    }),
    validatePut: async (payload) => {
      if (payload.llm_provider !== 'anthropic') {
        throw new Error(`Expected llm_provider to be anthropic, got ${payload.llm_provider}`)
      }
      if (payload.anthropic_base_url !== 'https://api.anthropic.com') {
        throw new Error(`Expected anthropic_base_url to be preserved, got ${payload.anthropic_base_url}`)
      }
      if (payload.anthropic_model !== 'claude-sonnet-4-20250514') {
        throw new Error(`Expected anthropic_model to be preserved, got ${payload.anthropic_model}`)
      }
    },
  })
}

export async function registerT12OllamaSaveFixtures(page, state) {
  await registerT12CountedConfigFixture(page, state, {
    getPayload: buildSettingsConfigPayload({
      llm_provider: 'ollama',
      openai_api_key_configured: false,
    }),
    validatePut: async (payload) => {
      if (payload.llm_provider !== 'ollama') {
        throw new Error(`Expected llm_provider to be ollama, got ${payload.llm_provider}`)
      }
      if (payload.ollama_url !== 'http://127.0.0.1:11434') {
        throw new Error(`Expected trimmed ollama_url, got ${payload.ollama_url}`)
      }
      if (payload.ollama_model !== 'qwen2.5:32b') {
        throw new Error(`Expected trimmed ollama_model, got ${payload.ollama_model}`)
      }
    },
  })
}

export async function registerT12DefaultConfigSaveFixtures(page, state) {
  await registerT12CountedConfigFixture(page, state)
}

export async function registerT12SecretStorageUnavailableFixtures(page, state) {
  await registerT12CountedConfigFixture(page, state, {
    getPayload: buildSettingsConfigPayload({
      secret_storage: {
        available: false,
        storage_type: 'environment_only',
        backend: null,
        message: (
          'No usable system keyring backend is available. '
          + 'The Settings page can save non-secret fields only; provide API keys via '
          + 'OPENAI_API_KEY / ANTHROPIC_API_KEY or configure a supported system keyring.'
        ),
        fallback_env_vars: ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY'],
      },
      openai_api_key_configured: false,
      anthropic_api_key_configured: false,
    }),
    validatePut: async (payload) => {
      if (payload.openai_api_key) {
        throw new Error('Expected frontend to block PUT /config when secure secret storage is unavailable')
      }
      if (payload.openai_base_url !== 'https://open.bigmodel.cn/api/coding/paas/v4') {
        throw new Error(`Expected non-secret openai_base_url to be saved, got ${payload.openai_base_url}`)
      }
      if (payload.openai_model !== 'glm-4.7') {
        throw new Error(`Expected non-secret openai_model to be saved, got ${payload.openai_model}`)
      }
    },
  })
}
