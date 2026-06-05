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
const MISSING_MEMORY_ID = 'mem-missing-detail-real-smoke'

async function verifyHttpBaseline({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const seededDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
  assertSmoke(seededDetail.statusCode === 200, `GET /memories/{seeded} failed: ${seededDetail.raw}`)

  const missingDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${MISSING_MEMORY_ID}`)
  const missingContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${MISSING_MEMORY_ID}/context`)
  assertSmoke(missingDetail.statusCode === 404, `Expected missing detail 404, got ${missingDetail.statusCode}`)
  assertSmoke(missingContext.statusCode === 404, `Expected missing context 404, got ${missingContext.statusCode}`)

  const allBeforeDelete = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=all`)
  assertSmoke(allBeforeDelete.statusCode === 200, `GET /memories before delete failed: ${allBeforeDelete.raw}`)
  assertSmoke(allBeforeDelete.json?.total === 1, `Expected 1 memory before delete, got ${allBeforeDelete.json?.total}`)

  return {
    health,
    seededDetail,
    missingDetail,
    missingContext,
    allBeforeDelete,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const context = await browser.newContext()
    const page = await context.newPage()

    await page.goto(`${backendBaseUrl}/memories/${MISSING_MEMORY_ID}`, { waitUntil: 'networkidle' })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Memory not found', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).count()) === 0, 'Missing detail should not expose archive action')
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).count()) === 0, 'Missing detail should not expose delete action')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-missing.png'),
      fullPage: true,
    })

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailCloseButton).click()
    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.list).waitFor({ timeout: 30000 })

    const deleteResponse = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`, { method: 'DELETE' })
    assertSmoke(deleteResponse.statusCode === 200, `DELETE /memories/{seeded} failed: ${deleteResponse.raw}`)
    assertSmoke(deleteResponse.json?.sync_status === 'deleted', 'Delete response did not return sync_status=deleted')

    await page.goto(`${backendBaseUrl}/memories/${seedPayload.memory_id}`, { waitUntil: 'networkidle' })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Memory not found', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).count()) === 0, 'Deleted detail should not expose archive action')
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).count()) === 0, 'Deleted detail should not expose delete action')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-deleted.png'),
      fullPage: true,
    })

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailCloseButton).click()
    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.statePanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无记忆数据', { timeout: 30000 })

    const deletedDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    const deletedContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
    const allAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=all`)
    assertSmoke(deletedDetail.statusCode === 404, `Expected deleted detail 404, got ${deletedDetail.statusCode}`)
    assertSmoke(deletedContext.statusCode === 404, `Expected deleted context 404, got ${deletedContext.statusCode}`)
    assertSmoke(allAfterDelete.json?.total === 0, `Expected 0 memories after delete, got ${allAfterDelete.json?.total}`)

    const finalUrl = page.url()
    await context.close()

    return {
      deleteResponse,
      deletedDetail,
      deletedContext,
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
    'task-37-memories-detail-failure-real-summary.txt',
    'task-37-memories-detail-failure-real-summary.json',
    'task-37-memories-detail-failure-real-http.json',
    'task-37-memories-detail-failure-real-seed.json',
    'task-37-memories-detail-failure-real-missing.png',
    'task-37-memories-detail-failure-real-deleted.png',
    'task-37-memories-detail-failure-real-error.txt',
    'task-37-memories-detail-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-memories-detail-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T37_BACKEND_PORT ?? '38370'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-seed.json')

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
    logFileName: 'task-37-memories-detail-failure-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:memories:detail:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      seeded_memory_id: seedPayload.memory_id,
      missing_memory_id: MISSING_MEMORY_ID,
      missing_detail_status: httpEvidence.missingDetail.statusCode,
      missing_context_status: httpEvidence.missingContext.statusCode,
      delete_status: browserEvidence.deleteResponse.statusCode,
      deleted_detail_status: browserEvidence.deletedDetail.statusCode,
      deleted_context_status: browserEvidence.deletedContext.statusCode,
      total_before_delete: httpEvidence.allBeforeDelete.json?.total,
      total_after_delete: browserEvidence.allAfterDelete.json?.total,
      final_url: browserEvidence.finalUrl,
      missing_screenshot: '.sisyphus/evidence/task-37-memories-detail-failure-real-missing.png',
      deleted_screenshot: '.sisyphus/evidence/task-37-memories-detail-failure-real-deleted.png',
      backend_log: '.sisyphus/evidence/task-37-memories-detail-failure-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-37-memories-detail-failure-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `seeded_memory_id=${summaryPayload.seeded_memory_id}`,
      `missing_memory_id=${summaryPayload.missing_memory_id}`,
      `missing_detail_status=${summaryPayload.missing_detail_status}`,
      `missing_context_status=${summaryPayload.missing_context_status}`,
      `delete_status=${summaryPayload.delete_status}`,
      `deleted_detail_status=${summaryPayload.deleted_detail_status}`,
      `deleted_context_status=${summaryPayload.deleted_context_status}`,
      `total_before_delete=${summaryPayload.total_before_delete}`,
      `total_after_delete=${summaryPayload.total_after_delete}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        seeded_detail: httpEvidence.seededDetail.json,
        missing_detail: {
          status_code: httpEvidence.missingDetail.statusCode,
          body: httpEvidence.missingDetail.json,
        },
        missing_context: {
          status_code: httpEvidence.missingContext.statusCode,
          body: httpEvidence.missingContext.json,
        },
        all_before_delete: httpEvidence.allBeforeDelete.json,
        delete: {
          status_code: browserEvidence.deleteResponse.statusCode,
          body: browserEvidence.deleteResponse.json,
        },
        deleted_detail: {
          status_code: browserEvidence.deletedDetail.statusCode,
          body: browserEvidence.deletedDetail.json,
        },
        deleted_context: {
          status_code: browserEvidence.deletedContext.statusCode,
          body: browserEvidence.deletedContext.json,
        },
        all_after_delete: browserEvidence.allAfterDelete.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-37-memories-detail-failure-real-error.txt'),
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
