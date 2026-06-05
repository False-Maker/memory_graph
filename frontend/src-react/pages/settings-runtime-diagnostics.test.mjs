import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_RUNTIME_DIAGNOSTICS,
  buildConfigSavedMessage,
  buildRuntimeDiagnosticsSummary,
  getFailedRuntimeDiagnosticsChecks,
  hasRuntimeDiagnostics,
  normalizeRuntimeDiagnostics,
} from './settings-runtime-diagnostics.js'

test('normalizeRuntimeDiagnostics returns stable defaults for empty payloads', () => {
  assert.deepEqual(normalizeRuntimeDiagnostics(null), DEFAULT_RUNTIME_DIAGNOSTICS)
})

test('hasRuntimeDiagnostics only turns true after a non-unknown payload', () => {
  assert.equal(hasRuntimeDiagnostics(null), false)
  assert.equal(hasRuntimeDiagnostics({ status: 'healthy' }), true)
})

test('getFailedRuntimeDiagnosticsChecks lists failed core checks with provider name', () => {
  assert.deepEqual(
    getFailedRuntimeDiagnosticsChecks({
      status: 'unhealthy',
      checks: {
        config: { ok: true },
        provider: { ok: false, current_provider: 'openai' },
        sqlite: { ok: false },
        vector_store: { ok: true },
      },
    }),
    ['Provider（openai）', '图存储']
  )
})

test('buildRuntimeDiagnosticsSummary reports core failure details', () => {
  const summary = buildRuntimeDiagnosticsSummary({
    status: 'unhealthy',
    checks: {
      config: { ok: true },
      provider: { ok: false, current_provider: 'openai', current_error: 'OpenAI API key is not configured' },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    recent_failures: [{ component: 'provider' }],
  })

  assert.equal(summary.tone, 'error')
  assert.equal(summary.message, '核心运行依赖未通过诊断：Provider（openai）。')
  assert.match(summary.detail, /OpenAI API key is not configured/)
  assert.match(summary.detail, /最近失败记录 1 条/)
})

test('buildRuntimeDiagnosticsSummary distinguishes warning-only attention items', () => {
  const summary = buildRuntimeDiagnosticsSummary({
    status: 'healthy',
    checks: {
      config: { ok: true },
      provider: { ok: true, current_provider: 'openai' },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    task_chain: {
      status: 'degraded',
      configured_sources: 1,
      detail: '1 sync source(s) need attention',
      sources: [],
    },
  })

  assert.equal(summary.tone, 'warning')
  assert.equal(summary.message, '核心运行依赖健康，但仍有待处理项。')
  assert.match(summary.detail, /Task Chain：1 sync source\(s\) need attention/)
})

test('buildRuntimeDiagnosticsSummary reports clean success state', () => {
  const summary = buildRuntimeDiagnosticsSummary({
    status: 'healthy',
    checks: {
      config: { ok: true },
      provider: { ok: true, current_provider: 'openai' },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    task_chain: {
      status: 'not_configured',
      configured_sources: 0,
      sources: [],
    },
    recent_failures: [],
  })

  assert.equal(summary.tone, 'success')
  assert.equal(summary.message, '核心运行依赖健康，当前没有待处理诊断项。')
  assert.match(summary.detail, /Task Chain 未配置/)
})

test('buildConfigSavedMessage reflects refreshed runtime diagnostics outcome', () => {
  assert.equal(buildConfigSavedMessage(null), '配置已保存，运行诊断尚未刷新。')
  assert.equal(
    buildConfigSavedMessage({
      status: 'unhealthy',
      checks: {
        config: { ok: true },
        provider: { ok: false, current_provider: 'openai' },
        sqlite: { ok: true },
        vector_store: { ok: true },
      },
    }),
    '配置已保存，但运行诊断仍未通过：Provider（openai）。'
  )
  assert.equal(
    buildConfigSavedMessage({
      status: 'healthy',
      checks: {
        config: { ok: true },
        provider: { ok: true, current_provider: 'openai' },
        sqlite: { ok: true },
        vector_store: { ok: true },
      },
      task_chain: { status: 'degraded', configured_sources: 1, sources: [] },
    }),
    '配置已保存，但运行诊断仍有待处理项。'
  )
  assert.equal(
    buildConfigSavedMessage({
      status: 'healthy',
      checks: {
        config: { ok: true },
        provider: { ok: true, current_provider: 'openai' },
        sqlite: { ok: true },
        vector_store: { ok: true },
      },
      recent_failures: [],
    }),
    '配置已保存，运行诊断已刷新。'
  )
})

test('buildRuntimeDiagnosticsSummary adds vector store reindex guidance when dimension mismatch is present', () => {
  const summary = buildRuntimeDiagnosticsSummary({
    status: 'unhealthy',
    checks: {
      config: { ok: true },
      provider: { ok: true, current_provider: 'openai' },
      sqlite: { ok: true },
      vector_store: { ok: false, state: { dimension_mismatch: true } },
    },
    recent_failures: [],
  })

  assert.equal(summary.tone, 'error')
  assert.match(summary.detail, /执行 reindex/)
})

test('buildRuntimeDiagnosticsSummary adds task-chain guidance for degraded attention items', () => {
  const summary = buildRuntimeDiagnosticsSummary({
    status: 'healthy',
    checks: {
      config: { ok: true },
      provider: { ok: true, current_provider: 'openai' },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    task_chain: {
      status: 'degraded',
      configured_sources: 1,
      detail: '1 sync source(s) need attention',
      sources: [],
    },
    recent_failures: [{ component: 'task_chain' }],
  })

  assert.equal(summary.tone, 'warning')
  assert.match(summary.detail, /外部记忆源/)
  assert.match(summary.detail, /recent failures/i)
})
