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
import { GRAPH_SMOKE_TEST_IDS } from '../pages/GraphPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpContract({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const stats = await requestJson(`${backendBaseUrl}/api/v1/graph/stats`)
  assertSmoke(stats.statusCode === 200, `GET /graph/stats failed: ${stats.raw}`)
  assertSmoke(stats.json?.total_entities === 2, `Expected 2 entities, got ${stats.json?.total_entities}`)
  assertSmoke(stats.json?.total_relationships === 1, `Expected 1 relationship, got ${stats.json?.total_relationships}`)
  assertSmoke(stats.json?.total_memories === 1, `Expected 1 memory, got ${stats.json?.total_memories}`)

  const entities = await requestJson(`${backendBaseUrl}/api/v1/graph/entities?limit=200`)
  assertSmoke(entities.statusCode === 200, `GET /graph/entities failed: ${entities.raw}`)
  assertSmoke(entities.json?.total === 2, `Expected 2 graph entities, got ${entities.json?.total}`)

  const relationships = await requestJson(`${backendBaseUrl}/api/v1/graph/relationships?limit=400`)
  assertSmoke(relationships.statusCode === 200, `GET /graph/relationships failed: ${relationships.raw}`)
  assertSmoke(relationships.json?.total === 1, `Expected 1 graph relationship, got ${relationships.json?.total}`)
  assertSmoke(
    relationships.json?.relationships?.[0]?.type === 'owns',
    `Expected relationship type owns, got ${relationships.json?.relationships?.[0]?.type}`
  )

  return { health, stats, entities, relationships }
}

async function runBrowserFlow({ backendBaseUrl }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/graph`, { waitUntil: 'networkidle' })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.toolbar).waitFor({ timeout: 30000 })
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).waitFor({ timeout: 30000 })

    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('circular')
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('hierarchical')
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('clustered')
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.layoutSelect).selectOption('force')

    const nodeLocator = page.locator(`[data-testid="${GRAPH_SMOKE_TEST_IDS.node}"]`)
    await nodeLocator.first().waitFor({ timeout: 30000 })
    const nodeCount = await nodeLocator.count()
    assertSmoke(nodeCount >= 2, `Expected at least 2 graph nodes, got ${nodeCount}`)

    await nodeLocator.first().click()
    await page.getByTestId(GRAPH_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Alice', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-26-graph-real.png'),
      fullPage: true,
    })

    return {
      nodeCount,
      finalUrl: page.url(),
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-26-graph-real-summary.txt',
    'task-26-graph-real-summary.json',
    'task-26-graph-real-http.json',
    'task-26-graph-real-seed.json',
    'task-26-graph-real.png',
    'task-26-graph-real-error.txt',
    'task-26-graph-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-graph-real-'))
  const backendPort = await findAvailablePort(Number(process.env.T26_BACKEND_PORT ?? '38260'))
  const ollamaPort = await findAvailablePort(Number(process.env.T26_OLLAMA_PORT ?? '38261'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-26-graph-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-26-graph-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:graph',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      total_entities: httpEvidence.stats.json?.total_entities,
      total_relationships: httpEvidence.stats.json?.total_relationships,
      total_memories: httpEvidence.stats.json?.total_memories,
      browser_node_count: browserEvidence.nodeCount,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-26-graph-real.png',
      backend_log: '.sisyphus/evidence/task-26-graph-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-26-graph-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `total_entities=${summaryPayload.total_entities}`,
      `total_relationships=${summaryPayload.total_relationships}`,
      `total_memories=${summaryPayload.total_memories}`,
      `browser_node_count=${summaryPayload.browser_node_count}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-26-graph-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-26-graph-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-26-graph-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        stats: httpEvidence.stats.json,
        entities: httpEvidence.entities.json,
        relationships: httpEvidence.relationships.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-26-graph-real-error.txt'),
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
