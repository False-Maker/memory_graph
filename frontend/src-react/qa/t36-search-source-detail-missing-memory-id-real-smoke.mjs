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
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'
import { SEARCH_SMOKE_TEST_IDS } from '../pages/SearchPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')
const SEARCH_QUESTION = 'Who owns the launch checklist?'
const SEARCH_MODE_LABELS = {
  global: '全局检索',
  local: '本地检索',
  hybrid: '混合检索',
}

async function querySearchMode({ backendBaseUrl, mode }) {
  return requestJson(`${backendBaseUrl}/api/v1/query`, {
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
}

async function verifyHttpContract({ backendBaseUrl, seedPayload, fakeOllama }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=20`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 1, `Expected one seeded community, got ${communities.json?.total}`)
  assertSmoke(
    communities.json?.communities?.[0]?.id === seedPayload.community_id,
    `Expected community_id=${seedPayload.community_id}, got ${communities.json?.communities?.[0]?.id}`
  )

  const memories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=all`)
  assertSmoke(memories.statusCode === 200, `GET /memories failed: ${memories.raw}`)
  assertSmoke(memories.json?.total === 0, `Expected no seeded memories, got ${memories.json?.total}`)

  const queryModes = {}
  for (const mode of ['global', 'local', 'hybrid']) {
    const query = await querySearchMode({ backendBaseUrl, mode })
    assertSmoke(query.statusCode === 200, `POST /query (${mode}) failed: ${query.raw}`)
    assertSmoke(query.json?.sources?.length >= 1, `Expected ${mode} query to return at least one source`)
    assertSmoke(query.json?.sources?.[0]?.memory_id === null, `Expected ${mode} query source memory_id=null, got ${query.json?.sources?.[0]?.memory_id}`)
    assertSmoke(
      query.json?.sources?.[0]?.community_id === seedPayload.community_id,
      `Expected ${mode} query source community_id=${seedPayload.community_id}, got ${query.json?.sources?.[0]?.community_id}`
    )
    assertSmoke(
      String(query.json?.sources?.[0]?.content || '').includes('community-only evidence'),
      `Expected ${mode} source content to include community-only evidence, got ${query.json?.sources?.[0]?.content}`
    )
    if (mode !== 'global') {
      assertSmoke(
        Array.isArray(query.json?.entities) && query.json.entities.includes('Alice'),
        `Expected ${mode} query.entities to include Alice, got ${JSON.stringify(query.json?.entities)}`
      )
    }
    queryModes[mode] = query
  }

  const communityDetail = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}`)
  assertSmoke(communityDetail.statusCode === 200, `GET /communities/{id} failed: ${communityDetail.raw}`)

  const counts = fakeOllama.getCounts()
  assertSmoke(counts.embeddingRequests >= 6, `Expected embeddingRequests>=6, got ${counts.embeddingRequests}`)
  assertSmoke(counts.generateRequests >= 3, `Expected generateRequests>=3, got ${counts.generateRequests}`)

  return {
    health,
    communities,
    memories,
    queryModes,
    communityDetail,
    fakeOllamaCounts: counts,
  }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    let memoryDetailRequestCount = 0

    page.on('request', (request) => {
      if (
        request.method() === 'GET'
        && /\/api\/v1\/memories\/[^/]+$/.test(request.url())
      ) {
        memoryDetailRequestCount += 1
      }
    })

    await page.goto(`${backendBaseUrl}/search`, { waitUntil: 'networkidle' })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.form).waitFor({ timeout: 30000 })
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.queryInput).fill(SEARCH_QUESTION)
    await page.locator(`button.search-strategy-button:has-text("${SEARCH_MODE_LABELS.global}")`).click()
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

    assertSmoke((await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).count()) === 0, 'Missing-memory-id source should not expose memory link')
    assertSmoke((await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceCommunityLink).count()) >= 1, 'Expected missing-memory-id source to keep source community link')

    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailToggle).first().click()
    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceDetailState).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=该来源未返回 memory_id，无法拉取详情。', { timeout: 30000 })
    await page.waitForTimeout(500)
    assertSmoke(memoryDetailRequestCount === 0, `Expected no memory detail requests, got ${memoryDetailRequestCount}`)

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-36-search-source-detail-missing-memory-id-real.png'),
      fullPage: true,
    })

    await page.getByTestId(SEARCH_SMOKE_TEST_IDS.sourceCommunityLink).first().click()
    await page.waitForURL(`**/communities#${seedPayload.community_id}`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })

    return {
      finalUrl: page.url(),
      memoryDetailRequestCount,
      memoryLinkCount: await page.getByTestId(SEARCH_SMOKE_TEST_IDS.memoryLink).count(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-36-search-source-detail-missing-memory-id-real-summary.txt',
    'task-36-search-source-detail-missing-memory-id-real-summary.json',
    'task-36-search-source-detail-missing-memory-id-real-http.json',
    'task-36-search-source-detail-missing-memory-id-real-seed.json',
    'task-36-search-source-detail-missing-memory-id-real.png',
    'task-36-search-source-detail-missing-memory-id-real-error.txt',
    'task-36-search-source-detail-missing-memory-id-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-search-missing-memory-id-'))
  const backendPort = await findAvailablePort(Number(process.env.T36_BACKEND_PORT ?? '38360'))
  const ollamaPort = await findAvailablePort(Number(process.env.T36_OLLAMA_PORT ?? '38361'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-36-search-source-detail-missing-memory-id-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'missing_memory_id',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-36-search-source-detail-missing-memory-id-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, seedPayload, fakeOllama })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl, seedPayload })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:search:source-detail:missing-memory-id',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      community_id: seedPayload.community_id,
      query_modes_tested: Object.keys(httpEvidence.queryModes),
      global_query_source_memory_id: httpEvidence.queryModes.global.json?.sources?.[0]?.memory_id,
      local_query_source_memory_id: httpEvidence.queryModes.local.json?.sources?.[0]?.memory_id,
      hybrid_query_source_memory_id: httpEvidence.queryModes.hybrid.json?.sources?.[0]?.memory_id,
      link_surface: 'source',
      memory_detail_requests: browserEvidence.memoryDetailRequestCount,
      memory_link_count: browserEvidence.memoryLinkCount,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-36-search-source-detail-missing-memory-id-real.png',
      backend_log: '.sisyphus/evidence/task-36-search-source-detail-missing-memory-id-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-36-search-source-detail-missing-memory-id-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `community_id=${summaryPayload.community_id}`,
      `query_modes_tested=${summaryPayload.query_modes_tested.join(',')}`,
      `global_query_source_memory_id=${summaryPayload.global_query_source_memory_id}`,
      `local_query_source_memory_id=${summaryPayload.local_query_source_memory_id}`,
      `hybrid_query_source_memory_id=${summaryPayload.hybrid_query_source_memory_id}`,
      `link_surface=${summaryPayload.link_surface}`,
      `memory_detail_requests=${summaryPayload.memory_detail_requests}`,
      `memory_link_count=${summaryPayload.memory_link_count}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-36-search-source-detail-missing-memory-id-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-36-search-source-detail-missing-memory-id-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-36-search-source-detail-missing-memory-id-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        communities: httpEvidence.communities.json,
        memories: httpEvidence.memories.json,
        query_global: httpEvidence.queryModes.global.json,
        query_local: httpEvidence.queryModes.local.json,
        query_hybrid: httpEvidence.queryModes.hybrid.json,
        community_detail: httpEvidence.communityDetail.json,
        fake_ollama_counts: httpEvidence.fakeOllamaCounts,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-36-search-source-detail-missing-memory-id-real-error.txt'),
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
