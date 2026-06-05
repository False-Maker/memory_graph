import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildRunSourceSummary,
  buildRunSummary,
  buildRunTypeLabel,
  buildRunStatusBadge,
  canRetryRun,
} from './ImportRunHistoryPanel.helpers.js'

test('directory import shows human-readable type and directory path summary', () => {
  const run = {
    run_type: 'directory_import',
    directory_path: '/tmp/memory',
    status: 'succeeded',
    imported: 3,
    attempted: 4,
    failed: 1,
    skipped: 0,
  }

  assert.equal(buildRunTypeLabel(run), '目录导入')
  assert.equal(buildRunSourceSummary(run), '目录: /tmp/memory')
  assert.equal(buildRunSummary(run), 'imported=3 | attempted=4 | failed=1 | skipped=0')
  assert.match(buildRunStatusBadge(run).className, /success/)
})

test('file and conversation imports keep readable labels', () => {
  assert.equal(buildRunTypeLabel({ run_type: 'file_import', filename: 'a.json' }), '文件导入')
  assert.equal(buildRunSourceSummary({ run_type: 'file_import', filename: 'a.json' }), '文件: a.json')

  assert.equal(buildRunTypeLabel({ run_type: 'conversation_import' }), '会话导入')
  assert.equal(
    buildRunSourceSummary({ run_type: 'conversation_import', source: 'data/import/conversations' }),
    '来源: data/import/conversations'
  )
})

test('source operations render source-aware labels and summaries', () => {
  const pushRun = {
    run_type: 'source_push',
    label: 'Project Notes',
    workspace_id: 'workspace-notes',
    summary: {
      matched_files: 3,
      scanned_records: 9,
      created: 2,
      updated: 1,
      conflicts: 0,
    }
  }
  assert.equal(buildRunTypeLabel(pushRun), '同步源推送')
  assert.equal(buildRunSourceSummary(pushRun), '同步源: Project Notes | workspace=workspace-notes')
  assert.equal(buildRunSummary(pushRun), 'matched=3 | scanned=9 | created=2 | updated=1 | conflicts=0')

  const syncRun = {
    run_type: 'source_sync',
    source_id: 'src-1',
    summary: {
      push: { created: 1, updated: 2, conflicts: 0 },
      pull: { processed_changes: 4, written_conflicts: 1 }
    }
  }
  assert.equal(buildRunTypeLabel(syncRun), '同步源双向同步')
  assert.equal(buildRunSourceSummary(syncRun), '同步源 ID: src-1')
  assert.equal(buildRunSummary(syncRun), 'push(created=1, updated=2, conflicts=0) | pull(processed=4, conflicts=1)')
})

test('missing fields are handled safely', () => {
  const run = {}
  assert.equal(buildRunTypeLabel(run), 'unknown')
  assert.equal(buildRunSourceSummary(run), '-')
  assert.equal(buildRunSummary(run), 'imported=0 | attempted=0 | failed=0 | skipped=0')
  assert.match(buildRunStatusBadge(run).className, /neutral/)
  assert.equal(canRetryRun(run), false)
})

test('retry is only enabled for replayable directory imports', () => {
  assert.equal(
    canRetryRun({ id: 'run-1', run_type: 'directory_import', retryable: true, directory_path: '/tmp/memory' }),
    true
  )
  assert.equal(
    canRetryRun({ id: 'run-2', run_type: 'directory_import', retryable: false, directory_path: '/tmp/memory' }),
    false
  )
  assert.equal(
    canRetryRun({ id: 'run-3', run_type: 'file_import', retryable: true, filename: 'payload.json' }),
    false
  )
})
