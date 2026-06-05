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
import { DASHBOARD_SMOKE_TEST_IDS } from '../pages/DashboardPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpBaseline({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const recentBeforeDelete = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  assertSmoke(recentBeforeDelete.statusCode === 200, `GET /memories before delete failed: ${recentBeforeDelete.raw}`)
  assertSmoke(recentBeforeDelete.json?.total === 1, `Expected 1 recent memory before delete, got ${recentBeforeDelete.json?.total}`)
  assertSmoke(
    recentBeforeDelete.json?.memories?.[0]?.id === seedPayload.memory_id,
    `Expected recent memory_id=${seedPayload.memory_id}, got ${recentBeforeDelete.json?.memories?.[0]?.id}`
  )

  const seededDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
  assertSmoke(seededDetail.statusCode === 200, `GET /memories/{id} before delete failed: ${seededDetail.raw}`)

  return {
    health,
    recentBeforeDelete,
    seededDetail,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).waitFor({ timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).waitFor({ timeout: 30000 })
    assertSmoke((await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).count()) === 1, 'Expected exactly one recent item before delete')

    const deleteResponse = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`, { method: 'DELETE' })
    assertSmoke(deleteResponse.statusCode === 200, `DELETE /memories/{id} failed: ${deleteResponse.raw}`)
    assertSmoke(deleteResponse.json?.sync_status === 'deleted', 'Delete response did not return sync_status=deleted')

    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).click()
    await page.waitForURL(`**/memories/${seedPayload.memory_id}`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Memory not found', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).count()) === 0, 'Deleted detail should not expose archive action')
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).count()) === 0, 'Deleted detail should not expose delete action')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-stale-detail.png'),
      fullPage: true,
    })

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailCloseButton).click()
    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.statePanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无记忆数据', { timeout: 30000 })

    await page.goto(`${backendBaseUrl}/dashboard`, { waitUntil: 'networkidle' })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无记忆，开始添加您的第一条记忆吧！', { timeout: 30000 })
    assertSmoke((await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItem).count()) === 0, 'Dashboard refresh should not keep deleted recent item')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-empty-dashboard.png'),
      fullPage: true,
    })

    const deletedDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    const deletedContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
    const recentAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
    assertSmoke(deletedDetail.statusCode === 404, `Expected deleted detail 404, got ${deletedDetail.statusCode}`)
    assertSmoke(deletedContext.statusCode === 404, `Expected deleted context 404, got ${deletedContext.statusCode}`)
    assertSmoke(recentAfterDelete.json?.total === 0, `Expected 0 recent memories after delete, got ${recentAfterDelete.json?.total}`)

    return {
      deleteResponse,
      deletedDetail,
      deletedContext,
      recentAfterDelete,
      finalUrl: page.url(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-45-dashboard-recent-memory-failure-real-summary.txt',
    'task-45-dashboard-recent-memory-failure-real-summary.json',
    'task-45-dashboard-recent-memory-failure-real-http.json',
    'task-45-dashboard-recent-memory-failure-real-seed.json',
    'task-45-dashboard-recent-memory-failure-real-stale-detail.png',
    'task-45-dashboard-recent-memory-failure-real-empty-dashboard.png',
    'task-45-dashboard-recent-memory-failure-real-error.txt',
    'task-45-dashboard-recent-memory-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-recent-memory-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T45_BACKEND_PORT ?? '38450'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-seed.json')

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
    logFileName: 'task-45-dashboard-recent-memory-failure-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:recent-memory:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      stale_recent_memory_id: seedPayload.memory_id,
      navigation_surface: 'dashboard_recent_item',
      delete_status: browserEvidence.deleteResponse.statusCode,
      deleted_detail_status: browserEvidence.deletedDetail.statusCode,
      deleted_context_status: browserEvidence.deletedContext.statusCode,
      recent_total_before_delete: httpEvidence.recentBeforeDelete.json?.total,
      recent_total_after_delete: browserEvidence.recentAfterDelete.json?.total,
      refreshed_dashboard_empty: true,
      final_url: browserEvidence.finalUrl,
      stale_detail_screenshot: '.sisyphus/evidence/task-45-dashboard-recent-memory-failure-real-stale-detail.png',
      empty_dashboard_screenshot: '.sisyphus/evidence/task-45-dashboard-recent-memory-failure-real-empty-dashboard.png',
      backend_log: '.sisyphus/evidence/task-45-dashboard-recent-memory-failure-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-45-dashboard-recent-memory-failure-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `stale_recent_memory_id=${summaryPayload.stale_recent_memory_id}`,
      `navigation_surface=${summaryPayload.navigation_surface}`,
      `delete_status=${summaryPayload.delete_status}`,
      `deleted_detail_status=${summaryPayload.deleted_detail_status}`,
      `deleted_context_status=${summaryPayload.deleted_context_status}`,
      `recent_total_before_delete=${summaryPayload.recent_total_before_delete}`,
      `recent_total_after_delete=${summaryPayload.recent_total_after_delete}`,
      `refreshed_dashboard_empty=${summaryPayload.refreshed_dashboard_empty}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        recent_before_delete: httpEvidence.recentBeforeDelete.json,
        seeded_detail: httpEvidence.seededDetail.json,
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
        recent_after_delete: browserEvidence.recentAfterDelete.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-45-dashboard-recent-memory-failure-real-error.txt'),
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
