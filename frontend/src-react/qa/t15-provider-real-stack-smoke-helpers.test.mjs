import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildProviderSmokeFailureHint,
  buildProviderSmokeArgv,
  buildProviderReadinessRows,
  buildProviderReadinessSummary,
  buildProviderSmokeSummary,
  buildProviderSmokeHint,
  buildProviderSmokeEnv,
  getProviderSmokeCommand,
  getProviderMatrixEvidencePaths,
  getProviderMatrixLogPath,
  getProviderReadinessEvidencePaths,
  getProviderPreflightError,
  normalizeProviderArg,
  parseProviderProfileArgs,
  parseProviderScopeArgs,
  parseProviderSmokeArgs,
  parseProviderList,
  resolveApiKeyEnvValue,
  resolveProviderProfileOverrides,
} from './t15-provider-real-stack-smoke-helpers.mjs'

test('normalizeProviderArg trims and lowercases input', () => {
  assert.equal(normalizeProviderArg('  OLLAMA  '), 'ollama')
})

test('normalizeProviderArg rejects unsupported provider', () => {
  assert.throws(
    () => normalizeProviderArg('custom'),
    /Provider must be one of/
  )
})

test('buildProviderSmokeEnv sets strict transient smoke env for provider', () => {
  assert.deepEqual(
    buildProviderSmokeEnv(
      'anthropic',
      {
        T14_OVERRIDE_OPENAI_MODEL: 'ignored-for-anthropic',
        BIGMODEL_API_KEY: 'secret-value',
      },
      {
        baseUrl: 'https://open.bigmodel.cn/api/anthropic',
        model: 'claude-3-5-sonnet-20241022',
        apiKeyEnv: 'BIGMODEL_API_KEY',
      }
    ),
    {
      T14_OVERRIDE_OPENAI_MODEL: 'ignored-for-anthropic',
      BIGMODEL_API_KEY: 'secret-value',
      T14_EXPECT_PROVIDER: 'anthropic',
      T14_OVERRIDE_PROVIDER: 'anthropic',
      T14_REQUIRE_CURRENT_PROVIDER_SUCCESS: 'true',
      T14_OVERRIDE_ANTHROPIC_API_KEY: 'secret-value',
      T14_OVERRIDE_ANTHROPIC_BASE_URL: 'https://open.bigmodel.cn/api/anthropic',
      T14_OVERRIDE_ANTHROPIC_MODEL: 'claude-3-5-sonnet-20241022',
    }
  )
})

test('buildProviderSmokeHint returns provider-specific guidance', () => {
  assert.match(buildProviderSmokeHint('anthropic', { apiKeyEnv: 'BIGMODEL_API_KEY' }), /BIGMODEL_API_KEY/)
  assert.match(buildProviderSmokeHint('ollama', { url: 'http://127.0.0.1:11434' }), /127.0.0.1:11434/)
  assert.match(buildProviderSmokeHint('openai'), /OpenAI-compatible API key/)
})

