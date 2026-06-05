import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildSettingsSmokeMatrixSummary,
  buildSettingsSmokeTaskSummary,
  extractSettingsSmokeSummaryField,
  getSettingsSmokeMatrixEvidencePaths,
  getSettingsSmokeMatrixLogPath,
  getSettingsSmokeTask,
  getSettingsSmokeTaskEvidencePaths,
  listSettingsSmokeTasks,
} from './t21-settings-smoke-matrix-helpers.mjs'

test('settings smoke task catalog stays unique and complete', () => {
  const tasks = listSettingsSmokeTasks()

  assert.deepEqual(
    tasks.map((task) => task.taskId),
    ['t12', 't19', 't20']
  )
  assert.equal(new Set(tasks.map((task) => task.npmScript)).size, tasks.length)
  assert.ok(getSettingsSmokeTask('t12'))
  assert.equal(getSettingsSmokeTask('missing'), null)
})

test('settings smoke evidence paths use stable filenames', () => {
  const evidenceDir = '/tmp/evidence'

  assert.deepEqual(getSettingsSmokeTaskEvidencePaths(evidenceDir, 't12'), {
    summary: '/tmp/evidence/task-12-settings-summary.txt',
    json: '/tmp/evidence/task-12-settings-summary.json',
  })
  assert.equal(
    getSettingsSmokeMatrixLogPath(evidenceDir, 't20'),
    '/tmp/evidence/task-21-settings-smoke-matrix-t20.log'
  )
  assert.deepEqual(getSettingsSmokeMatrixEvidencePaths(evidenceDir), {
    summary: '/tmp/evidence/task-21-settings-smoke-matrix-summary.txt',
    json: '/tmp/evidence/task-21-settings-smoke-matrix-summary.json',
  })
})

test('settings smoke task summary keeps core fields', () => {
  const summary = buildSettingsSmokeTaskSummary({
    taskId: 't19',
    status: 'passed',
    generatedAt: '2026-04-03T13:10:00.000Z',
    exitCode: 0,
    scenarios: ['export_happy_path', 'restore_dry_run_failure_path'],
    artifacts: ['task-19-settings-recovery.png', 'task-19-settings-recovery-error.png'],
    notes: 'dry-run only',
  })

  assert.equal(extractSettingsSmokeSummaryField(summary, 'task'), 't19')
  assert.equal(extractSettingsSmokeSummaryField(summary, 'status'), 'passed')
  assert.equal(extractSettingsSmokeSummaryField(summary, 'scenario_count'), '2')
  assert.equal(extractSettingsSmokeSummaryField(summary, 'artifact_count'), '2')
  assert.equal(extractSettingsSmokeSummaryField(summary, 'notes'), 'dry-run only')
})

test('settings smoke matrix summary formats rows and counters', () => {
  assert.equal(
    buildSettingsSmokeMatrixSummary(
      [
        {
          taskId: 't12',
          label: 'settings-core',
          status: 'passed',
          reason: '',
          exitCode: 0,
          command: 'npm --prefix frontend run qa:settings-playwright:t12',
          evidence: '.sisyphus/evidence/task-12-settings-summary.txt',
          jsonEvidence: '.sisyphus/evidence/task-12-settings-summary.json',
          log: '.sisyphus/evidence/task-21-settings-smoke-matrix-t12.log',
          summaryExcerpt: 'status=passed | artifact_count=4',
        },
        {
          taskId: 't20',
          label: 'settings-reindex',
          status: 'failed',
          reason: 'reindex service unavailable',
          exitCode: 1,
          command: 'npm --prefix frontend run qa:settings-playwright:t20',
          evidence: '.sisyphus/evidence/task-20-settings-reindex-summary.txt',
          jsonEvidence: '.sisyphus/evidence/task-20-settings-reindex-summary.json',
          log: '.sisyphus/evidence/task-21-settings-smoke-matrix-t20.log',
          summaryExcerpt: 'status=failed | error=reindex service unavailable',
        },
      ],
      {
        generatedAt: '2026-04-03T15:00:00.000Z',
        source: 'qa:settings-playwright',
        taskScope: 't12,t19,t20',
      }
    ),
    [
      'generated_at=2026-04-03T15:00:00.000Z',
      'source=qa:settings-playwright',
      'task_scope=t12,t19,t20',
      '',
      'task=t12',
      'label=settings-core',
      'status=passed',
      'reason=',
      'exit_code=0',
      'command=npm --prefix frontend run qa:settings-playwright:t12',
      'evidence=.sisyphus/evidence/task-12-settings-summary.txt',
      'json_evidence=.sisyphus/evidence/task-12-settings-summary.json',
      'log=.sisyphus/evidence/task-21-settings-smoke-matrix-t12.log',
      'summary_excerpt=status=passed | artifact_count=4',
      '',
      'task=t20',
      'label=settings-reindex',
      'status=failed',
      'reason=reindex service unavailable',
      'exit_code=1',
      'command=npm --prefix frontend run qa:settings-playwright:t20',
      'evidence=.sisyphus/evidence/task-20-settings-reindex-summary.txt',
      'json_evidence=.sisyphus/evidence/task-20-settings-reindex-summary.json',
      'log=.sisyphus/evidence/task-21-settings-smoke-matrix-t20.log',
      'summary_excerpt=status=failed | error=reindex service unavailable',
      '',
      'passed_count=1',
      'blocked_count=0',
      'failed_count=1',
      '',
    ].join('\n')
  )
})
