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
const TARGET_COMMUNITY_ID = 'comm-release-readiness'
const QA_FAIL_ENV = 'MEMORY_GRAPH_QA_FAIL_COMMUNITY_FACETS'

async function verifyHttpBaseline({ backendBaseUrl }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const beforeSummary = await requestJson(`${backendBaseUrl}/api/v1/communities/${TARGET_COMMUNITY_ID}`)
  assertSmoke(beforeSummary.statusCode === 200, `GET /communities/{id} failed: ${beforeSummary.raw}`)

  const entities = await requestJson(`${backendBaseUrl}/api/v1/communities/${TARGET_COMMUNITY_ID}/entities?limit=20`)
  const relationships = await requestJson(`${backendBaseUrl}/api/v1/communities/${TARGET_COMMUNITY_ID}/relationships?limit=20`)
  assertSmoke(entities.statusCode === 500, `Expected entities failure 500, got ${entities.statusCode}`)
  assertSmoke(relationships.statusCode === 500, `Expected relationships failure 500, got ${relationships.statusCode}`)

  const ancestors = await requestJson(`${backendBaseUrl}/api/v1/communities/${TARGET_COMMUNITY_ID}/ancestors`)
  const descendants = await requestJson(`${backendBaseUrl}/api/v1/communities/${TARGET_COMMUNITY_ID}/descendants`)
  assertSmoke(ancestors.statusCode === 200, `Expected ancestors success, got ${ancestors.statusCode}`)
  assertSmoke(descendants.statusCode === 200, `Expected descendants success, got ${descendants.statusCode}`)

  return {
    health,
    beforeSummary,
    entities,
    relationships,
    ancestors,
    descendants,
  }
}

async function runBrowserFlow({ backendBaseUrl }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/communities#${TARGET_COMMUNITY_ID}`, { waitUntil: 'networkidle' })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.entitiesError).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.relationshipsError).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=Level 2 Cluster 1', { timeout: 30000 })

    const summarizeResponsePromise = page.waitForResponse(
      (response) =>
        response.url().endsWith(`/api/v1/communities/${TARGET_COMMUNITY_ID}/summarize`)
        && response.request().method() === 'POST'
    )
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.summarizeButton).click()
    const summarizeResponse = await summarizeResponsePromise
    const summarizePayload = await summarizeResponse.json()
    assertSmoke(summarizeResponse.status() === 200, `Expected summarize status 200, got ${summarizeResponse.status()}`)
    assertSmoke(typeof summarizePayload?.summary === 'string' && summarizePayload.summary.length > 0, 'Expected summarize payload to include non-empty summary')

    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=摘要已重新生成', { timeout: 30000 })
    await page.waitForSelector(`text=${summarizePayload.summary}`, { timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.entitiesError).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.relationshipsError).waitFor({ timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-43-community-summary-facet-failure-real.png'),
      fullPage: true,
    })

    return {
      finalUrl: page.url(),
      summarizePayload,
    }
  } finally {
    await browser.close()
  }
}

async function main() {
  await mkdir(EVIDENCE_DIR, { recursive: true })
  await Promise.all([
    'task-43-community-summary-facet-failure-real-summary.txt',
    'task-43-community-summary-facet-failure-real-summary.json',
    'task-43-community-summary-facet-failure-real-http.json',
    'task-43-community-summary-facet-failure-real-seed.json',
    'task-43-community-summary-facet-failure-real.png',
    'task-43-community-summary-facet-failure-real-error.txt',
    'task-43-community-summary-facet-failure-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-community-summary-facet-failure-'))
  const backendPort = await findAvailablePort(Number(process.env.T43_BACKEND_PORT ?? '38430'))
  const ollamaPort = await findAvailablePort(Number(process.env.T43_OLLAMA_PORT ?? '38431'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-43-community-summary-facet-failure-real-seed.json')

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
    logFileName: 'task-43-community-summary-facet-failure-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
      [QA_FAIL_ENV]: `${TARGET_COMMUNITY_ID}:entities,relationships`,
    },
  })

  try {
    const httpEvidence = await verifyHttpBaseline({ backendBaseUrl })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const afterSummary = await requestJson(`${backendBaseUrl}/api/v1/communities/${TARGET_COMMUNITY_ID}`)
    assertSmoke(afterSummary.statusCode === 200, `GET /communities/{id} after summarize failed: ${afterSummary.raw}`)
    assertSmoke(afterSummary.json?.summary === browserEvidence.summarizePayload.summary, 'Expected refreshed summary to persist after summarize')

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:communities:summary:facet-failure',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      target_community_id: TARGET_COMMUNITY_ID,
      before_summary: httpEvidence.beforeSummary.json?.summary,
      refreshed_summary: afterSummary.json?.summary,
      entities_status: httpEvidence.entities.statusCode,
      relationships_status: httpEvidence.relationships.statusCode,
      ancestors_status: httpEvidence.ancestors.statusCode,
      descendants_status: httpEvidence.descendants.statusCode,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-43-community-summary-facet-failure-real.png',
      backend_log: '.sisyphus/evidence/task-43-community-summary-facet-failure-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-43-community-summary-facet-failure-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `target_community_id=${summaryPayload.target_community_id}`,
      `before_summary=${summaryPayload.before_summary}`,
      `refreshed_summary=${summaryPayload.refreshed_summary}`,
      `entities_status=${summaryPayload.entities_status}`,
      `relationships_status=${summaryPayload.relationships_status}`,
      `ancestors_status=${summaryPayload.ancestors_status}`,
      `descendants_status=${summaryPayload.descendants_status}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-43-community-summary-facet-failure-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-43-community-summary-facet-failure-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-43-community-summary-facet-failure-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        before_summary: httpEvidence.beforeSummary.json,
        entities: {
          status_code: httpEvidence.entities.statusCode,
          body: httpEvidence.entities.json,
        },
        relationships: {
          status_code: httpEvidence.relationships.statusCode,
          body: httpEvidence.relationships.json,
        },
        ancestors: httpEvidence.ancestors.json,
        descendants: httpEvidence.descendants.json,
        after_summary: afterSummary.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-43-community-summary-facet-failure-real-error.txt'),
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
