import test from 'node:test'
import assert from 'node:assert/strict'

import {
  assertCurrentProviderConnection,
  buildConfigPayloadFromSettings,
  buildConnectionSummary,
  buildOverrideConfigPayload,
  configPayloadEquals,
  getProviderFieldExpectation,
  parseRequireFlag,
  resolveCurrentProvider
} from './t14-real-stack-smoke-helpers.mjs'

test('parseRequireFlag recognizes supported truthy values', () => {
  assert.equal(parseRequireFlag('true'), true)
  assert.equal(parseRequireFlag(' YES '), true)
  assert.equal(parseRequireFlag('0'), false)
  assert.equal(parseRequireFlag(undefined), false)
})

test('buildConnectionSummary formats provider and store status', () => {
  assert.equal(
    buildConnectionSummary({
      success: true,
      providers: { openai: true, anthropic: false },
      graph_store: true,
      vector_store: false
    }),
    'success=true | providers(openai=true, anthropic=false) | graph_store=true | vector_store=false'
  )
})

test('buildConnectionSummary includes current_error when present', () => {
  assert.equal(
    buildConnectionSummary({
      success: false,
      providers: { openai: false },
      graph_store: true,
      vector_store: true,
      current_error: 'invalid api key'
    }),
    'success=false | providers(openai=false) | graph_store=true | vector_store=true | current_error=invalid api key'
  )
})

test('buildConfigPayloadFromSettings normalizes visible config with defaults', () => {
  assert.deepEqual(
    buildConfigPayloadFromSettings({
      llm_provider: 'openai',
      openai_base_url: ' https://api.openai.com/v1 ',
      openai_model: '',
      anthropic_model: ' claude-sonnet-4-20250514 ',
      ollama_url: null
    }),
    {
      llm_provider: 'openai',
      openai_base_url: 'https://api.openai.com/v1',
      openai_model: 'gpt-4o',
      anthropic_base_url: 'https://api.anthropic.com',
      anthropic_model: 'claude-sonnet-4-20250514',
      ollama_url: 'http://localhost:11434',
      ollama_model: 'qwen2.5:14b'
    }
  )
})

test('resolveCurrentProvider returns valid provider and normalizes expected value', () => {
  assert.equal(
    resolveCurrentProvider({ llm_provider: 'openai' }, '  OPENAI  '),
    'openai'
  )
})

test('resolveCurrentProvider rejects unsupported current provider', () => {
  assert.throws(
    () => resolveCurrentProvider({ llm_provider: 'custom' }),
    /unsupported llm_provider=custom/
  )
})

test('resolveCurrentProvider rejects unsupported expected provider', () => {
  assert.throws(
    () => resolveCurrentProvider({ llm_provider: 'openai' }, 'custom'),
    /T14_EXPECT_PROVIDER must be one of/
  )
})

test('buildOverrideConfigPayload applies trimmed override fields', () => {
  assert.deepEqual(
    buildOverrideConfigPayload(
      {
        llm_provider: 'openai',
        openai_base_url: 'https://api.openai.com/v1',
        openai_model: 'gpt-4o',
        anthropic_model: 'claude-sonnet-4-20250514',
        ollama_url: 'http://localhost:11434',
        ollama_model: 'qwen2.5:14b'
      },
      {
        T14_OVERRIDE_PROVIDER: ' ollama ',
        T14_OVERRIDE_OLLAMA_URL: '  http://127.0.0.1:11434  ',
        T14_OVERRIDE_OLLAMA_MODEL: '  qwen2.5:32b  '
      }
    ),
    {
      payload: {
        llm_provider: 'ollama',
        openai_base_url: 'https://api.openai.com/v1',
        openai_model: 'gpt-4o',
        anthropic_model: 'claude-sonnet-4-20250514',
        ollama_url: 'http://127.0.0.1:11434',
        ollama_model: 'qwen2.5:32b'
      },
      changedFields: ['llm_provider', 'ollama_url', 'ollama_model'],
      overrideApplied: true
    }
  )
})

test('buildOverrideConfigPayload rejects unsupported override provider', () => {
  assert.throws(
    () => buildOverrideConfigPayload(
      buildConfigPayloadFromSettings({ llm_provider: 'openai' }),
      { T14_OVERRIDE_PROVIDER: 'custom' }
    ),
    /T14_OVERRIDE_PROVIDER must be one of/
  )
})

test('getProviderFieldExpectation returns provider-specific selectors', () => {
  assert.deepEqual(
    getProviderFieldExpectation('ollama'),
    {
      summary: 'ollama(url,model)',
      selectors: ['#settings-ollama-url', '#settings-ollama-model']
    }
  )
})

test('configPayloadEquals compares visible config payloads', () => {
  assert.equal(
    configPayloadEquals(
      buildConfigPayloadFromSettings({ llm_provider: 'openai', openai_model: 'gpt-4o' }),
      buildConfigPayloadFromSettings({ llm_provider: 'openai', openai_model: 'gpt-4o' })
    ),
    true
  )
  assert.equal(
    configPayloadEquals(
      buildConfigPayloadFromSettings({ llm_provider: 'openai' }),
      buildConfigPayloadFromSettings({ llm_provider: 'ollama' })
    ),
    false
  )
})

test('assertCurrentProviderConnection allows false when not required', () => {
  assert.equal(
    assertCurrentProviderConnection({ providers: { anthropic: false } }, 'anthropic', false),
    false
  )
})

test('assertCurrentProviderConnection rejects false when required', () => {
  assert.throws(
    () => assertCurrentProviderConnection({
      providers: { current: false },
      provider_errors: { ollama: 'endpoint not reachable' }
    }, 'ollama', true),
    /endpoint not reachable/
  )
})

test('assertCurrentProviderConnection prefers current provider result when present', () => {
  assert.equal(
    assertCurrentProviderConnection({
      providers: { current: true, anthropic: false }
    }, 'anthropic', true),
    true
  )
})
