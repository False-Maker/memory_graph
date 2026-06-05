import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildProviderMatrixSummary,
  extractSummaryField,
} from './t16-provider-matrix-helpers.mjs'

test('extractSummaryField reads top-level provider summary fields', () => {
  const raw = [
    'provider=anthropic',
    'status=preflight_failed',
    'hint=Hint text',
    'error=Error: failed',
    '',
  ].join('\n')

  assert.equal(extractSummaryField(raw, 'status'), 'preflight_failed')
  assert.equal(extractSummaryField(raw, 'hint'), 'Hint text')
})

test('buildProviderMatrixSummary formats rows and counters', () => {
  assert.equal(
    buildProviderMatrixSummary(
      [
        { provider: 'openai', status: 'passed', readiness: 'ready', reason: '', exitCode: 0, command: 'cmd-openai', log: 'openai.log', summaryExcerpt: 'ok' },
        { provider: 'anthropic', status: 'blocked', readiness: 'blocked', reason: 'auth rejected', exitCode: 1, command: 'cmd-anthropic', hint: 'configure key', log: 'anthropic.log' },
        { provider: 'ollama', status: 'failed', readiness: 'ready', reason: 'request timeout', exitCode: 1, command: 'cmd-ollama', hint: 'start service', log: 'ollama.log' },
      ],
      {
        generatedAt: '2026-03-28T12:00:00.000Z',
        source: 'qa:real-stack-smoke:matrix',
        readinessEvidence: '.sisyphus/evidence/task-15-provider-readiness.json',
        providerScope: 'openai,anthropic,ollama',
      }
    ),
    [
      'generated_at=2026-03-28T12:00:00.000Z',
      'source=qa:real-stack-smoke:matrix',
      'readiness_evidence=.sisyphus/evidence/task-15-provider-readiness.json',
      'provider_scope=openai,anthropic,ollama',
      '',
      'provider=openai',
      'status=passed',
      'readiness=ready',
      'reason=',
      'exit_code=0',
      'command=cmd-openai',
      'hint=',
      'evidence=',
      'log=openai.log',
      'summary_excerpt=ok',
      '',
      'provider=anthropic',
      'status=blocked',
      'readiness=blocked',
      'reason=auth rejected',
      'exit_code=1',
      'command=cmd-anthropic',
      'hint=configure key',
      'evidence=',
      'log=anthropic.log',
      'summary_excerpt=',
      '',
      'provider=ollama',
      'status=failed',
      'readiness=ready',
      'reason=request timeout',
      'exit_code=1',
      'command=cmd-ollama',
      'hint=start service',
      'evidence=',
      'log=ollama.log',
      'summary_excerpt=',
      '',
      'passed_count=1',
      'blocked_count=1',
      'failed_count=1',
      '',
    ].join('\n')
  )
})