test('buildProviderSmokeFailureHint specializes upstream auth failures', () => {
  assert.match(
    buildProviderSmokeFailureHint(
      'anthropic',
      { apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY' },
      "Error code: 401 - {'error': {'message': '令牌已过期或验证不正确'}}"
    ),
    /rejected by the upstream endpoint/
  )
  assert.match(
    buildProviderSmokeFailureHint('openai', { apiKeyEnv: 'OPENAI_API_KEY' }, 'HTTP 401 unauthorized'),
    /OPENAI_API_KEY/
  )
})

test('getProviderSmokeCommand formats npm passthrough flags for overrides', () => {
  assert.equal(
    getProviderSmokeCommand('anthropic', {
      baseUrl: 'https://open.bigmodel.cn/api/anthropic',
      model: 'GLM-4.7',
      apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
    }),
    'npm --prefix frontend run qa:real-stack-smoke:anthropic -- --base-url https://open.bigmodel.cn/api/anthropic --model GLM-4.7 --api-key-env BIGMODEL_API_KEY,ANTHROPIC_API_KEY'
  )
  assert.deepEqual(
    buildProviderSmokeArgv('ollama', {
      url: 'http://127.0.0.1:11434',
      model: 'qwen2.5:32b',
    }),
    ['--url', 'http://127.0.0.1:11434', '--model', 'qwen2.5:32b']
  )
})

test('resolveProviderProfileOverrides returns anthropic bigmodel defaults', () => {
  assert.deepEqual(
    resolveProviderProfileOverrides('anthropic', 'bigmodel'),
    {
      baseUrl: 'https://open.bigmodel.cn/api/anthropic',
      model: 'GLM-4.7',
      apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
    }
  )
})

test('resolveProviderProfileOverrides returns openai bigmodel defaults', () => {
  assert.deepEqual(
    resolveProviderProfileOverrides('openai', 'bigmodel'),
    {
      baseUrl: 'https://open.bigmodel.cn/api/coding/paas/v4',
      model: 'glm-4.7',
      apiKeyEnv: 'OPENAI_API_KEY,BIGMODEL_API_KEY',
    }
  )
})

test('parseProviderProfileArgs parses anthropic profile override', () => {
  assert.deepEqual(
    parseProviderProfileArgs(['--anthropic-profile', 'bigmodel']),
    {
      anthropic: {
        baseUrl: 'https://open.bigmodel.cn/api/anthropic',
        model: 'GLM-4.7',
        apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
      }
    }
  )
})

test('parseProviderList normalizes and deduplicates providers', () => {
  assert.deepEqual(
    parseProviderList(' openai , anthropic,openai '),
    ['openai', 'anthropic']
  )
})

test('parseProviderScopeArgs parses profiles, providers, and evidence suffix', () => {
  assert.deepEqual(
    parseProviderScopeArgs([
      '--providers', 'openai,anthropic',
      '--openai-profile', 'bigmodel',
      '--anthropic-profile', 'bigmodel',
      '--evidence-suffix', 'remote scope',
    ]),
    {
      providerOverrides: {
        openai: {
          baseUrl: 'https://open.bigmodel.cn/api/coding/paas/v4',
          model: 'glm-4.7',
          apiKeyEnv: 'OPENAI_API_KEY,BIGMODEL_API_KEY',
        },
        anthropic: {
          baseUrl: 'https://open.bigmodel.cn/api/anthropic',
          model: 'GLM-4.7',
          apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
        },
      },
      providers: ['openai', 'anthropic'],
      evidenceSuffix: 'remote-scope',
    }
  )
})

test('evidence path helpers preserve legacy names and support suffixes', () => {
  assert.deepEqual(
    getProviderReadinessEvidencePaths('/tmp/evidence'),
    {
      summary: '/tmp/evidence/task-15-provider-readiness.txt',
      json: '/tmp/evidence/task-15-provider-readiness.json',
    }
  )
  assert.deepEqual(
    getProviderMatrixEvidencePaths('/tmp/evidence', 'remote'),
    {
      summary: '/tmp/evidence/task-16-provider-matrix-summary-remote.txt',
      json: '/tmp/evidence/task-16-provider-matrix-summary-remote.json',
    }
  )
  assert.equal(
    getProviderMatrixLogPath('/tmp/evidence', 'anthropic', 'remote'),
    '/tmp/evidence/task-16-provider-matrix-remote-anthropic.log'
  )
})

test('buildProviderSmokeSummary formats provider smoke evidence', () => {
  assert.equal(
    buildProviderSmokeSummary({
      provider: 'openai',
      status: 'passed',
      generatedAt: '2026-03-28T12:00:00.000Z',
      overrides: {
        apiKeyEnv: 'BIGMODEL_API_KEY',
        baseUrl: 'https://api.openai.com/v1',
        model: 'gpt-4o-mini',
      },
      childExitCode: 0,
      childSummaryExcerpt: 'browser_smoke=passed',
    }),
    [
      'provider=openai',
      'status=passed',
      'generated_at=2026-03-28T12:00:00.000Z',
      'override_api_key_env=BIGMODEL_API_KEY',
      'override_model=gpt-4o-mini',
      'override_url=',
      'override_base_url=https://api.openai.com/v1',
      'child_exit_code=0',
      'child_summary_excerpt=browser_smoke=passed',
      'child_error_excerpt=',
      'error=',
      'hint=',
      '',
    ].join('\n')
  )
})

test('buildProviderReadinessRows derives ready and blocked providers from probe', () => {
  assert.deepEqual(
    buildProviderReadinessRows(
      {
        openai: { apiKeyConfigured: true },
        anthropic: { apiKeyConfigured: false },
        ollama: { reachable: false, url: 'http://localhost:11434' },
      },
      {
        anthropic: {
          baseUrl: 'https://open.bigmodel.cn/api/anthropic',
          model: 'GLM-4.7',
          apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
        }
      },
      {
        ANTHROPIC_API_KEY: 'secret-value',
      },
      {
        openai: {
          checked: true,
          ok: true,
          error: '',
        },
        anthropic: {
          checked: true,
          ok: true,
          error: '',
        },
      }
    ),
    [
      {
        provider: 'openai',
        ready: true,
        reason: '',
        hint: '',
        command: getProviderSmokeCommand('openai'),
        overrides: {},
        remote_check: 'passed',
        remote_error: '',
      },
      {
        provider: 'anthropic',
        ready: true,
        reason: '',
        hint: '',
        command: 'npm --prefix frontend run qa:real-stack-smoke:anthropic -- --base-url https://open.bigmodel.cn/api/anthropic --model GLM-4.7 --api-key-env BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
        overrides: {
          baseUrl: 'https://open.bigmodel.cn/api/anthropic',
          model: 'GLM-4.7',
          apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
        },
        remote_check: 'passed',
        remote_error: '',
      },
      {
        provider: 'ollama',
        ready: false,
        reason: 'Ollama endpoint is not reachable at http://localhost:11434',
        hint: 'Hint: ensure Ollama is running at http://localhost:11434 and the target model is available before rerunning `qa:real-stack-smoke:ollama`.',
        command: getProviderSmokeCommand('ollama'),
        overrides: {},
        remote_check: 'skipped',
        remote_error: '',
      },
    ]
  )
})

test('buildProviderReadinessRows turns remote auth failure into blocked readiness', () => {
  assert.deepEqual(
    buildProviderReadinessRows(
      {
        anthropic: { apiKeyConfigured: true },
      },
      {
        anthropic: {
          baseUrl: 'https://open.bigmodel.cn/api/anthropic',
          model: 'GLM-4.7',
          apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
        },
      },
      {
        ANTHROPIC_API_KEY: 'secret-value',
      },
      {
        anthropic: {
          checked: true,
          ok: false,
          error: "Error code: 401 - {'error': {'message': '令牌已过期或验证不正确'}}",
        },
      }
    )[1],
    {
      provider: 'anthropic',
      ready: false,
      reason: "Error code: 401 - {'error': {'message': '令牌已过期或验证不正确'}}",
      hint: 'Hint: the Anthropic-compatible token from one of BIGMODEL_API_KEY or ANTHROPIC_API_KEY was rejected by the upstream endpoint. Update the token and rerun `qa:real-stack-smoke:anthropic`.',
      command: 'npm --prefix frontend run qa:real-stack-smoke:anthropic -- --base-url https://open.bigmodel.cn/api/anthropic --model GLM-4.7 --api-key-env BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
      overrides: {
        baseUrl: 'https://open.bigmodel.cn/api/anthropic',
        model: 'GLM-4.7',
        apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY',
      },
      remote_check: 'failed',
      remote_error: "Error code: 401 - {'error': {'message': '令牌已过期或验证不正确'}}",
    }
  )
})

test('buildProviderReadinessSummary formats metadata and counters', () => {
  assert.equal(
    buildProviderReadinessSummary(
      [
        {
          provider: 'openai',
          ready: true,
          reason: '',
          hint: '',
          command: getProviderSmokeCommand('openai'),
          remote_check: 'passed',
          remote_error: '',
        },
        {
          provider: 'anthropic',
          ready: false,
          reason: 'Anthropic API key is not configured',
          hint: 'configure key',
          command: getProviderSmokeCommand('anthropic'),
          remote_check: 'skipped',
          remote_error: '',
        },
      ],
      {
        generatedAt: '2026-03-28T12:00:00.000Z',
        source: 'qa:real-stack-smoke:readiness',
        providerScope: 'openai,anthropic',
      }
    ),
    [
      'generated_at=2026-03-28T12:00:00.000Z',
      'source=qa:real-stack-smoke:readiness',
      'provider_scope=openai,anthropic',
      '',
      'provider=openai',
      'ready=true',
      'remote_check=passed',
      'remote_error=',
      'reason=',
      'hint=',
      'command=npm --prefix frontend run qa:real-stack-smoke:openai',
      '',
      'provider=anthropic',
      'ready=false',
      'remote_check=skipped',
      'remote_error=',
      'reason=Anthropic API key is not configured',
      'hint=configure key',
      'command=npm --prefix frontend run qa:real-stack-smoke:anthropic',
      '',
      'ready_count=1',
      'blocked_count=1',
      '',
    ].join('\n')
  )
})

test('getProviderPreflightError returns provider-specific blocker', () => {
  assert.equal(
    getProviderPreflightError('anthropic', { anthropic: { apiKeyConfigured: false } }),
    'Anthropic API key is not configured'
  )
  assert.equal(
    getProviderPreflightError(
      'ollama',
      { ollama: { reachable: false, url: 'http://localhost:11434' } },
      { url: 'http://127.0.0.1:11434' }
    ),
    'Ollama endpoint is not reachable at http://127.0.0.1:11434'
  )
  assert.equal(
    getProviderPreflightError('openai', { openai: { apiKeyConfigured: true } }),
    null
  )
  assert.equal(
    getProviderPreflightError(
      'anthropic',
      { anthropic: { apiKeyConfigured: false } },
      { apiKeyEnv: 'BIGMODEL_API_KEY' },
      { BIGMODEL_API_KEY: 'secret-value' }
    ),
    null
  )
})

test('parseProviderSmokeArgs parses positional provider and overrides', () => {
  assert.deepEqual(
    parseProviderSmokeArgs(['openai', '--base-url', 'https://example.com/v1', '--model', 'gpt-4o-mini']),
    {
      provider: 'openai',
      overrides: {
        apiKeyEnv: null,
        baseUrl: 'https://example.com/v1',
        model: 'gpt-4o-mini',
        url: null,
      }
    }
  )
})

test('parseProviderSmokeArgs parses --provider form', () => {
  assert.deepEqual(
    parseProviderSmokeArgs(['--provider', 'ollama', '--url', 'http://127.0.0.1:11434', '--model', 'qwen2.5:32b']),
    {
      provider: 'ollama',
      overrides: {
        apiKeyEnv: null,
        baseUrl: null,
        model: 'qwen2.5:32b',
        url: 'http://127.0.0.1:11434',
      }
    }
  )
})

test('parseProviderSmokeArgs parses api-key-env override', () => {
  assert.deepEqual(
    parseProviderSmokeArgs(['anthropic', '--base-url', 'https://open.bigmodel.cn/api/anthropic', '--model', 'GLM-4.7', '--api-key-env', 'BIGMODEL_API_KEY']),
    {
      provider: 'anthropic',
      overrides: {
        apiKeyEnv: 'BIGMODEL_API_KEY',
        baseUrl: 'https://open.bigmodel.cn/api/anthropic',
        model: 'GLM-4.7',
        url: null,
      }
    }
  )
})

test('resolveApiKeyEnvValue reads key from provided env map', () => {
  assert.equal(
    resolveApiKeyEnvValue({ apiKeyEnv: 'BIGMODEL_API_KEY' }, { BIGMODEL_API_KEY: 'secret-value' }),
    'secret-value'
  )
  assert.equal(
    resolveApiKeyEnvValue(
      { apiKeyEnv: 'BIGMODEL_API_KEY,ANTHROPIC_API_KEY' },
      { ANTHROPIC_API_KEY: 'anthropic-secret' }
    ),
    'anthropic-secret'
  )
})
