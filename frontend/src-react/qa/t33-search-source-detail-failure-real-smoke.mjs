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

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SEARCH_QUESTION = 'Who owns the launch checklist?'

async function verifyHttpContract({ backendBaseUrl, seedPayload }) {
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
  assertSmoke(query.json?.sources?.[0]?.memory_id === seedPayload.memory_id, `Expected source memory id ${seedPayload.memory_id}, got ${query.json?.sources?.[0]?.memory_id}`)
  return { health, query }
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
    await page.locator('button.search-strategy-button:has-text("全局检索")').click()
    const queryResponse = page.waitForResponse(
      (response) =>
        response.url().endsWith('/api/v1/query')
        && response.request().method() === 'POST'
        && response.status() === 200
    )
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.submitButton).click()
    await queryResponse
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.resultsGrid).waitFor({ timeout: 30000 })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailToggle).first().waitFor({ timeout: 30000 })

    const deleteResponse = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`, { method: 'DELETE' })
    assertSmoke(deleteResponse.statusCode === 200, `DELETE /memories/{id} failed: ${deleteResponse.raw}`)
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailToggle).first().click()
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Memory not found', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-33-search-source-detail-failure-real.png'),
      fullPage: true,
    })

    const detailAfterDelete = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
    assertSmoke(detailAfterDelete.statusCode === 404, `Expected deleted memory detail 404, got ${detailAfterDelete.statusCode}`)

    return {
      finalUrl: page.url(),
      deleteStatus: deleteResponse.statusCode,
      detailStatusAfterDelete: detailAfterDelete.statusCode,
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-33-search-source-detail-failure-real-summary.txt',
    'task-33-search-source-detail-failure-real-summary.json',
    'task-33-search-source-detail-failure-real-http.json',
    'task-33-search-source-detail-failure-real-seed.json',
    'task-33-search-source-detail-failure-real.png',
    'task-33-search-source-detail-failure-real-error.txt',
    'task-33-search-source-detail-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-search-source-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T33_BACKEND_PORT ?? '38330'))
  const ollamaPort = await findAvailablePort(Number(process.env.T33_OLLAMA_PORT ?? '38331'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-33-search-source-detail-failure-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'basic',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-33-search-source-detail-failure-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, seedPayload })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, seedPayload })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:search:source-detail:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      memory_id: seedPayload.memory_id,
      delete_status: browserEvidence.deleteStatus,
      detail_status_after_delete: browserEvidence.detailStatusAfterDelete,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-33-search-source-detail-failure-real.png',
      backend_log: '.sisyphus/evidence/task-33-search-source-detail-failure-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-33-search-source-detail-failure-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `memory_id=${summaryPayload.memory_id}`,
      `delete_status=${summaryPayload.delete_status}`,
      `detail_status_after_delete=${summaryPayload.detail_status_after_delete}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-33-search-source-detail-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-33-search-source-detail-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-33-search-source-detail-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        query: httpEvidence.query.json,
        deleted: { status_code: browserEvidence.deleteStatus },
        detail_after_delete: { status_code: browserEvidence.detailStatusAfterDelete },
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-33-search-source-detail-failure-real-error.txt'),
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
