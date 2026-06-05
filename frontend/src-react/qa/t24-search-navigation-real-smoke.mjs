import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
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
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'
import { SEARCH_SMOKE_TEST_IDS } from '../pages/SearchPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SETTINGS_PATH_ENV = 'MEMORY_GRAPH_SETTINGS_PATH'
const SEARCH_QUESTION = 'Who owns the launch checklist?'
const SEARCH_MODE_LABELS = {
  global: '全局检索',
  local: '本地检索',
  hybrid: '混合检索',
}

async function querySearchMode({ backendBaseUrl, mode }) {
  const response = await requestJson(`${backendBaseUrl}/api/v1/query`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      question: SEARCH_QUESTION,
      strategy: 'graphrag',
      retrieval_mode: mode,
      top_k: 5,
      include_sources: true,
    }),
    timeoutMs: 15000,
  })
  return response
}

async function verifyHttpContract({ backendBaseUrl, seedPayload, fakeOllama }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const memories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0`)
  assertSmoke(memories.statusCode === 200, `GET /memories failed: ${memories.raw}`)
  assertSmoke(memories.json?.total === 1, `Expected one seeded memory, got ${memories.json?.total}`)
  assertSmoke(memories.json?.memories?.[0]?.id === seedPayload.memory_id, 'Seeded memory_id did not surface in /memories')

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=20`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 1, `Expected one seeded community, got ${communities.json?.total}`)
  assertSmoke(
    communities.json?.communities?.[0]?.id === seedPayload.community_id,
    `Expected community_id=${seedPayload.community_id}, got ${communities.json?.communities?.[0]?.id}`
  )

  const queryModes = {}
  for (const mode of ['global', 'local', 'hybrid']) {
    const query = await querySearchMode({ backendBaseUrl, mode })
    assertSmoke(query.statusCode === 200, `POST /query (${mode}) failed: ${query.raw}`)
    assertSmoke(
      query.json?.sources?.[0]?.memory_id === seedPayload.memory_id,
      `Expected ${mode} query source memory_id=${seedPayload.memory_id}, got ${query.json?.sources?.[0]?.memory_id}`
    )
    assertSmoke(
      query.json?.sources?.[0]?.community_id === seedPayload.community_id,
      `Expected ${mode} query source community_id=${seedPayload.community_id}, got ${query.json?.sources?.[0]?.community_id}`
    )
    assertSmoke(
      query.json?.communities?.[0]?.community_id === seedPayload.community_id,
      `Expected ${mode} query community_id=${seedPayload.community_id}, got ${query.json?.communities?.[0]?.community_id}`
    )
    assertSmoke(
      String(query.json?.answer || '').includes('Alice owns the launch checklist'),
      `Expected ${mode} answer to mention ownership, got ${query.json?.answer}`
    )
    if (mode !== 'global') {
      assertSmoke(
        Array.isArray(query.json?.entities) && query.json.entities.includes('Alice'),
        `Expected ${mode} query.entities to include Alice, got ${JSON.stringify(query.json?.entities)}`
      )
    }
    queryModes[mode] = query
  }

  const memoryContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
  assertSmoke(memoryContext.statusCode === 200, `GET /memories/{id}/context failed: ${memoryContext.raw}`)
  assertSmoke(memoryContext.json?.total_communities === 1, `Expected one memory context community, got ${memoryContext.json?.total_communities}`)
  assertSmoke(
    memoryContext.json?.communities?.[0]?.id === seedPayload.community_id,
    `Expected memory context community_id=${seedPayload.community_id}, got ${memoryContext.json?.communities?.[0]?.id}`
  )

  const counts = fakeOllama.getCounts()
  assertSmoke(counts.embeddingRequests >= 8, `Expected embeddingRequests>=8, got ${counts.embeddingRequests}`)
  assertSmoke(counts.generateRequests >= 5, `Expected generateRequests>=5, got ${counts.generateRequests}`)

  return {
    health,
    memories,
    communities,
    queryModes,
    memoryContext,
    fakeOllamaCounts: counts,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()

    async function runSearchAndWait(mode) {
      await page.goto(`${backendBaseUrl}/search`, { waitUntil: 'networkidle' })
      await page.getByTestId(SEARCH_SMOKE_TEST_IDS.form).waitFor({ timeout: 30000 })
      await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill(SEARCH_QUESTION)
      await page.locator(`button.search-strategy-button:has-text("${SEARCH_MODE_LABELS[mode]}")`).click()
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
      await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceCommunityLink).first().waitFor({ timeout: 30000 })
      await page.getByTestId(SEARCH_SMOKE_TEST_IDS.communityLink).first().waitFor({ timeout: 30000 })
    }

    await runSearchAndWait('global')
    const detailResponse = page.waitForResponse(
      (response) =>
        response.url().includes(`/api/v1/memories/${seedPayload.memory_id}`)
        && !response.url().endsWith('/context')
        && response.request().method() === 'GET'
        && response.status() === 200
    )
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailToggle).first().click()
    await detailResponse
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=notes/launch-checklist.md', { timeout: 30000 })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).first().click()
    await page.waitForURL(`**/memories/${seedPayload.memory_id}`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communitiesSection).waitFor({ timeout: 30000 })

    await runSearchAndWait('local')
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceCommunityLink).first().click()
    await page.waitForURL(`**/communities#${seedPayload.community_id}`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Launch Owners', { timeout: 30000 })

    await runSearchAndWait('hybrid')
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.communityLink).first().click()
    await page.waitForURL('**/communities*', { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Launch Owners', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-24-search-navigation-real.png'),
      fullPage: true,
    })

    return {
      finalUrl: page.url(),
      browserModesTested: ['global', 'local', 'hybrid'],
      sourceDetailLoaded: true,
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-24-search-navigation-real-summary.txt',
    'task-24-search-navigation-real-summary.json',
    'task-24-search-navigation-real-http.json',
    'task-24-search-navigation-real-seed.json',
    'task-24-search-navigation-real.png',
    'task-24-search-navigation-real-error.txt',
    'task-24-search-navigation-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-search-navigation-'))
  const backendPort = await findAvailablePort(Number(process.env.T24_BACKEND_PORT ?? '38240'))
  const ollamaPort = await findAvailablePort(Number(process.env.T24_OLLAMA_PORT ?? '38241'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-24-search-navigation-real-seed.json')

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
    logFileName: 'task-24-search-navigation-real-backend.log',
    backendPort,
    extraEnv: {
      [SETTINGS_PATH_ENV]: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, seedPayload, fakeOllama })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, seedPayload })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:search:navigation',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      memory_id: seedPayload.memory_id,
      community_id: seedPayload.community_id,
      query_modes_tested: Object.keys(httpEvidence.queryModes),
      browser_modes_tested: browserEvidence.browserModesTested,
      source_detail_loaded: browserEvidence.sourceDetailLoaded,
      query_source_memory_id: httpEvidence.queryModes.global.json?.sources?.[0]?.memory_id,
      query_source_community_id: httpEvidence.queryModes.global.json?.sources?.[0]?.community_id,
      community_link_surfaces_tested: ['source', 'result'],
      local_query_entities: httpEvidence.queryModes.local.json?.entities || [],
      hybrid_query_entities: httpEvidence.queryModes.hybrid.json?.entities || [],
      query_answer_excerpt: String(httpEvidence.queryModes.hybrid.json?.answer || '').slice(0, 120),
      context_community_count: httpEvidence.memoryContext.json?.total_communities,
      fake_ollama_embedding_requests: httpEvidence.fakeOllamaCounts.embeddingRequests,
      fake_ollama_generate_requests: httpEvidence.fakeOllamaCounts.generateRequests,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-24-search-navigation-real.png',
      backend_log: '.sisyphus/evidence/task-24-search-navigation-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-24-search-navigation-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `memory_id=${summaryPayload.memory_id}`,
      `community_id=${summaryPayload.community_id}`,
      `query_modes_tested=${summaryPayload.query_modes_tested.join(',')}`,
      `browser_modes_tested=${summaryPayload.browser_modes_tested.join(',')}`,
      `source_detail_loaded=${summaryPayload.source_detail_loaded}`,
      `query_source_memory_id=${summaryPayload.query_source_memory_id}`,
      `query_source_community_id=${summaryPayload.query_source_community_id}`,
      `community_link_surfaces_tested=${summaryPayload.community_link_surfaces_tested.join(',')}`,
      `local_query_entities=${summaryPayload.local_query_entities.join(',')}`,
      `hybrid_query_entities=${summaryPayload.hybrid_query_entities.join(',')}`,
      `context_community_count=${summaryPayload.context_community_count}`,
      `fake_ollama_embedding_requests=${summaryPayload.fake_ollama_embedding_requests}`,
      `fake_ollama_generate_requests=${summaryPayload.fake_ollama_generate_requests}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-24-search-navigation-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-24-search-navigation-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-24-search-navigation-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        memories: httpEvidence.memories.json,
        communities: httpEvidence.communities.json,
        query_modes: {
          global: httpEvidence.queryModes.global.json,
          local: httpEvidence.queryModes.local.json,
          hybrid: httpEvidence.queryModes.hybrid.json,
        },
        memory_context: httpEvidence.memoryContext.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-24-search-navigation-real-error.txt'),
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
