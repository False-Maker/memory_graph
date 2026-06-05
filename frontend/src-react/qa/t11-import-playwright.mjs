import { spawn } from 'node:child_process'
import { mkdir, rm, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { chromium } from 'playwright'
import {
  buildDirectoryScanResponse,
  buildImportRun,
  createImportRunsStore,
  toImportRunsApiPayload,
} from './t11-import-playwright-helpers.mjs'
import {
  buildBaseUrl,
  findAvailablePort,
  resolvePlaywrightPreviewStartPort,
  runBuildWeb,
  startPreviewServer as startManagedPreviewServer,
  stopPreviewServer as stopManagedPreviewServer,
  waitForManagedPreviewServerReady,
} from './settings-playwright-runtime.mjs'
import {
  launchPlaywrightBrowser,
  writePlaywrightSmokeEvidence,
} from './playwright-smoke-runtime.mjs'

const FRONTEND_ROOT = path.resolve(process.cwd())
const EVIDENCE_DIR = path.resolve(FRONTEND_ROOT, '..', '.sisyphus', 'evidence')

async function waitForImportReady(page) {
  await page.waitForURL('**/inbox', { timeout: 30000 })
  await page.waitForSelector('.import-diagnostics-card', { state: 'visible', timeout: 30000 })
  await page.waitForSelector('.import-tabs', { state: 'visible', timeout: 30000 })
  await page.waitForSelector('.import-card', { state: 'visible', timeout: 30000 })
}

async function runHappyPath(browser, baseUrl) {
  const context = await browser.newContext()
  let scanCalls = 0
  let directoryImportCalls = 0
  let importRunsReadCalls = 0
  let sourcePreviewCalls = 0
  let sourceSaveCalls = 0
  let sourceStatusCalls = 0
  let sourcePushCalls = 0
  let savedSources = []
  let sourceStatusPayload = null

  const importRunsStore = createImportRunsStore([
    buildImportRun({
      id: 'seed-file-run',
      status: 'succeeded',
      run_type: 'file_import',
      source: 'data/import',
      filename: 'seed.json',
      message: 'seed run',
      imported: 1,
      attempted: 1,
      failed: 0,
      skipped: 0,
      started_at: '2026-04-02T09:30:00Z',
      finished_at: '2026-04-02T09:30:10Z',
      created_at: '2026-04-02T09:30:10Z'
    })
  ])

  function buildDiagnosticsPayload() {
    if (savedSources.length === 0) {
      return {
        status: 'healthy',
        generated_at: '2026-04-02T10:00:00Z',
        checks: {
          config: { ok: true },
          provider: { ok: true, current_provider: 'openai', providers: { openai: true }, provider_errors: {}, current_error: null },
          sqlite: { ok: true },
          vector_store: { ok: true, state: { indexed_documents: 4, stored_documents: 4, dimension_mismatch: false } }
        },
        task_chain: {
          status: 'not_configured',
          configured_sources: 0,
          sources: [],
          detail: 'No sync sources configured'
        },
        recent_failures: []
      }
    }

    const activeSource = savedSources[0]
    return {
      status: 'healthy',
      generated_at: '2026-04-02T10:00:00Z',
      checks: {
        config: { ok: true },
        provider: { ok: true, current_provider: 'openai', providers: { openai: true }, provider_errors: {}, current_error: null },
        sqlite: { ok: true },
        vector_store: {
          ok: true,
          state: {
            indexed_documents: sourceStatusPayload?.local_state?.tracked_records ?? 0,
            stored_documents: sourceStatusPayload?.local_state?.tracked_records ?? 0,
            dimension_mismatch: false
          }
        }
      },
      task_chain: {
        status: 'healthy',
        configured_sources: savedSources.length,
        sources: [
          {
            source_id: activeSource.source_id,
            label: activeSource.label,
            source_system: activeSource.source_system,
            workspace_id: activeSource.workspace_id,
            workspace_root: activeSource.workspace_root,
            state_status: 'healthy',
            record_count: sourceStatusPayload?.local_state?.tracked_records ?? 0,
            conflicts: sourceStatusPayload?.local_state?.conflict_records ?? 0,
            deleted_records: sourceStatusPayload?.local_state?.deleted_records ?? 0,
            last_pulled_seq: sourceStatusPayload?.local_state?.last_pulled_seq ?? 0,
            detail: null
          }
        ],
        detail: null
      },
      recent_failures: []
    }
  }

  await context.route('**/api/v1/diagnostics/runtime', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(buildDiagnosticsPayload())
    })
  })

  await context.route('**/api/v1/sync/sources/settings', async (route) => {
    const method = route.request().method()
    if (method === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sources: savedSources })
      })
      return
    }

    if (method === 'POST') {
      sourceSaveCalls += 1
      const payload = route.request().postDataJSON() || {}
      const source = {
        source_id: 'src-1',
        label: payload.label || 'Project Notes',
        source_system: payload.source_system || 'notes',
        workspace_id: payload.workspace_id || 'workspace-notes',
        workspace_root: payload.workspace_root || '/tmp/source-workspace',
        source_paths: payload.source_paths || ['notes/**/*.md'],
        updated_at: '2026-04-02T10:02:00Z'
      }
      savedSources = [source]
      sourceStatusPayload = {
        source_id: source.source_id,
        label: source.label,
        source_system: source.source_system,
        workspace_id: source.workspace_id,
        workspace_root: source.workspace_root,
        source_paths: source.source_paths,
        state_path: '/tmp/source-workspace/.state/memory-graph-sync.json',
        conflicts_dir: '/tmp/source-workspace/.state/conflicts',
        inbox_dir: '/tmp/source-workspace/memory/inbox',
        matched_files: 2,
        local_state: {
          tracked_records: 1,
          deleted_records: 0,
          conflict_records: 0,
          synced_records: 1,
          last_pulled_seq: 0,
          recent_mutation_ids: 0
        },
        remote_state: {
          active_records: 1,
          tombstones: 0,
          conflicts: 0,
          last_change_seq: 1,
          last_server_change_at: '2026-04-02T10:02:00Z'
        }
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(source)
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sources: savedSources })
    })
  })

  await context.route('**/api/v1/sync/sources/preview', async (route) => {
    sourcePreviewCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source_system: 'notes',
        workspace_id: 'workspace-notes',
        workspace_root: '/tmp/source-workspace',
        source_paths: ['notes/**/*.md'],
        matched_files: ['notes/a.md', 'notes/b.md'],
        record_count: 4
      })
    })
  })

  await context.route('**/api/v1/sync/sources/settings/src-1/status', async (route) => {
    sourceStatusCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(sourceStatusPayload)
    })
  })

  await context.route('**/api/v1/sync/sources/settings/src-1/push', async (route) => {
    sourcePushCalls += 1
    importRunsStore.prepend({
      id: 'source-run-1',
      status: 'succeeded',
      run_type: 'source_push',
      source: 'sync/sources/settings/src-1/push',
      source_id: 'src-1',
      workspace_id: 'workspace-notes',
      label: 'Project Notes',
      message: 'source push completed: Project Notes',
      summary: {
        matched_files: 2,
        scanned_records: 4,
        pushed_records: 4,
        restore_candidates: 0,
        created: 2,
        updated: 1,
        noop: 1,
        conflicts: 0,
        rejected: 0,
        marker_updates: 1,
        deleted_remote_records: []
      }
    })
    sourceStatusPayload = {
      ...sourceStatusPayload,
      local_state: {
        tracked_records: 4,
        deleted_records: 0,
        conflict_records: 0,
        synced_records: 4,
        last_pulled_seq: 0,
        recent_mutation_ids: 2
      },
      remote_state: {
        active_records: 4,
        tombstones: 0,
        conflicts: 0,
        last_change_seq: 4,
        last_server_change_at: '2026-04-02T10:05:00Z'
      }
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        source_id: 'src-1',
        label: 'Project Notes',
        source_system: 'notes',
        workspace_id: 'workspace-notes',
        workspace_root: '/tmp/source-workspace',
        source_paths: ['notes/**/*.md'],
        state_path: '/tmp/source-workspace/.state/memory-graph-sync.json',
        conflicts_dir: '/tmp/source-workspace/.state/conflicts',
        summary: {
          matched_files: 2,
          scanned_records: 4,
          pushed_records: 4,
          restore_candidates: 0,
          created: 2,
          updated: 1,
          noop: 1,
          conflicts: 0,
          rejected: 0,
          marker_updates: 1,
          deleted_remote_records: []
        }
      })
    })
  })

  await context.route('**/api/v1/data/import-runs**', async (route) => {
    importRunsReadCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(toImportRunsApiPayload(importRunsStore, route.request().url()))
    })
  })

  await context.route('**/api/v1/data/scan-directory', async (route) => {
    scanCalls += 1
    const payload = route.request().postDataJSON() || {}

    if (payload.directory_path !== '/tmp/inbox-e2e') {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: `unexpected directory path: ${payload.directory_path}` })
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        buildDirectoryScanResponse({
          matchedPaths: ['/tmp/inbox-e2e/chat-a.json', '/tmp/inbox-e2e/chat-b.json'],
          skippedFiles: [{ path: '/tmp/inbox-e2e/ignore.log', reason: 'unsupported extension' }]
        })
      )
    })
  })

  await context.route('**/api/v1/data/import-directory', async (route) => {
    directoryImportCalls += 1
    const payload = route.request().postDataJSON() || {}

    if (payload.directory_path !== '/tmp/inbox-e2e') {
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({ detail: `unexpected directory path: ${payload.directory_path}` })
      })
      return
    }

    const response = {
      status: 'completed',
      message: '目录导入完成：共处理 2 个文件，成功导入 2 条会话记忆。',
      imported: 2,
      attempted: 2,
      failed: 0,
      skipped: 1,
      duplicates_skipped: 0,
      retryable_count: 0,
      retryable_failed_files: []
    }
    importRunsStore.prepend({
      status: 'completed',
      run_type: 'directory_import',
      source: payload.directory_path,
      message: response.message,
      imported: response.imported,
      attempted: response.attempted,
      failed: response.failed,
      skipped: response.skipped,
      started_at: '2026-04-02T10:01:00Z',
      finished_at: '2026-04-02T10:01:20Z'
    })

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(response)
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/inbox`, { waitUntil: 'networkidle' })
  await waitForImportReady(page)
  await page.waitForSelector('text=导入/同步状态', { timeout: 30000 })
  await page.waitForSelector('text=当前没有配置外部记忆源；不影响文件、目录和会话导入。', { timeout: 30000 })
  await page.waitForSelector('button[data-tab="directory"]', { timeout: 30000 })

  await page.locator('[data-tab="directory"]').click()
  await page.waitForSelector('section[aria-label="Recent import runs"]', { state: 'visible', timeout: 30000 })
  await page.fill('#import-directory-path-input', '/tmp/inbox-e2e')
  await page.click('button:has-text("预扫描目录")')
  await page.waitForSelector('text=matched=2', { timeout: 30000 })
  await page.waitForSelector('text=skipped=1', { timeout: 30000 })
  await page.click('button.import-submit')
  await page.waitForSelector('.directory-import-result', { timeout: 30000 })
  await page.waitForSelector('text=目录导入结果', { timeout: 30000 })
  await page.waitForSelector('text=目录导入完成：共处理 2 个文件，成功导入 2 条会话记忆。', { timeout: 30000 })
  await page.waitForSelector('text=目录批量导入完成：/tmp/inbox-e2e', { timeout: 30000 })
  await page.waitForSelector('text=imported=2 | attempted=2 | failed=0 | skipped=1', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-11-import-file.png'), fullPage: true })

  if (scanCalls < 1) {
    throw new Error(`Expected at least 1 /data/scan-directory call, got ${scanCalls}`)
  }
  if (directoryImportCalls < 1) {
    throw new Error(`Expected at least 1 /data/import-directory call, got ${directoryImportCalls}`)
  }
  if (importRunsReadCalls < 2) {
    throw new Error(`Expected at least 2 /data/import-runs calls, got ${importRunsReadCalls}`)
  }
  if (importRunsStore.size() < 2) {
    throw new Error('Expected import run store to include new directory run')
  }

  await page.locator('[data-tab="source"]').click()
  await page.fill('#import-source-label', 'Project Notes')
  await page.fill('#import-source-system', 'notes')
  await page.fill('#import-source-workspace-id', 'workspace-notes')
  await page.fill('#import-source-workspace-root', '/tmp/source-workspace')
  await page.fill('#import-source-paths', 'notes/**/*.md')
  await page.click('button:has-text("预览当前源")')
  await page.waitForSelector('text=同步源预览完成：notes', { timeout: 30000 })
  await page.waitForSelector('text=匹配 2 个文件，预计解析 4 条记录', { timeout: 30000 })
  await page.click('button.import-submit')
  await page.waitForSelector('text=同步源已保存：Project Notes', { timeout: 30000 })
  await page.waitForSelector('text=核心运行依赖健康，导入/同步链路当前可信。', { timeout: 30000 })
  await page.waitForSelector('text=tracked：1', { timeout: 30000 })
  await page.click('button:has-text("推送当前源")')
  await page.waitForSelector('text=同步源执行完成：Project Notes', { timeout: 30000 })
  await page.waitForSelector('text=matched=2 | scanned=4 | created=2 | updated=1 | conflicts=0', { timeout: 30000 })
  await page.waitForSelector('text=同步源推送', { timeout: 30000 })
  await page.waitForSelector('text=同步源: Project Notes | workspace=workspace-notes', { timeout: 30000 })
  await page.waitForSelector('text=matched=2 | scanned=4 | created=2 | updated=1 | conflicts=0', { timeout: 30000 })

  if (sourcePreviewCalls < 1) {
    throw new Error(`Expected at least 1 /sync/sources/preview call, got ${sourcePreviewCalls}`)
  }
  if (sourceSaveCalls < 1) {
    throw new Error(`Expected at least 1 source save call, got ${sourceSaveCalls}`)
  }
  if (sourceStatusCalls < 1) {
    throw new Error(`Expected at least 1 source status call, got ${sourceStatusCalls}`)
  }
  if (sourcePushCalls < 1) {
    throw new Error(`Expected at least 1 source push call, got ${sourcePushCalls}`)
  }

  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-11-import-directory.png'), fullPage: true })
  await context.close()

  return {
    scenario: 'happy_path',
    status: 'passed',
    artifacts: ['task-11-import-file.png', 'task-11-import-directory.png'],
  }
}

async function runFailurePath(browser, baseUrl) {
  const context = await browser.newContext()
  const importRunsStore = createImportRunsStore([])

  await context.route('**/api/v1/diagnostics/runtime', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        status: 'healthy',
        generated_at: '2026-04-02T10:10:00Z',
        checks: {
          config: { ok: true },
          provider: { ok: true, current_provider: 'openai', providers: { openai: true }, provider_errors: {}, current_error: null },
          sqlite: { ok: true },
          vector_store: { ok: true, state: { indexed_documents: 0, stored_documents: 0, dimension_mismatch: false } }
        },
        task_chain: {
          status: 'not_configured',
          configured_sources: 0,
          sources: [],
          detail: null
        },
        recent_failures: []
      })
    })
  })

  await context.route('**/api/v1/sync/sources/settings', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ sources: [] })
    })
  })

  await context.route('**/api/v1/data/import-runs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(toImportRunsApiPayload(importRunsStore, route.request().url()))
    })
  })

  await context.route('**/api/v1/data/scan-directory', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(
        buildDirectoryScanResponse({
          matchedPaths: ['/tmp/inbox-fail/chat-a.json'],
          skippedFiles: []
        })
      )
    })
  })

  await context.route('**/api/v1/data/import-directory', async (route) => {
    importRunsStore.prepend({
      status: 'failed',
      run_type: 'directory_import',
      source: '/tmp/inbox-fail',
      imported: 0,
      attempted: 1,
      failed: 1,
      skipped: 0,
      error: 'invalid import payload'
    })
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'invalid import payload' })
    })
  })

  const page = await context.newPage()
  await page.goto(`${baseUrl}/inbox`, { waitUntil: 'networkidle' })
  await waitForImportReady(page)
  await page.locator('[data-tab="directory"]').click()
  await page.fill('#import-directory-path-input', '/tmp/inbox-fail')
  await page.click('button:has-text("预扫描目录")')
  await page.waitForSelector('text=matched=1', { timeout: 30000 })
  await page.click('button.import-submit')
  await page.waitForSelector('.import-result--error', { timeout: 30000 })
  await page.waitForSelector('text=invalid import payload', { timeout: 30000 })
  await page.waitForSelector('text=导入失败', { timeout: 30000 })
  await page.screenshot({ path: path.join(EVIDENCE_DIR, 'task-11-import-invalid.png'), fullPage: true })

  await context.close()

  return {
    scenario: 'failure_path',
    status: 'passed',
    artifacts: ['task-11-import-invalid.png'],
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  const previewLogPath = path.join(EVIDENCE_DIR, 'task-11-preview.log')
  await Promise.all([
    'task-11-import-summary.txt',
    'task-11-import-summary.json',
    'task-11-import-error.txt',
    'task-11-import-file.png',
    'task-11-import-directory.png',
    'task-11-import-invalid.png',
    'task-11-preview.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb()
  const previewPort = await findAvailablePort(resolvePlaywrightPreviewStartPort('t11', 'T11_PREVIEW_PORT'))
  const baseUrl = buildBaseUrl(previewPort)

  const previewServer = startManagedPreviewServer({
    frontendRoot: FRONTEND_ROOT,
    previewLogPath,
    port: previewPort,
  })
  try {
    await waitForManagedPreviewServerReady(previewServer, `${baseUrl}/`)

    const browser = await launchPlaywrightBrowser(chromium, FRONTEND_ROOT)
    try {
      const results = []
      results.push(await runHappyPath(browser, baseUrl))
      results.push(await runFailurePath(browser, baseUrl))

      const generatedAt = new Date().toISOString()
      await writePlaywrightSmokeEvidence({
        evidenceDir: EVIDENCE_DIR,
        summaryFileName: 'task-11-import-summary.txt',
        jsonFileName: 'task-11-import-summary.json',
        generatedAt,
        status: 'passed',
        baseUrl,
        results,
        extraArtifacts: ['task-11-preview.log'],
      })
    } finally {
      await browser.close()
    }
  } finally {
    await stopManagedPreviewServer(previewServer.child)
    await previewServer.flushLog()
  }

  process.stdout.write('T11 import Playwright scenarios completed.\n')
}

main().catch(async (error) => {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await writeFile(path.join(EVIDENCE_DIR, 'task-11-import-error.txt'), `${error.stack || error.message}\n`, 'utf8')
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
