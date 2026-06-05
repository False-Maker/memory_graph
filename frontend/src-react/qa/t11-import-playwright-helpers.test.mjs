import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDirectoryScanResponse,
  buildImportRun,
  createImportRunsStore,
  toImportRunsApiPayload
} from './t11-import-playwright-helpers.mjs'

test('buildDirectoryScanResponse maps matched and skipped files', () => {
  const response = buildDirectoryScanResponse({
    matchedPaths: ['/tmp/a.json', '/tmp/b.json'],
    skippedFiles: [{ path: '/tmp/c.log', reason: 'unsupported extension' }]
  })

  assert.equal(response.total_files, 3)
  assert.equal(response.conversation_files.length, 2)
  assert.equal(response.skipped_files.length, 1)
  assert.equal(response.skipped_files[0].reason, 'unsupported extension')
})

test('createImportRunsStore prepends newest run and respects limit', () => {
  const store = createImportRunsStore([
    buildImportRun({ id: 'r1', run_type: 'file_import', imported: 1, attempted: 1 })
  ])

  store.prepend({ id: 'r2', run_type: 'directory_import', imported: 2, attempted: 2 })
  const listed = store.list(2)

  assert.equal(listed.length, 2)
  assert.equal(listed[0].id, 'r2')
  assert.equal(listed[0].run_type, 'directory_import')
  assert.equal(listed[1].id, 'r1')
})

test('buildImportRun keeps source-operation fields', () => {
  const run = buildImportRun({
    id: 'src-run-1',
    run_type: 'source_push',
    source_id: 'src-1',
    workspace_id: 'workspace-notes',
    label: 'Project Notes',
    summary: { matched_files: 2, created: 1 }
  })

  assert.equal(run.source_id, 'src-1')
  assert.equal(run.workspace_id, 'workspace-notes')
  assert.equal(run.label, 'Project Notes')
  assert.deepEqual(run.summary, { matched_files: 2, created: 1 })
})

test('toImportRunsApiPayload parses limit query parameter', () => {
  const store = createImportRunsStore([
    buildImportRun({ id: 'r1' }),
    buildImportRun({ id: 'r2' }),
    buildImportRun({ id: 'r3' })
  ])

  const payload = toImportRunsApiPayload(store, 'http://localhost:4173/api/v1/data/import-runs?limit=1')

  assert.equal(payload.success, true)
  assert.equal(payload.runs.length, 1)
})
