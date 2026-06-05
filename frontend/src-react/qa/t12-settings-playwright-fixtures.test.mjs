import test from 'node:test'
import assert from 'node:assert/strict'

import {
  registerT12AnthropicSaveFixtures,
  registerT12DefaultConfigSaveFixtures,
  buildT12SaveHappyPathDiagnosticsPayload,
  registerT12ConnectionFailureFixtures,
  registerT12OllamaSaveFixtures,
  registerT12SecretStorageUnavailableFixtures,
  registerT12SaveHappyPathFixtures,
} from './t12-settings-playwright-fixtures.mjs'

test('buildT12SaveHappyPathDiagnosticsPayload returns stable degraded diagnostics payload', () => {
  const payload = buildT12SaveHappyPathDiagnosticsPayload()

  assert.equal(payload.status, 'unhealthy')
  assert.equal(payload.generated_at, '2026-04-03T12:00:00Z')
  assert.equal(payload.checks.provider.ok, false)
  assert.equal(payload.checks.provider.current_error, 'mock provider timeout')
  assert.equal(payload.task_chain.status, 'degraded')
  assert.equal(payload.task_chain.sources[0].label, 'workspace-main')
  assert.equal(payload.recent_failures[0].detail, 'mock provider timeout')
})

test('registerT12SaveHappyPathFixtures wires diagnostics, config PUT validation, and test-connection route', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }
  const state = {
    putCount: 0,
    testConnectionCount: 0,
    diagnosticsCalls: 0,
  }

  await registerT12SaveHappyPathFixtures(page, state)

  assert.equal(registrations.length, 3)
  assert.deepEqual(
    registrations.map(({ url }) => url),
    [
      '**/api/v1/diagnostics/runtime',
      '**/api/v1/config/test-connection',
      '**/api/v1/config',
    ]
  )

  const diagnosticsFulfilled = []
  await registrations[0].handler({
    fulfill: async (payload) => {
      diagnosticsFulfilled.push(payload)
    },
  })
  assert.equal(state.diagnosticsCalls, 1)
  assert.equal(JSON.parse(diagnosticsFulfilled[0].body).task_chain.status, 'degraded')

  const testConnectionFulfilled = []
  await registrations[1].handler({
    request: () => ({
      postDataJSON: () => ({
        openai_base_url: 'https://mock-override.example/v1',
        openai_model: 'glm-4.7-preview',
      }),
    }),
    fulfill: async (payload) => {
      testConnectionFulfilled.push(payload)
    },
  })
  assert.equal(state.testConnectionCount, 1)
  assert.equal(JSON.parse(testConnectionFulfilled[0].body).success, true)

  const configFulfilled = []
  await registrations[2].handler({
    request: () => ({
      method: () => 'PUT',
      postDataJSON: () => ({
        openai_base_url: 'https://open.bigmodel.cn/api/coding/paas/v4',
        openai_model: 'glm-4.7',
      }),
    }),
    fulfill: async (payload) => {
      configFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('config PUT should not fallback')
    },
  })
  assert.equal(state.putCount, 1)
  assert.equal(JSON.parse(configFulfilled[0].body).success, true)
})

test('registerT12SaveHappyPathFixtures rejects unexpected unsaved test-connection payload', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }

  await registerT12SaveHappyPathFixtures(page, {
    putCount: 0,
    testConnectionCount: 0,
    diagnosticsCalls: 0,
  })

  await assert.rejects(
    () => registrations[1].handler({
      request: () => ({
        postDataJSON: () => ({
          openai_base_url: 'https://api.openai.com/v1',
          openai_model: 'gpt-4o',
        }),
      }),
      fulfill: async () => {},
    }),
    /Expected unsaved openai_base_url/
  )
})

test('registerT12ConnectionFailureFixtures wires config default and failure test-connection route', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }

  await registerT12ConnectionFailureFixtures(page)

  assert.equal(registrations.length, 3)
  assert.deepEqual(
    registrations.map(({ url }) => url),
    [
      '**/api/v1/diagnostics/runtime',
      '**/api/v1/config',
      '**/api/v1/config/test-connection',
    ]
  )

  const diagnosticsFulfilled = []
  await registrations[0].handler({
    fulfill: async (payload) => {
      diagnosticsFulfilled.push(payload)
    },
  })
  assert.equal(JSON.parse(diagnosticsFulfilled[0].body).status, 'healthy')

  const configFulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'GET',
    }),
    fulfill: async (payload) => {
      configFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('config GET should not fallback')
    },
  })
  assert.equal(JSON.parse(configFulfilled[0].body).openai_base_url, 'https://open.bigmodel.cn/api/coding/paas/v4')

  const failureFulfilled = []
  await registrations[2].handler({
    fulfill: async (payload) => {
      failureFulfilled.push(payload)
    },
  })
  const body = JSON.parse(failureFulfilled[0].body)
  assert.equal(body.success, false)
  assert.equal(body.current_error, 'mock connection failure')
})

