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
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SEARCH_QUESTION = 'Who owns the launch checklist?'
const SEARCH_MODE_LABEL = '混合检索'
const MISSING_COMMUNITY_ID = 'comm-missing-search-result-stale-link-real-smoke'

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
      retrieval_mode: 'hybrid',
      top_k: 5,
      include_sources: true,
    }),
    timeoutMs: 15000,
  })
  assertSmoke(query.statusCode === 200, `POST /query failed: ${query.raw}`)
  assertSmoke(query.json?.communities?.[0]?.community_id === seedPayload.community_id, `Expected first community hit ${seedPayload.community_id}, got ${query.json?.communities?.[0]?.community_id}`)

  const communityDetail = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}`)
  assertSmoke(communityDetail.statusCode === 200, `GET /communities/{id} failed: ${communityDetail.raw}`)

  const missingCommunity = await requestJson(`${backendBaseUrl}/api/v1/communities/${MISSING_COMMUNITY_ID}`)
  assertSmoke(missingCommunity.statusCode === 404, `Expected missing community detail 404, got ${missingCommunity.statusCode}`)

  return {
    health,
    query,
    communityDetail,
    missingCommunity,
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
    await page
      .getByTestId(SEARCH_SMOKE_TEST_IDS.communitySourceItem)
      .filter({ hasText: 'Launch Owners' })
      .getByTestId(SEARCH_SMOKE_TEST_IDS.communityLink)
      .waitFor({ timeout: 30000 })

    await page
      .getByTestId(SEARCH_SMOKE_TEST_IDS.communitySourceItem)
      .filter({ hasText: 'Launch Owners' })
      .getByTestId(SEARCH_SMOKE_TEST_IDS.communityLink)
      .click()
    await page.waitForURL(`**/communities#${seedPayload.community_id}`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=社区详情', { timeout: 30000 })

    await page.evaluate((communityId) => {
      window.location.hash = `#${communityId}`
    }, MISSING_COMMUNITY_ID)

    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ timeout: 30000 })
    await page.waitForSelector(`text=Community ${MISSING_COMMUNITY_ID} not found`, { timeout: 30000 })
    await page.waitForTimeout(500)
    assertSmoke((await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).count()) === 0, 'Stale community hash should clear existing detail panel when entered from Search result surface')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-59-search-result-community-stale-link-real.png'),
      fullPage: true,
    })

    return {
      finalUrl: page.url(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-59-search-result-community-stale-link-real-summary.txt',
    'task-59-search-result-community-stale-link-real-summary.json',
    'task-59-search-result-community-stale-link-real-http.json',
    'task-59-search-result-community-stale-link-real-seed.json',
    'task-59-search-result-community-stale-link-real.png',
    'task-59-search-result-community-stale-link-real-error.txt',
    'task-59-search-result-community-stale-link-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-search-result-community-stale-link-'))
  const backendPort = await findAvailablePort(Number(process.env.T59_BACKEND_PORT ?? '38590'))
  const ollamaPort = await findAvailablePort(Number(process.env.T59_OLLAMA_PORT ?? '38591'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-59-search-result-community-stale-link-real-seed.json')

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
    logFileName: 'task-59-search-result-community-stale-link-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:search:result-community:stale-link',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      community_id: seedPayload.community_id,
      missing_community_id: MISSING_COMMUNITY_ID,
      link_surface: 'result',
      query_hit_community_id: httpEvidence.query.json?.communities?.[0]?.community_id,
      missing_detail_status: httpEvidence.missingCommunity.statusCode,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-59-search-result-community-stale-link-real.png',
      backend_log: '.sisyphus/evidence/task-59-search-result-community-stale-link-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-59-search-result-community-stale-link-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `community_id=${summaryPayload.community_id}`,
      `missing_community_id=${summaryPayload.missing_community_id}`,
      `link_surface=${summaryPayload.link_surface}`,
      `query_hit_community_id=${summaryPayload.query_hit_community_id}`,
      `missing_detail_status=${summaryPayload.missing_detail_status}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-59-search-result-community-stale-link-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-59-search-result-community-stale-link-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-59-search-result-community-stale-link-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        query: httpEvidence.query.json,
        community_detail: httpEvidence.communityDetail.json,
        missing_detail: {
          status_code: httpEvidence.missingCommunity.statusCode,
          body: httpEvidence.missingCommunity.json,
        },
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-59-search-result-community-stale-link-real-error.txt'),
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
