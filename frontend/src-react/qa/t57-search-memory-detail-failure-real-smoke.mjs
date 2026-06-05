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
import { SEARCH_SMOKE_TEST_IDS } from '../pages/SearchPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SEARCH_QUESTION = 'Who owns the launch checklist?'
const SEARCH_MODE_LABEL = '全局检索'

async function verifyHttpBaseline({ backendBaseUrl, seedPayload, fakeOllama }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const query = await requestJson(`${backendBaseUrl}/api/v1/query`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      question: SEARCH_QUESTION,
      strategy: 'graphrag',
      retrieval_mode: 'global',
      top_k: 5,
      include_sources: true,
    }),
    timeoutMs: 15000,
  })
  assertSmoke(query.statusCode === 200, `POST /query failed: ${query.raw}`)
  assertSmoke(
    query.json?.sources?.[0]?.memory_id === seedPayload.memory_id,
    `Expected search source memory_id=${seedPayload.memory_id}, got ${query.json?.sources?.[0]?.memory_id}`
  )

  const seededDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
  assertSmoke(seededDetail.statusCode === 200, `GET /memories/{id} before delete failed: ${seededDetail.raw}`)

  const counts = fakeOllama.getCounts()
  assertSmoke(counts.embeddingRequests >= 4, `Expected embeddingRequests>=4, got ${counts.embeddingRequests}`)
  assertSmoke(counts.generateRequests >= 1, `Expected generateRequests>=1, got ${counts.generateRequests}`)

  return {
    health,
    query,
    seededDetail,
    fakeOllamaCounts: counts,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/search`, { waitUntil: 'networkidle' })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.form).waitFor({ timeout: 30000 })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill(SEARCH_QUESTION)
    await page.locator(`button.search-strategy-button:has-text("${SEARCH_MODE_LABEL}")`).click()
    const queryResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith('/api/v1/query')
        && response.request().method() === 'POST'
        && response.status() === 200
    )
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
    await queryResponse
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.resultsGrid).waitFor({ timeout: 30000 })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).first().waitFor({ timeout: 30000 })

    const deleteResponse = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`, { method: 'DELETE' })
    assertSmoke(deleteResponse.statusCode === 200, `DELETE /memories/{id} failed: ${deleteResponse.raw}`)
    assertSmoke(deleteResponse.json?.sync_status === 'deleted', 'Delete payload did not return sync_status=deleted')

    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).first().click()
    await page.waitForURL(`**/memories/${seedPayload.memory_id}`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Memory not found', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailArchiveButton).count()) === 0, 'Deleted detail should not expose archive action')
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailDeleteButton).count()) === 0, 'Deleted detail should not expose delete action')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-57-search-memory-detail-failure-real.png'),
      fullPage: true,
    })

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailCloseButton).click()
    await page.waitForURL(`${backendBaseUrl}/memories`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.statePanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=暂无记忆数据', { timeout: 30000 })

    const detailAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    const contextAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
    const allAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=all`)
    assertSmoke(detailAfterDelete.statusCode === 404, `Expected deleted detail 404, got ${detailAfterDelete.statusCode}`)
    assertSmoke(contextAfterDelete.statusCode === 404, `Expected deleted context 404, got ${contextAfterDelete.statusCode}`)
    assertSmoke(allAfterDelete.json?.total === 0, `Expected 0 memories after delete, got ${allAfterDelete.json?.total}`)

    return {
      deleteResponse,
      detailAfterDelete,
      contextAfterDelete,
      allAfterDelete,
      finalUrl: page.url(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-57-search-memory-detail-failure-real-summary.txt',
    'task-57-search-memory-detail-failure-real-summary.json',
    'task-57-search-memory-detail-failure-real-http.json',
    'task-57-search-memory-detail-failure-real-seed.json',
    'task-57-search-memory-detail-failure-real.png',
    'task-57-search-memory-detail-failure-real-error.txt',
    'task-57-search-memory-detail-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-search-memory-detail-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T57_BACKEND_PORT ?? '38570'))
  const ollamaPort = await findAvailablePort(Number(process.env.T57_OLLAMA_PORT ?? '38571'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-57-search-memory-detail-failure-real-seed.json')

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
    logFileName: 'task-57-search-memory-detail-failure-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpBaseline({ backendBaseUrl, seedPayload, fakeOllama })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, seedPayload })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:search:memory:detail:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      recent_memory_id: seedPayload.memory_id,
      navigation_surface: 'search_memory_link',
      query_source_memory_id: httpEvidence.query.json?.sources?.[0]?.memory_id,
      delete_status: browserEvidence.deleteResponse.statusCode,
      detail_status_after_delete: browserEvidence.detailAfterDelete.statusCode,
      context_status_after_delete: browserEvidence.contextAfterDelete.statusCode,
      total_after_delete: browserEvidence.allAfterDelete.json?.total,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-57-search-memory-detail-failure-real.png',
      backend_log: '.sisyphus/evidence/task-57-search-memory-detail-failure-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-57-search-memory-detail-failure-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `recent_memory_id=${summaryPayload.recent_memory_id}`,
      `navigation_surface=${summaryPayload.navigation_surface}`,
      `query_source_memory_id=${summaryPayload.query_source_memory_id}`,
      `delete_status=${summaryPayload.delete_status}`,
      `detail_status_after_delete=${summaryPayload.detail_status_after_delete}`,
      `context_status_after_delete=${summaryPayload.context_status_after_delete}`,
      `total_after_delete=${summaryPayload.total_after_delete}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-57-search-memory-detail-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-57-search-memory-detail-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-57-search-memory-detail-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        query: httpEvidence.query.json,
        delete: {
          status_code: browserEvidence.deleteResponse.statusCode,
          body: browserEvidence.deleteResponse.json,
        },
        detail_after_delete: {
          status_code: browserEvidence.detailAfterDelete.statusCode,
          body: browserEvidence.detailAfterDelete.json,
        },
        context_after_delete: {
          status_code: browserEvidence.contextAfterDelete.statusCode,
          body: browserEvidence.contextAfterDelete.json,
        },
        all_after_delete: browserEvidence.allAfterDelete.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-57-search-memory-detail-failure-real-error.txt'),
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
