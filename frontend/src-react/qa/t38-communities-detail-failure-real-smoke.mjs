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
const MISSING_COMMUNITY_ID = 'comm-missing-detail-real-smoke'

async function verifyHttpContract({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const communities = await requestJson(`${backendBaseUrl}/api/v1/communities?limit=500`)
  assertSmoke(communities.statusCode === 200, `GET /communities failed: ${communities.raw}`)
  assertSmoke(communities.json?.total === 3, `Expected 3 communities, got ${communities.json?.total}`)

  const existingCommunityId = communities.json?.communities?.find((item) => String(item.id) === 'comm-release-readiness')?.id
    || communities.json?.communities?.[0]?.id
  assertSmoke(Boolean(existingCommunityId), 'Expected one existing community id for stale deep-link scenario')

  const missingDetail = await requestJson(`${backendBaseUrl}/api/v1/communities/${MISSING_COMMUNITY_ID}`)
  assertSmoke(missingDetail.statusCode === 404, `Expected missing community detail 404, got ${missingDetail.statusCode}`)

  return {
    health,
    communities,
    existingCommunityId,
    missingDetail,
  }
}

async function runBrowserFlow({ backendBaseUrl, existingCommunityId }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()

    await page.goto(`${backendBaseUrl}/communities#${MISSING_COMMUNITY_ID}`, { waitUntil: 'networkidle' })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ timeout: 30000 })
    await page.waitForSelector(`text=Community ${MISSING_COMMUNITY_ID} not found`, { timeout: 30000 })
    assertSmoke((await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).count()) === 0, 'Missing deep-link should not render stale community detail panel')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-missing.png'),
      fullPage: true,
    })

    await page.goto(`${backendBaseUrl}/communities#${existingCommunityId}`, { waitUntil: 'networkidle' })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=社区详情', { timeout: 30000 })
    await page.waitForSelector('text=社区脉络', { timeout: 30000 })

    await page.evaluate((communityId) => {
      window.location.hash = `#${communityId}`
    }, MISSING_COMMUNITY_ID)

    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ timeout: 30000 })
    await page.waitForSelector(`text=Community ${MISSING_COMMUNITY_ID} not found`, { timeout: 30000 })
    await page.waitForTimeout(500)
    assertSmoke((await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).count()) === 0, 'Stale invalid hash should clear previous community detail panel')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-stale.png'),
      fullPage: true,
    })

    const finalUrl = page.url()
    await page.close()

    return {
      finalUrl,
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-38-communities-detail-failure-real-summary.txt',
    'task-38-communities-detail-failure-real-summary.json',
    'task-38-communities-detail-failure-real-http.json',
    'task-38-communities-detail-failure-real-seed.json',
    'task-38-communities-detail-failure-real-missing.png',
    'task-38-communities-detail-failure-real-stale.png',
    'task-38-communities-detail-failure-real-error.txt',
    'task-38-communities-detail-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-communities-detail-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T38_BACKEND_PORT ?? '38380'))
  const ollamaPort = await findAvailablePort(Number(process.env.T38_OLLAMA_PORT ?? '38381'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-seed.json')

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
    logFileName: 'task-38-communities-detail-failure-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({
      backendBaseUrl,
      existingCommunityId: httpEvidence.existingCommunityId,
    })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:communities:detail:failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      existing_community_id: httpEvidence.existingCommunityId,
      missing_community_id: MISSING_COMMUNITY_ID,
      missing_detail_status: httpEvidence.missingDetail.statusCode,
      total_communities: httpEvidence.communities.json?.total,
      final_url: browserEvidence.finalUrl,
      missing_screenshot: '.sisyphus/evidence/task-38-communities-detail-failure-real-missing.png',
      stale_screenshot: '.sisyphus/evidence/task-38-communities-detail-failure-real-stale.png',
      backend_log: '.sisyphus/evidence/task-38-communities-detail-failure-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-38-communities-detail-failure-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `existing_community_id=${summaryPayload.existing_community_id}`,
      `missing_community_id=${summaryPayload.missing_community_id}`,
      `missing_detail_status=${summaryPayload.missing_detail_status}`,
      `total_communities=${summaryPayload.total_communities}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        communities: httpEvidence.communities.json,
        missing_detail: {
          status_code: httpEvidence.missingDetail.statusCode,
          body: httpEvidence.missingDetail.json,
        },
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-38-communities-detail-failure-real-error.txt'),
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
