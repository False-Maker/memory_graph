import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { chromium } from 'playwright'

import {
  buildBaseUrl,
  findAvailablePort,
  runBuildWeb,
  stopPreviewServer,
} from './settings-playwright-runtime.mjs'
import {
  assertSmoke,
  buildSmokeBrowserEnv,
  requestJson,
  startBackendService,
  waitForStatus,
  writeTempSettingsConfig,
} from './focused-real-smoke-runtime.mjs'
import { runSeedFixture } from './search-real-smoke-fixtures.mjs'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

function buildMemoryItemSelector(memoryId) {
  return `[data-testid="${MEMORIES_SMOKE_TEST_IDS.item}"][data-memory-id="${memoryId}"]`
}

async function listMemories(backendBaseUrl, status) {
  const response = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=${status}`)
  assertSmoke(response.statusCode === 200, `GET /memories?status=${status} failed: ${response.raw}`)
  return response
}

async function inspectHttpBaseline({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const activeBefore = await listMemories(backendBaseUrl, 'active')
  const archivedBefore = await listMemories(backendBaseUrl, 'archived')
  assertSmoke(activeBefore.json?.total === 19, `Expected 19 active memories before mutations, got ${activeBefore.json?.total}`)
  assertSmoke(archivedBefore.json?.total === 4, `Expected 4 archived memories before mutations, got ${archivedBefore.json?.total}`)

  const archiveTarget = activeBefore.json?.memories?.[0]
  const deleteTarget = activeBefore.json?.memories?.find((memory) => memory?.id && memory.id !== archiveTarget?.id)
  assertSmoke(Boolean(archiveTarget?.id), 'Missing archive target from active memories payload')
  assertSmoke(Boolean(deleteTarget?.id), 'Missing delete target from active memories payload')

  return {
    health,
    activeBefore,
    archivedBefore,
    archiveTargetId: archiveTarget.id,
    deleteTargetId: deleteTarget.id,
  }
}

async function runBrowserFlow({ backendBaseUrl, archiveTargetId, deleteTargetId }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const context = await browser.newContext()
    await context.addInitScript(() => {
      window.confirm = () => true
    })

    const page = await context.newPage()
    await page.goto(`${backendBaseUrl}/memories`, { waitUntil: 'networkidle' })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.list).waitFor({ timeout: 30000 })

    const archiveItem = page.locator(buildMemoryItemSelector(archiveTargetId))
    const deleteItem = page.locator(buildMemoryItemSelector(deleteTargetId))

    await archiveItem.waitFor({ state: 'visible', timeout: 30000 })
    const archiveResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/memories/${archiveTargetId}/archive`)
        && response.request().method() === 'POST'
    )
    await archiveItem.getByTestId(MEMORIES_SMOKE_TEST_IDS.itemArchiveButton).click()
    const archiveResponse = await archiveResponsePromise
    const archivePayload = await archiveResponse.json()
    assertSmoke(archiveResponse.status() === 200, `Archive request returned ${archiveResponse.status()}`)
    assertSmoke(archivePayload?.archived === true, 'Archive payload did not set archived=true')
    await page.waitForSelector('text=记忆已归档', { timeout: 30000 })
    await archiveItem.waitFor({ state: 'detached', timeout: 30000 })
    const activeAfterArchive = await listMemories(backendBaseUrl, 'active')
    const archivedAfterArchive = await listMemories(backendBaseUrl, 'archived')
    assertSmoke(activeAfterArchive.json?.total === 18, `Expected 18 active memories after archive, got ${activeAfterArchive.json?.total}`)
    assertSmoke(archivedAfterArchive.json?.total === 5, `Expected 5 archived memories after archive, got ${archivedAfterArchive.json?.total}`)
    assertSmoke(
      !activeAfterArchive.json?.memories?.some((memory) => memory.id === archiveTargetId),
      'Archived memory still appeared in active list after archive'
    )
    assertSmoke(
      archivedAfterArchive.json?.memories?.some((memory) => memory.id === archiveTargetId),
      'Archived memory did not appear in archived list after archive'
    )

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.archivedFilter).click()
    await archiveItem.waitFor({ state: 'visible', timeout: 30000 })
    const unarchiveResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/memories/${archiveTargetId}/unarchive`)
        && response.request().method() === 'POST'
    )
    await archiveItem.getByTestId(MEMORIES_SMOKE_TEST_IDS.itemArchiveButton).click()
    const unarchiveResponse = await unarchiveResponsePromise
    const unarchivePayload = await unarchiveResponse.json()
    assertSmoke(unarchiveResponse.status() === 200, `Unarchive request returned ${unarchiveResponse.status()}`)
    assertSmoke(unarchivePayload?.archived === false, 'Unarchive payload did not set archived=false')
    await page.waitForSelector('text=记忆已取消归档', { timeout: 30000 })
    await archiveItem.waitFor({ state: 'detached', timeout: 30000 })
    const activeAfterUnarchive = await listMemories(backendBaseUrl, 'active')
    const archivedAfterUnarchive = await listMemories(backendBaseUrl, 'archived')
    assertSmoke(activeAfterUnarchive.json?.total === 19, `Expected 19 active memories after unarchive, got ${activeAfterUnarchive.json?.total}`)
    assertSmoke(archivedAfterUnarchive.json?.total === 4, `Expected 4 archived memories after unarchive, got ${archivedAfterUnarchive.json?.total}`)
    assertSmoke(
      activeAfterUnarchive.json?.memories?.some((memory) => memory.id === archiveTargetId),
      'Unarchived memory did not return to active list'
    )

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.activeFilter).click()
    await archiveItem.waitFor({ state: 'visible', timeout: 30000 })
    await deleteItem.waitFor({ state: 'visible', timeout: 30000 })
    const deleteResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/memories/${deleteTargetId}`)
        && response.request().method() === 'DELETE'
    )
    await deleteItem.getByTestId(MEMORIES_SMOKE_TEST_IDS.itemDeleteButton).click()
    const deleteResponse = await deleteResponsePromise
    const deletePayload = await deleteResponse.json()
    assertSmoke(deleteResponse.status() === 200, `Delete request returned ${deleteResponse.status()}`)
    assertSmoke(deletePayload?.sync_status === 'deleted', 'Delete payload did not return sync_status=deleted')
    await page.waitForSelector('text=记忆已删除', { timeout: 30000 })
    await deleteItem.waitFor({ state: 'detached', timeout: 30000 })
    const activeAfterDelete = await listMemories(backendBaseUrl, 'active')
    const archivedAfterDelete = await listMemories(backendBaseUrl, 'archived')
    const allAfterDelete = await listMemories(backendBaseUrl, 'all')
    const detailAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories/${deleteTargetId}`)
    assertSmoke(activeAfterDelete.json?.total === 18, `Expected 18 active memories after delete, got ${activeAfterDelete.json?.total}`)
    assertSmoke(archivedAfterDelete.json?.total === 4, `Expected 4 archived memories after delete, got ${archivedAfterDelete.json?.total}`)
    assertSmoke(allAfterDelete.json?.total === 22, `Expected 22 total memories after delete, got ${allAfterDelete.json?.total}`)
    assertSmoke(detailAfterDelete.statusCode === 404, `Expected deleted memory detail 404, got ${detailAfterDelete.statusCode}`)
    assertSmoke(
      !activeAfterDelete.json?.memories?.some((memory) => memory.id === deleteTargetId),
      'Deleted memory still appeared in active list after delete'
    )

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-34-memories-write-real.png'),
      fullPage: true,
    })

    const finalUrl = page.url()
    await context.close()

    return {
      archivePayload,
      activeAfterArchive,
      archivedAfterArchive,
      unarchivePayload,
      activeAfterUnarchive,
      archivedAfterUnarchive,
      deletePayload,
      activeAfterDelete,
      archivedAfterDelete,
      allAfterDelete,
      detailAfterDelete,
      finalUrl,
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-34-memories-write-real-summary.txt',
    'task-34-memories-write-real-summary.json',
    'task-34-memories-write-real-http.json',
    'task-34-memories-write-real-seed.json',
    'task-34-memories-write-real.png',
    'task-34-memories-write-real-error.txt',
    'task-34-memories-write-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-memories-write-real-'))
  const backendPort = await findAvailablePort(Number(process.env.T34_BACKEND_PORT ?? '38340'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-34-memories-write-real-seed.json')

  await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'memories_list',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-34-memories-write-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await inspectHttpBaseline({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({
      backendBaseUrl,
      archiveTargetId: httpEvidence.archiveTargetId,
      deleteTargetId: httpEvidence.deleteTargetId,
    })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:memories:write-path',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      profile: 'memories_list',
      archive_target_id: httpEvidence.archiveTargetId,
      delete_target_id: httpEvidence.deleteTargetId,
      active_before: httpEvidence.activeBefore.json?.total,
      archived_before: httpEvidence.archivedBefore.json?.total,
      active_after_archive: browserEvidence.activeAfterArchive.json?.total,
      archived_after_archive: browserEvidence.archivedAfterArchive.json?.total,
      active_after_unarchive: browserEvidence.activeAfterUnarchive.json?.total,
      archived_after_unarchive: browserEvidence.archivedAfterUnarchive.json?.total,
      active_after_delete: browserEvidence.activeAfterDelete.json?.total,
      archived_after_delete: browserEvidence.archivedAfterDelete.json?.total,
      total_after_delete: browserEvidence.allAfterDelete.json?.total,
      detail_status_after_delete: browserEvidence.detailAfterDelete.statusCode,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-34-memories-write-real.png',
      backend_log: '.sisyphus/evidence/task-34-memories-write-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-34-memories-write-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `profile=${summaryPayload.profile}`,
      `archive_target_id=${summaryPayload.archive_target_id}`,
      `delete_target_id=${summaryPayload.delete_target_id}`,
      `active_before=${summaryPayload.active_before}`,
      `archived_before=${summaryPayload.archived_before}`,
      `active_after_archive=${summaryPayload.active_after_archive}`,
      `archived_after_archive=${summaryPayload.archived_after_archive}`,
      `active_after_unarchive=${summaryPayload.active_after_unarchive}`,
      `archived_after_unarchive=${summaryPayload.archived_after_unarchive}`,
      `active_after_delete=${summaryPayload.active_after_delete}`,
      `archived_after_delete=${summaryPayload.archived_after_delete}`,
      `total_after_delete=${summaryPayload.total_after_delete}`,
      `detail_status_after_delete=${summaryPayload.detail_status_after_delete}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-34-memories-write-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-34-memories-write-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-34-memories-write-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        active_before: httpEvidence.activeBefore.json,
        archived_before: httpEvidence.archivedBefore.json,
        archive: browserEvidence.archivePayload,
        active_after_archive: browserEvidence.activeAfterArchive.json,
        archived_after_archive: browserEvidence.archivedAfterArchive.json,
        unarchive: browserEvidence.unarchivePayload,
        active_after_unarchive: browserEvidence.activeAfterUnarchive.json,
        archived_after_unarchive: browserEvidence.archivedAfterUnarchive.json,
        delete: browserEvidence.deletePayload,
        active_after_delete: browserEvidence.activeAfterDelete.json,
        archived_after_delete: browserEvidence.archivedAfterDelete.json,
        all_after_delete: browserEvidence.allAfterDelete.json,
        detail_after_delete: {
          status_code: browserEvidence.detailAfterDelete.statusCode,
          body: browserEvidence.detailAfterDelete.json,
        },
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-34-memories-write-real-error.txt'),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    await stopPreviewServer(backend.child)
    await backend.flushLog()
    await rm(workspaceRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