test('registerT12AnthropicSaveFixtures wires anthropic defaults and validated PUT route', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }
  const state = { putCount: 0 }

  await registerT12AnthropicSaveFixtures(page, state)

  assert.equal(registrations.length, 2)
  assert.equal(registrations[0].url, '**/api/v1/diagnostics/runtime')
  assert.equal(registrations[1].url, '**/api/v1/config')

  const getFulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'GET',
    }),
    fulfill: async (payload) => {
      getFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('anthropic GET should not fallback')
    },
  })
  const getBody = JSON.parse(getFulfilled[0].body)
  assert.equal(getBody.llm_provider, 'anthropic')
  assert.equal(getBody.anthropic_api_key_configured, true)

  const putFulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'PUT',
      postDataJSON: () => ({
        llm_provider: 'anthropic',
        anthropic_base_url: 'https://api.anthropic.com',
        anthropic_model: 'claude-sonnet-4-20250514',
      }),
    }),
    fulfill: async (payload) => {
      putFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('anthropic PUT should not fallback')
    },
  })
  assert.equal(state.putCount, 1)
  assert.equal(JSON.parse(putFulfilled[0].body).success, true)
})

test('registerT12OllamaSaveFixtures wires ollama defaults and validated PUT route', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }
  const state = { putCount: 0 }

  await registerT12OllamaSaveFixtures(page, state)

  assert.equal(registrations.length, 2)
  const fulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'PUT',
      postDataJSON: () => ({
        llm_provider: 'ollama',
        ollama_url: 'http://127.0.0.1:11434',
        ollama_model: 'qwen2.5:32b',
      }),
    }),
    fulfill: async (payload) => {
      fulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('ollama PUT should not fallback')
    },
  })
  assert.equal(state.putCount, 1)
  assert.equal(JSON.parse(fulfilled[0].body).success, true)
})

test('registerT12DefaultConfigSaveFixtures wires default config and counted PUT route', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }
  const state = { putCount: 0 }

  await registerT12DefaultConfigSaveFixtures(page, state)

  assert.equal(registrations.length, 2)

  const getFulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'GET',
    }),
    fulfill: async (payload) => {
      getFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('default GET should not fallback')
    },
  })
  assert.equal(JSON.parse(getFulfilled[0].body).llm_provider, 'openai')

  const putFulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'PUT',
      postDataJSON: () => ({
        graph: { defaultLayout: 'clustered' },
      }),
    }),
    fulfill: async (payload) => {
      putFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('default PUT should not fallback')
    },
  })
  assert.equal(state.putCount, 1)
  assert.equal(JSON.parse(putFulfilled[0].body).success, true)
})

test('registerT12SecretStorageUnavailableFixtures exposes unavailable secret storage and rejects secret PUT payloads', async () => {
  const registrations = []
  const page = {
    route: async (url, handler) => {
      registrations.push({ url, handler })
    },
  }
  const state = { putCount: 0 }

  await registerT12SecretStorageUnavailableFixtures(page, state)

  assert.equal(registrations.length, 2)

  const getFulfilled = []
  await registrations[1].handler({
    request: () => ({
      method: () => 'GET',
    }),
    fulfill: async (payload) => {
      getFulfilled.push(payload)
    },
    fallback: async () => {
      throw new Error('secret storage unavailable GET should not fallback')
    },
  })
  const getBody = JSON.parse(getFulfilled[0].body)
  assert.equal(getBody.secret_storage.available, false)
  assert.equal(getBody.secret_storage.storage_type, 'environment_only')

  await assert.rejects(
    () => registrations[1].handler({
      request: () => ({
        method: () => 'PUT',
        postDataJSON: () => ({
          openai_api_key: 'sk-test',
          openai_base_url: 'https://open.bigmodel.cn/api/coding/paas/v4',
          openai_model: 'glm-4.7',
        }),
      }),
      fulfill: async () => {},
      fallback: async () => {
        throw new Error('secret storage unavailable PUT should not fallback')
      },
    }),
    /block PUT \/config/
  )
})
