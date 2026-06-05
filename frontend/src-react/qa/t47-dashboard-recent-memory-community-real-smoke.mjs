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
import { DASHBOARD_SMOKE_TEST_IDS } from '../pages/DashboardPage.smoke-helpers.js'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'
import { COMMUNITIES_SMOKE_TEST_IDS } from '../pages/CommunitiesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpContract({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const recentMemories = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=10`)
  assertSmoke(recentMemories.statusCode === 200, `GET /memories?limit=10 failed: ${recentMemories.raw}`)
  assertSmoke(recentMemories.json?.total === 1, `Expected 1 recent memory, got ${recentMemories.json?.total}`)
  assertSmoke(recentMemories.json?.memories?.[0]?.id === seedPayload.memory_id, `Expected recent memory_id=${seedPayload.memory_id}, got ${recentMemories.json?.memories?.[0]?.id}`)

  const memoryDetail = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}`)
  assertSmoke(memoryDetail.statusCode === 200, `GET /memories/{id} failed: ${memoryDetail.raw}`)
  assertSmoke(memoryDetail.json?.metadata?.title === 'Launch ownership note', `Expected memory title Launch ownership note, got ${memoryDetail.json?.metadata?.title}`)

  const memoryContext = await requestJson(`${backendBaseUrl}/api/v1/memories/${seedPayload.memory_id}/context`)
  assertSmoke(memoryContext.statusCode === 200, `GET /memories/{id}/context failed: ${memoryContext.raw}`)
  assertSmoke(memoryContext.json?.total_communities === 1, `Expected 1 memory context community, got ${memoryContext.json?.total_communities}`)
  assertSmoke(memoryContext.json?.communities?.[0]?.id === seedPayload.community_id, `Expected memory context community_id=${seedPayload.community_id}, got ${memoryContext.json?.communities?.[0]?.id}`)

  const communityDetail = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}`)
  assertSmoke(communityDetail.statusCode === 200, `GET /communities/{id} failed: ${communityDetail.raw}`)
  assertSmoke(communityDetail.json?.title === 'Launch Owners', `Expected community title Launch Owners, got ${communityDetail.json?.title}`)

  const communityEntities = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}/entities?limit=20`)
  const communityRelationships = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}/relationships?limit=20`)
  assertSmoke(communityEntities.statusCode === 200, `GET /communities/{id}/entities failed: ${communityEntities.raw}`)
  assertSmoke(communityRelationships.statusCode === 200, `GET /communities/{id}/relationships failed: ${communityRelationships.raw}`)
  assertSmoke(communityEntities.json?.total === 2, `Expected 2 community entities, got ${communityEntities.json?.total}`)
  assertSmoke(communityRelationships.json?.total === 1, `Expected 1 community relationship, got ${communityRelationships.json?.total}`)

  const ancestors = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}/ancestors`)
  const descendants = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}/descendants`)
  assertSmoke(ancestors.statusCode === 200, `GET /communities/{id}/ancestors failed: ${ancestors.raw}`)
  assertSmoke(descendants.statusCode === 200, `GET /communities/{id}/descendants failed: ${descendants.raw}`)

  return {
    health,
    recentMemories,
    memoryDetail,
    memoryContext,
    communityDetail,
    communityEntities,
    communityRelationships,
    ancestors,
    descendants,
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
    await page.waitForSelector('text=Launch ownership note', { timeout: 30000 })
    await page.getByTestId(DASHBOARD_SMOKE_TEST_IDS.recentItemLink).click()

    await page.waitForURL(`**/memories/${seedPayload.memory_id}`, { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communitiesSection).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.entitiesSection).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Alice', { timeout: 30000 })
    await page.waitForSelector('text=Launch Checklist', { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.communityLink).click()

    await page.waitForURL(`**/communities#${seedPayload.community_id}`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.lineageSection).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.entitiesSection).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.relationshipsSection).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Launch Owners', { timeout: 30000 })
    await page.waitForSelector('text=暂无上游社区', { timeout: 30000 })
    await page.waitForSelector('text=暂无下游社区', { timeout: 30000 })
    await page.waitForSelector('text=owns', { timeout: 30000 })
    await page.waitForSelector('text=Launch Checklist', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-47-dashboard-recent-memory-community-real.png'),
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
    'task-47-dashboard-recent-memory-community-real-summary.txt',
    'task-47-dashboard-recent-memory-community-real-summary.json',
    'task-47-dashboard-recent-memory-community-real-http.json',
    'task-47-dashboard-recent-memory-community-real-seed.json',
    'task-47-dashboard-recent-memory-community-real.png',
    'task-47-dashboard-recent-memory-community-real-error.txt',
    'task-47-dashboard-recent-memory-community-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-dashboard-recent-memory-community-'))
  const backendPort = await findAvailablePort(Number(process.env.T47_BACKEND_PORT ?? '38470'))
  const ollamaPort = await findAvailablePort(Number(process.env.T47_OLLAMA_PORT ?? '38471'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-47-dashboard-recent-memory-community-real-seed.json')

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
    logFileName: 'task-47-dashboard-recent-memory-community-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:dashboard:recent-memory:community-navigation',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      recent_memory_id: seedPayload.memory_id,
      community_id: seedPayload.community_id,
      navigation_path: 'dashboard_recent_item,memory_detail,community_detail',
      memory_context_communities: httpEvidence.memoryContext.json?.total_communities,
      community_entities_total: httpEvidence.communityEntities.json?.total,
      community_relationships_total: httpEvidence.communityRelationships.json?.total,
      ancestors_total: httpEvidence.ancestors.json?.total,
      descendants_total: httpEvidence.descendants.json?.total,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-47-dashboard-recent-memory-community-real.png',
      backend_log: '.sisyphus/evidence/task-47-dashboard-recent-memory-community-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-47-dashboard-recent-memory-community-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `recent_memory_id=${summaryPayload.recent_memory_id}`,
      `community_id=${summaryPayload.community_id}`,
      `navigation_path=${summaryPayload.navigation_path}`,
      `memory_context_communities=${summaryPayload.memory_context_communities}`,
      `community_entities_total=${summaryPayload.community_entities_total}`,
      `community_relationships_total=${summaryPayload.community_relationships_total}`,
      `ancestors_total=${summaryPayload.ancestors_total}`,
      `descendants_total=${summaryPayload.descendants_total}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-47-dashboard-recent-memory-community-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-47-dashboard-recent-memory-community-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-47-dashboard-recent-memory-community-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        recent_memories: httpEvidence.recentMemories.json,
        memory_detail: httpEvidence.memoryDetail.json,
        memory_context: httpEvidence.memoryContext.json,
        community_detail: httpEvidence.communityDetail.json,
        community_entities: httpEvidence.communityEntities.json,
        community_relationships: httpEvidence.communityRelationships.json,
        community_ancestors: httpEvidence.ancestors.json,
        community_descendants: httpEvidence.descendants.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-47-dashboard-recent-memory-community-real-error.txt'),
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
