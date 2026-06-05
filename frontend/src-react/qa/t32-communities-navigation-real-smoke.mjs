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

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpContract({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 3, `Expected 3 communities, got ${communities.json?.total}`)
  const root = (communities.json?.communities || []).find((item) => Number(item.level) === 2)
  assertSmoke(Boolean(root), 'Expected one level-2 root community')

  const hierarchy = await requestJson(`${backendBaseUrl}/api/v1/communities/hierarchy`)
  assertSmoke(hierarchy.statusCode === 200, `GET /communities/hierarchy failed: ${hierarchy.raw}`)
  assertSmoke(hierarchy.json?.total_communities === 3, `Expected hierarchy total_communities=3, got ${hierarchy.json?.total_communities}`)

  const subtree = await requestJson(`${backendBaseUrl}/api/v1/communities/${root.id}/hierarchy`)
  assertSmoke(subtree.statusCode === 200, `GET /communities/{id}/hierarchy failed: ${subtree.raw}`)

  const ancestors = await requestJson(`${backendBaseUrl}/api/v1/communities/comm-release-readiness/ancestors`)
  const descendants = await requestJson(`${backendBaseUrl}/api/v1/communities/${root.json?.id || root.id}/descendants`)
  assertSmoke(ancestors.statusCode === 200, `GET ancestors failed: ${ancestors.raw}`)
  assertSmoke(descendants.statusCode === 200, `GET descendants failed: ${descendants.raw}`)
  assertSmoke(ancestors.json?.total === 1, `Expected 1 ancestor, got ${ancestors.json?.total}`)
  assertSmoke(descendants.json?.total === 2, `Expected 2 descendants for root, got ${descendants.json?.total}`)

  return { health, communities, hierarchy, subtree, ancestors, descendants, root: root.json ? root.json : root }
}

async function runBrowserFlow({ backendBaseUrl }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/communities#comm-release-readiness`, { waitUntil: 'networkidle' })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Release Readiness', { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.lineageSection).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Level 2 Cluster 1', { timeout: 30000 })

    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.hierarchyToggle).click()
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.hierarchyPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Launch Owners', { timeout: 30000 })
    await page.waitForSelector('text=Release Readiness', { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-32-communities-navigation-real.png'),
      fullPage: true,
    })

    return { finalUrl: page.url() }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-32-communities-navigation-real-summary.txt',
    'task-32-communities-navigation-real-summary.json',
    'task-32-communities-navigation-real-http.json',
    'task-32-communities-navigation-real-seed.json',
    'task-32-communities-navigation-real.png',
    'task-32-communities-navigation-real-error.txt',
    'task-32-communities-navigation-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-communities-navigation-real-'))
  const backendPort = await findAvailablePort(Number(process.env.T32_BACKEND_PORT ?? '38320'))
  const ollamaPort = await findAvailablePort(Number(process.env.T32_OLLAMA_PORT ?? '38321'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-32-communities-navigation-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'multi_aggregate',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-32-communities-navigation-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:communities:navigation',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      total_communities: httpEvidence.communities.json?.total,
      hierarchy_total: httpEvidence.hierarchy.json?.total_communities,
      root_id: httpEvidence.root.id,
      ancestors_total: httpEvidence.ancestors.json?.total,
      descendants_total: httpEvidence.descendants.json?.total,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-32-communities-navigation-real.png',
      backend_log: '.sisyphus/evidence/task-32-communities-navigation-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-32-communities-navigation-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `total_communities=${summaryPayload.total_communities}`,
      `hierarchy_total=${summaryPayload.hierarchy_total}`,
      `root_id=${summaryPayload.root_id}`,
      `ancestors_total=${summaryPayload.ancestors_total}`,
      `descendants_total=${summaryPayload.descendants_total}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-32-communities-navigation-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-32-communities-navigation-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-32-communities-navigation-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        communities: httpEvidence.communities.json,
        hierarchy: httpEvidence.hierarchy.json,
        subtree: httpEvidence.subtree.json,
        ancestors: httpEvidence.ancestors.json,
        descendants: httpEvidence.descendants.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-32-communities-navigation-real-error.txt'),
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
