import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildHealthyRuntimeDiagnosticsPayload,
  buildSettingsConfigPayload,
  buildSettingsConfigUpdateSuccessPayload,
  registerHealthyRuntimeDiagnosticsRoute,
  registerSettingsConfigRoute,
} from './settings-playwright-mocks.mjs'

test('buildSettingsConfigPayload returns stable default config with overrides', () => {
  const payload = buildSettingsConfigPayload({
    llm_provider: 'anthropic',
    anthropic_api_key_configured: true,
    openai_api_key_configured: false,
  })

  assert.equal(payload.llm_provider, 'anthropic')
  assert.equal(payload.embedding_model, 'text-embedding-3-large')
  assert.equal(payload.vector_store_type, 'faiss')
  assert.equal(payload.anthropic_api_key_configured, true)
  assert.equal(payload.openai_api_key_configured, false)
  assert.equal(payload.ollama_url, 'http://localhost:11434')
  assert.equal(payload.secret_storage.available, true)
})

test('buildSettingsConfigUpdateSuccessPayload keeps stable success response', () => {
  assert.deepEqual(buildSettingsConfigUpdateSuccessPayload(), {
    success: true,
    message: 'Configuration saved to settings.yaml',
  })
})

test('buildHealthyRuntimeDiagnosticsPayload returns healthy diagnostics with overrides', () => {
  const payload = buildHealthyRuntimeDiagnosticsPayload({
    generatedAt: '2026-04-03T13:30:00Z',
    currentProvider: 'ollama',
    providers: { openai: false, ollama: true },
    indexedDocuments: 12,
    storedDocuments: 14,
  })

  assert.equal(payload.status, 'healthy')
  assert.equal(payload.generated_at, '2026-04-03T13:30:00Z')
  assert.equal(payload.checks.provider.current_provider, 'ollama')
  assert.deepEqual(payload.checks.provider.providers, { openai: false, ollama: true })
  assert.equal(payload.checks.vector_store.state.indexed_documents, 12)
  assert.equal(payload.checks.vector_store.state.stored_documents, 14)
  assert.equal(payload.task_chain.status, 'not_configured')
})

test('registerSettingsConfigRoute fulfills GET config and validated PUT success response', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }
  const seen = []

  await registerSettingsConfigRoute(page, {
    getPayload: buildSettingsConfigPayload({ llm_provider: 'anthropic' }),
    onPut: async (payload) => {
      seen.push(payload)
    },
  })

  assert.equal(registrations.length, 1)
  assert.equal(registrations[0].url, '**/api/v1/config')

  const fulfilled = []
  const route = {
    request: () => ({
      method: () => 'GET',
    }),
    fulfill: async (payload) => {
      fulfilled.push(payload)
    },
    fallback: async () => {
      fulfilled.push('fallback')
    },
  }
  await registrations[0].handler(route)
  assert.equal(JSON.parse(fulfilled[0].body).llm_provider, 'anthropic')

  const putRoute = {
    request: () => ({
      method: () => 'PUT',
      postDataJSON: () => ({ openai_model: 'glm-4.7' }),
    }),
    fulfill: async (payload) => {
      fulfilled.push(payload)
    },
    fallback: async () => {
      fulfilled.push('fallback')
    },
  }
  await registrations[0].handler(putRoute)
  assert.deepEqual(seen, [{ openai_model: 'glm-4.7' }])
  assert.deepEqual(JSON.parse(fulfilled[1].body), buildSettingsConfigUpdateSuccessPayload())
})

test('registerHealthyRuntimeDiagnosticsRoute fulfills stable diagnostics payload', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }

  await registerHealthyRuntimeDiagnosticsRoute(page, {
    generatedAt: '2026-04-03T13:30:00Z',
    indexedDocuments: 12,
  })

  assert.equal(registrations.length, 1)
  assert.equal(registrations[0].url, '**/api/v1/diagnostics/runtime')

  const fulfilled = []
  await registrations[0].handler({
    fulfill: async (payload) => {
      fulfilled.push(payload)
    },
  })

  const body = JSON.parse(fulfilled[0].body)
  assert.equal(body.generated_at, '2026-04-03T13:30:00Z')
  assert.equal(body.checks.vector_store.state.indexed_documents, 12)
})
