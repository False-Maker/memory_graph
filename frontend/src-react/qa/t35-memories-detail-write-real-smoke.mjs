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
import { runSeedFixture, startFakeOllamaServer } from './search-real-smoke-fixtures.mjs'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function waitForDetailLifecycle(page, expectedValue, timeoutMs = 30000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    const currentValue = await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailLifecycleValue).textContent().catch(() => null)
    if (currentValue?.trim() === expectedValue) {
      return
    }
    await page.waitForTimeout(200)
  }
  throw new Error(`Timed out waiting for detail lifecycle=${expectedValue}`)
}

async function listMemories(backendBaseUrl, status) {
  const response = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=${status}`)
  assertSmoke(response.statusCode === 200, `GET /memories?status=${status} failed: ${response.raw}`)
  return response
}

async function verifyHttpBaseline({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const memoryDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
  assertSmoke(memoryDetail.statusCode === 200, `GET /memories/{id} failed: ${memoryDetail.raw}`)
  assertSmoke(memoryDetail.json?.metadata?.archived !== true, 'Seeded detail should start as active')

  const memoryContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
  assertSmoke(memoryContext.statusCode === 200, `GET /memories/{id}/context failed: ${memoryContext.raw}`)
  assertSmoke(memoryContext.json?.total_entities === 2, `Expected 2 context entities, got ${memoryContext.json?.total_entities}`)
  assertSmoke(memoryContext.json?.total_communities === 1, `Expected 1 context community, got ${memoryContext.json?.total_communities}`)

  const activeBefore = await listMemories(backendBaseUrl, 'active')
  const archivedBefore = await listMemories(backendBaseUrl, 'archived')
  const allBefore = await listMemories(backendBaseUrl, 'all')
  assertSmoke(activeBefore.json?.total === 1, `Expected 1 active memory before mutations, got ${activeBefore.json?.total}`)
  assertSmoke(archivedBefore.json?.total === 0, `Expected 0 archived memories before mutations, got ${archivedBefore.json?.total}`)
  assertSmoke(allBefore.json?.total === 1, `Expected 1 total memory before mutations, got ${allBefore.json?.total}`)

  return {
    health,
    memoryDetail,
    memoryContext,
    activeBefore,
    archivedBefore,
    allBefore,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const context = await browser.newContext()
    await context.addInitScript(() => {
      window.confirm = () => true
    })

    const page = await context.newPage()
    await page.goto(`${backendBaseUrl}/memories/${seedPayload.memory_id}`, { waitUntil: 'networkidle' })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communitiesSection).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.entitiesSection).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailLifecycleValue).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Alice', { timeout: 30000 })
    await page.waitForSelector('text=Launch Checklist', { timeout: 30000 })

    const initialLifecycle = await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailLifecycleValue).textContent()
    assertSmoke(initialLifecycle?.trim() === 'active', `Expected initial lifecycle active, got ${initialLifecycle}`)

    const archiveResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/memories/${seedPayload.memory_id}/archive`)
        && response.request().method() === 'POST'
    )
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).click()
    const archiveResponse = await archiveResponsePromise
    const archivePayload = await archiveResponse.json()
    assertSmoke(archiveResponse.status() === 200, `Archive detail request returned ${archiveResponse.status()}`)
    assertSmoke(archivePayload?.archived === true, 'Archive payload did not set archived=true')
    await page.waitForSelector('text=记忆已归档', { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailLifecycleValue).waitFor({ timeout: 30000 })
    await waitForDetailLifecycle(page, 'archived')

    const detailAfterArchive = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    const activeAfterArchive = await listMemories(backendBaseUrl, 'active')
    const archivedAfterArchive = await listMemories(backendBaseUrl, 'archived')
    assertSmoke(detailAfterArchive.statusCode === 200, `Expected archived detail 200, got ${detailAfterArchive.statusCode}`)
    assertSmoke(detailAfterArchive.json?.metadata?.archived === true, 'Detail metadata did not persist archived=true')
    assertSmoke(activeAfterArchive.json?.total === 0, `Expected 0 active memories after archive, got ${activeAfterArchive.json?.total}`)
    assertSmoke(archivedAfterArchive.json?.total === 1, `Expected 1 archived memory after archive, got ${archivedAfterArchive.json?.total}`)

    const unarchiveResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/memories/${seedPayload.memory_id}/unarchive`)
        && response.request().method() === 'POST'
    )
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).click()
    const unarchiveResponse = await unarchiveResponsePromise
    const unarchivePayload = await unarchiveResponse.json()
    assertSmoke(unarchiveResponse.status() === 200, `Unarchive detail request returned ${unarchiveResponse.status()}`)
    assertSmoke(unarchivePayload?.archived === false, 'Unarchive payload did not set archived=false')
    await page.waitForSelector('text=记忆已取消归档', { timeout: 30000 })
    await waitForDetailLifecycle(page, 'active')

    const detailAfterUnarchive = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    const activeAfterUnarchive = await listMemories(backendBaseUrl, 'active')
    const archivedAfterUnarchive = await listMemories(backendBaseUrl, 'archived')
    assertSmoke(detailAfterUnarchive.statusCode === 200, `Expected unarchived detail 200, got ${detailAfterUnarchive.statusCode}`)
    assertSmoke(detailAfterUnarchive.json?.metadata?.archived !== true, 'Detail metadata still reported archived after unarchive')
    assertSmoke(activeAfterUnarchive.json?.total === 1, `Expected 1 active memory after unarchive, got ${activeAfterUnarchive.json?.total}`)
    assertSmoke(archivedAfterUnarchive.json?.total === 0, `Expected 0 archived memories after unarchive, got ${archivedAfterUnarchive.json?.total}`)

    const deleteResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/memories/${seedPayload.memory_id}`)
        && response.request().method() === 'DELETE'
    )
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).click()
    const deleteResponse = await deleteResponsePromise
    const deletePayload = await deleteResponse.json()
    assertSmoke(deleteResponse.status() === 200, `Delete detail request returned ${deleteResponse.status()}`)
    assertSmoke(deletePayload?.sync_status === 'deleted', 'Delete payload did not return sync_status=deleted')
    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.waitForSelector('text=记忆已删除', { timeout: 30000 })

    const detailPanelVisible = await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).isVisible().catch(() => false)
    assertSmoke(detailPanelVisible === false, 'Detail panel should be closed after deleting current memory')

    const detailAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    const contextAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
    const activeAfterDelete = await listMemories(backendBaseUrl, 'active')
    const archivedAfterDelete = await listMemories(backendBaseUrl, 'archived')
    const allAfterDelete = await listMemories(backendBaseUrl, 'all')
    assertSmoke(detailAfterDelete.statusCode === 404, `Expected deleted detail 404, got ${detailAfterDelete.statusCode}`)
    assertSmoke(contextAfterDelete.statusCode === 404, `Expected deleted context 404, got ${contextAfterDelete.statusCode}`)
    assertSmoke(activeAfterDelete.json?.total === 0, `Expected 0 active memories after delete, got ${activeAfterDelete.json?.total}`)
    assertSmoke(archivedAfterDelete.json?.total === 0, `Expected 0 archived memories after delete, got ${archivedAfterDelete.json?.total}`)
    assertSmoke(allAfterDelete.json?.total === 0, `Expected 0 total memories after delete, got ${allAfterDelete.json?.total}`)

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-35-memories-detail-write-real.png'),
      fullPage: true,
    })

    const finalUrl = page.url()
    await context.close()

    return {
      archivePayload,
      detailAfterArchive,
      activeAfterArchive,
      archivedAfterArchive,
      unarchivePayload,
      detailAfterUnarchive,
      activeAfterUnarchive,
      archivedAfterUnarchive,
      deletePayload,
      detailAfterDelete,
      contextAfterDelete,
      activeAfterDelete,
      archivedAfterDelete,
      allAfterDelete,
      finalUrl,
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-35-memories-detail-write-real-summary.txt',
    'task-35-memories-detail-write-real-summary.json',
    'task-35-memories-detail-write-real-http.json',
    'task-35-memories-detail-write-real-seed.json',
    'task-35-memories-detail-write-real.png',
    'task-35-memories-detail-write-real-error.txt',
    'task-35-memories-detail-write-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-memories-detail-write-'))
  const backendPort = await findAvailablePort(Number(process.env.T35_BACKEND_PORT ?? '38350'))
  const ollamaPort = await findAvailablePort(Number(process.env.T35_OLLAMA_PORT ?? '38351'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-35-memories-detail-write-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-35-memories-detail-write-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpBaseline({ backendBaseUrl, seedPayload })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, seedPayload })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:memories:detail:write-path',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      memory_id: seedPayload.memory_id,
      community_id: seedPayload.community_id,
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
      context_status_after_delete: browserEvidence.contextAfterDelete.statusCode,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-35-memories-detail-write-real.png',
      backend_log: '.sisyphus/evidence/task-35-memories-detail-write-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-35-memories-detail-write-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `memory_id=${summaryPayload.memory_id}`,
      `community_id=${summaryPayload.community_id}`,
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
      `context_status_after_delete=${summaryPayload.context_status_after_delete}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-35-memories-detail-write-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-35-memories-detail-write-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-35-memories-detail-write-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        memory_detail_before: httpEvidence.memoryDetail.json,
        memory_context_before: httpEvidence.memoryContext.json,
        active_before: httpEvidence.activeBefore.json,
        archived_before: httpEvidence.archivedBefore.json,
        all_before: httpEvidence.allBefore.json,
        archive: browserEvidence.archivePayload,
        detail_after_archive: browserEvidence.detailAfterArchive.json,
        active_after_archive: browserEvidence.activeAfterArchive.json,
        archived_after_archive: browserEvidence.archivedAfterArchive.json,
        unarchive: browserEvidence.unarchivePayload,
        detail_after_unarchive: browserEvidence.detailAfterUnarchive.json,
        active_after_unarchive: browserEvidence.activeAfterUnarchive.json,
        archived_after_unarchive: browserEvidence.archivedAfterUnarchive.json,
        delete: browserEvidence.deletePayload,
        detail_after_delete: {
          status_code: browserEvidence.detailAfterDelete.statusCode,
          body: browserEvidence.detailAfterDelete.json,
        },
        context_after_delete: {
          status_code: browserEvidence.contextAfterDelete.statusCode,
          body: browserEvidence.contextAfterDelete.json,
        },
        active_after_delete: browserEvidence.activeAfterDelete.json,
        archived_after_delete: browserEvidence.archivedAfterDelete.json,
        all_after_delete: browserEvidence.allAfterDelete.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-35-memories-detail-write-real-error.txt'),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    await stopPreviewServer(backend.child)
    await backend.flushLog()
    await fakeOllama.close()
    await rm(workspaceRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
