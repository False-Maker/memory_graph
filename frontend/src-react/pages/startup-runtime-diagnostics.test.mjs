import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildBackendDiagnosticsUnavailableState,
  buildBackendStartupState,
  buildDownStartupServiceState,
  buildSidecarStartupState,
  buildStartupAlertState,
  normalizeProbeError,
} from './startup-runtime-diagnostics.js'

test('normalizeProbeError returns a stable string', () => {
  assert.equal(normalizeProbeError(null), 'unknown error')
  assert.equal(normalizeProbeError(new Error('timeout')), 'timeout')
})

test('buildDownStartupServiceState records a down service result', () => {
  assert.deepEqual(
    buildDownStartupServiceState('HTTP 503', '2026-04-08T01:00:00Z'),
    {
      status: 'down',
      detail: 'HTTP 503',
      checkedAt: '2026-04-08T01:00:00Z',
      runtimeTone: 'unknown',
      runtimeMessage: '',
      runtimeDetail: '',
    }
  )
})

test('buildSidecarStartupState rejects unexpected payloads', () => {
  assert.equal(
    buildSidecarStartupState({ status: 'DOWN' }, '2026-04-08T01:00:00Z').status,
    'down'
  )
  assert.equal(
    buildSidecarStartupState({ status: 'UP' }, '2026-04-08T01:00:00Z').status,
    'up'
  )
})

test('buildBackendStartupState marks healthy backend diagnostics as trusted', () => {
  const result = buildBackendStartupState(
    { status: 'healthy' },
    {
      status: 'healthy',
      generated_at: '2026-04-08T01:00:00Z',
      checks: {
        config: { ok: true },
        provider: { ok: true, current_provider: 'openai' },
        sqlite: { ok: true },
        vector_store: { ok: true },
      },
      task_chain: { status: 'not_configured', configured_sources: 0, sources: [] },
      recent_failures: [],
    },
    '2026-04-08T01:00:01Z'
  )

  assert.equal(result.status, 'up')
  assert.equal(result.runtimeTone, 'healthy')
  assert.match(result.runtimeMessage, /当前没有待处理诊断项/)
})

test('buildBackendStartupState surfaces warning diagnostics without collapsing reachability', () => {
  const result = buildBackendStartupState(
    { status: 'healthy' },
    {
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
    },
    '2026-04-08T01:00:01Z'
  )

  assert.equal(result.status, 'up')
  assert.equal(result.runtimeTone, 'warning')
  assert.match(result.runtimeMessage, /核心运行依赖未通过诊断/)
  assert.match(result.runtimeDetail, /OpenAI API key is not configured/)
})

test('buildBackendDiagnosticsUnavailableState keeps service reachable but warns', () => {
  const result = buildBackendDiagnosticsUnavailableState(new Error('timeout'), '2026-04-08T01:00:01Z')

  assert.equal(result.status, 'up')
  assert.equal(result.runtimeTone, 'warning')
  assert.match(result.runtimeMessage, /无法确认 backend 运行态是否可信/)
  assert.equal(result.runtimeDetail, 'timeout')
})

test('buildStartupAlertState distinguishes error, warning, and success', () => {
  assert.deepEqual(
    buildStartupAlertState({
      backend: { status: 'down' },
      sidecar: { status: 'up' },
    }),
    {
      tone: 'error',
      message: '检测到基础服务不可达。请先确认 backend 与 sidecar 已启动，再刷新本页重新检查。',
    }
  )

  assert.deepEqual(
    buildStartupAlertState({
      backend: { status: 'up', runtimeTone: 'warning' },
      sidecar: { status: 'up' },
    }),
    {
      tone: 'warning',
      message: '基础服务可达，但 backend 运行诊断仍有告警。请先到 Settings 检查当前 provider、存储和最近失败记录。',
    }
  )

  assert.deepEqual(
    buildStartupAlertState({
      backend: { status: 'up', runtimeTone: 'healthy' },
      sidecar: { status: 'up' },
    }),
    {
      tone: 'success',
      message: '所有基础服务探测通过，当前启动状态可继续进入功能页面。',
    }
  )
})
