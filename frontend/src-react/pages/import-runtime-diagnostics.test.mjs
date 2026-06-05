import test from 'node:test'
import assert from 'node:assert/strict'

import { buildImportRuntimeDiagnosticsSummary } from './import-runtime-diagnostics.js'

test('buildImportRuntimeDiagnosticsSummary returns neutral when diagnostics are unknown', () => {
  assert.deepEqual(
    buildImportRuntimeDiagnosticsSummary(null),
    {
      tone: 'neutral',
      message: '尚未获取导入/同步运行诊断。',
      detail: ''
    }
  )
})

test('buildImportRuntimeDiagnosticsSummary turns failed core checks into import-specific error guidance', () => {
  const summary = buildImportRuntimeDiagnosticsSummary({
    status: 'unhealthy',
    checks: {
      config: { ok: true },
      provider: {
        ok: false,
        current_provider: 'openai',
        current_error: 'OpenAI API key is not configured',
      },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    recent_failures: [{ component: 'provider' }],
  })

  assert.equal(summary.tone, 'error')
  assert.equal(summary.message, '核心运行依赖未通过诊断，导入/同步结果当前不可完全信任。')
  assert.match(summary.detail, /Provider（openai）/)
  assert.match(summary.detail, /OpenAI API key is not configured/)
})

test('buildImportRuntimeDiagnosticsSummary keeps not-configured task chain as a success path', () => {
  const summary = buildImportRuntimeDiagnosticsSummary({
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
      detail: null,
    },
    recent_failures: [],
  })

  assert.equal(summary.tone, 'success')
  assert.equal(summary.message, '当前没有配置外部记忆源；不影响文件、目录和会话导入。')
  assert.match(summary.detail, /外部记忆源/)
})

test('buildImportRuntimeDiagnosticsSummary reports warning for sync attention items', () => {
  const summary = buildImportRuntimeDiagnosticsSummary({
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
    recent_failures: [],
  })

  assert.equal(summary.tone, 'warning')
  assert.equal(summary.message, '核心运行依赖健康，但同步链路仍有待处理项。')
  assert.match(summary.detail, /Task Chain：1 sync source\(s\) need attention/)
})

test('buildImportRuntimeDiagnosticsSummary reports trusted sync path when task chain is healthy', () => {
  const summary = buildImportRuntimeDiagnosticsSummary({
    status: 'healthy',
    checks: {
      config: { ok: true },
      provider: { ok: true, current_provider: 'openai' },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    task_chain: {
      status: 'healthy',
      configured_sources: 2,
      sources: [{ source_id: 'src-1' }],
      detail: null,
    },
    recent_failures: [],
  })

  assert.equal(summary.tone, 'success')
  assert.equal(summary.message, '核心运行依赖健康，导入/同步链路当前可信。')
  assert.equal(summary.detail, '已配置 source：2')
})

test('buildImportRuntimeDiagnosticsSummary adds sync recovery guidance for degraded task chain', () => {
  const summary = buildImportRuntimeDiagnosticsSummary({
    status: 'healthy',
    checks: {
      config: { ok: true },
      provider: { ok: true, current_provider: 'openai' },
      sqlite: { ok: true },
      vector_store: { ok: true },
    },
    task_chain: {
      status: 'degraded',
      configured_sources: 2,
      detail: '2 sync source(s) need attention',
      sources: [],
    },
    recent_failures: [],
  })

  assert.equal(summary.tone, 'warning')
  assert.match(summary.detail, /先处理 source 冲突\/路径问题/)
})
