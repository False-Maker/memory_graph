import test from 'node:test'
import assert from 'node:assert/strict'
import os from 'node:os'
import path from 'node:path'
import { mkdtemp, rm, writeFile } from 'node:fs/promises'

import {
  evaluateRemoteDoctorEvidence,
  loadRemoteDoctorEvidence,
  parseRemoteDoctorArgs,
} from './t17-provider-remote-doctor-helpers.mjs'

test('parseRemoteDoctorArgs applies remote defaults and refresh flag', () => {
  assert.deepEqual(
    parseRemoteDoctorArgs(['--refresh']),
    {
      refresh: true,
      scopeArgs: [
        '--providers', 'openai,anthropic',
        '--openai-profile', 'bigmodel',
        '--anthropic-profile', 'bigmodel',
        '--evidence-suffix', 'remote',
      ],
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
      evidenceSuffix: 'remote',
    }
  )
})

test('evaluateRemoteDoctorEvidence returns green for fully passing remote evidence', () => {
  const report = evaluateRemoteDoctorEvidence({
    readiness: {
      generated_at: '2026-03-29T16:15:47.737Z',
      provider_scope: 'openai,anthropic',
      evidence_suffix: 'remote',
      providers: [
        { provider: 'openai', ready: true, remote_check: 'passed' },
        { provider: 'anthropic', ready: true, remote_check: 'passed' },
      ],
      counts: {
        ready: 2,
        blocked: 0,
      },
    },
    matrix: {
      generated_at: '2026-03-29T16:15:47.737Z',
      provider_scope: 'openai,anthropic',
      evidence_suffix: 'remote',
      readiness_evidence: '.sisyphus/evidence/task-15-provider-readiness-remote.json',
      providers: [
        { provider: 'openai', status: 'passed', readiness: 'ready' },
        { provider: 'anthropic', status: 'passed', readiness: 'ready' },
      ],
      counts: {
        passed: 2,
        blocked: 0,
        failed: 0,
      },
    },
    providers: ['openai', 'anthropic'],
    evidenceSuffix: 'remote',
    expectedReadinessEvidenceRef: '.sisyphus/evidence/task-15-provider-readiness-remote.json',
  })

  assert.equal(report.status, 'green')
  assert.equal(report.exitCode, 0)
  assert.match(report.line, /remote_doctor=green/)
  assert.match(report.line, /readiness_ready=2\/2/)
  assert.match(report.line, /matrix_failed=-/)
})

test('evaluateRemoteDoctorEvidence returns red when a provider is blocked or failed', () => {
  const report = evaluateRemoteDoctorEvidence({
    readiness: {
      generated_at: '2026-03-29T16:15:47.737Z',
      provider_scope: 'openai,anthropic',
      evidence_suffix: 'remote',
      providers: [
        { provider: 'openai', ready: true, remote_check: 'passed' },
        { provider: 'anthropic', ready: false, remote_check: 'failed' },
      ],
      counts: {
        ready: 1,
        blocked: 1,
      },
    },
    matrix: {
      generated_at: '2026-03-29T16:15:47.737Z',
      provider_scope: 'openai,anthropic',
      evidence_suffix: 'remote',
      readiness_evidence: '.sisyphus/evidence/task-15-provider-readiness-remote.json',
      providers: [
        { provider: 'openai', status: 'passed', readiness: 'ready' },
        { provider: 'anthropic', status: 'blocked', readiness: 'blocked' },
      ],
      counts: {
        passed: 1,
        blocked: 1,
        failed: 0,
      },
    },
    providers: ['openai', 'anthropic'],
    evidenceSuffix: 'remote',
    expectedReadinessEvidenceRef: '.sisyphus/evidence/task-15-provider-readiness-remote.json',
  })

  assert.equal(report.status, 'red')
  assert.equal(report.exitCode, 1)
  assert.match(report.line, /readiness_blocked=anthropic/)
  assert.match(report.line, /matrix_blocked=anthropic/)
})

test('evaluateRemoteDoctorEvidence returns error for mismatched evidence metadata', () => {
  const report = evaluateRemoteDoctorEvidence({
    readiness: {
      generated_at: '2026-03-29T16:15:47.737Z',
      provider_scope: 'openai,anthropic',
      evidence_suffix: 'remote',
      providers: [
        { provider: 'openai', ready: true },
        { provider: 'anthropic', ready: true },
      ],
      counts: {
        ready: 2,
        blocked: 0,
      },
    },
    matrix: {
      generated_at: '2026-03-29T16:15:47.737Z',
      provider_scope: 'openai',
      evidence_suffix: 'local',
      readiness_evidence: '.sisyphus/evidence/task-15-provider-readiness.json',
      providers: [
        { provider: 'openai', status: 'passed', readiness: 'ready' },
      ],
      counts: {
        passed: 1,
        blocked: 0,
        failed: 0,
      },
    },
    providers: ['openai', 'anthropic'],
    evidenceSuffix: 'remote',
    expectedReadinessEvidenceRef: '.sisyphus/evidence/task-15-provider-readiness-remote.json',
  })

  assert.equal(report.status, 'error')
  assert.equal(report.exitCode, 2)
  assert.match(report.line, /matrix_evidence_suffix_mismatch:local/)
  assert.match(report.line, /matrix_provider_scope_mismatch:openai/)
})

test('loadRemoteDoctorEvidence reports missing and invalid json evidence', async () => {
  const tempDir = await mkdtemp(path.join(os.tmpdir(), 'remote-doctor-'))
  try {
    await writeFile(path.join(tempDir, 'task-15-provider-readiness-remote.json'), '{bad json', 'utf8')
    const evidence = loadRemoteDoctorEvidence(tempDir, 'remote')

    assert.equal(evidence.readiness, null)
    assert.equal(evidence.matrix, null)
    assert.deepEqual(
      evidence.issues.sort(),
      [
        'invalid_readiness_evidence:task-15-provider-readiness-remote.json',
        'missing_matrix_evidence:task-16-provider-matrix-summary-remote.json',
      ]
    )
  } finally {
    await rm(tempDir, { recursive: true, force: true })
  }
})
