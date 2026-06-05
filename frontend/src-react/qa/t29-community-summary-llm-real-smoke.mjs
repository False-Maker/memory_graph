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
const REFRESHED_SUMMARY = 'Launch Owners is a refreshed summary covering Alice, the launch checklist, and release coordination.'

async function verifyHttpContract({ backendBaseUrl, seedPayload, fakeOllama }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const beforeSummary = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}`)
  assertSmoke(beforeSummary.statusCode === 200, `GET /communities/{id} failed: ${beforeSummary.raw}`)
  assertSmoke(beforeSummary.json?.entity_count >= 3, `Expected large community entity_count>=3, got ${beforeSummary.json?.entity_count}`)
  assertSmoke(beforeSummary.json?.summary === 'stale large summary should be replaced', `Expected stale large summary, got ${beforeSummary.json?.summary}`)

  const regenerate = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}/summarize`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
    },
    body: JSON.stringify({
      regenerate: true,
      max_tokens: 500,
    }),
  })
  assertSmoke(regenerate.statusCode === 200, `POST /communities/{id}/summarize failed: ${regenerate.raw}`)
  assertSmoke(regenerate.json?.summary === REFRESHED_SUMMARY, `Expected refreshed LLM summary, got ${regenerate.json?.summary}`)

  const afterSummary = await requestJson(`${backendBaseUrl}/api/v1/communities/${seedPayload.community_id}`)
  assertSmoke(afterSummary.statusCode === 200, `GET /communities/{id} after summarize failed: ${afterSummary.raw}`)
  assertSmoke(afterSummary.json?.summary === REFRESHED_SUMMARY, `Expected persisted LLM summary, got ${afterSummary.json?.summary}`)

  const counts = fakeOllama.getCounts()
  assertSmoke(counts.generateRequests >= 1, `Expected at least one generate request, got ${counts.generateRequests}`)

  return { health, beforeSummary, regenerate, afterSummary, counts }
}

async function runBrowserFlow({ backendBaseUrl, seedPayload }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/communities#${seedPayload.community_id}`, { waitUntil: 'networkidle' })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.detailPanel).waitFor({ timeout: 30000 })
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.summarizeButton).click()
    await page.getByTestId(COMMUNITIES_SMOKE_TEST_IDS.actionFeedback).waitFor({ timeout: 30000 })
    await page.waitForSelector(`text=${REFRESHED_SUMMARY}`, { timeout: 30000 })

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-29-community-summary-llm-real.png'),
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
    'task-29-community-summary-llm-real-summary.txt',
    'task-29-community-summary-llm-real-summary.json',
    'task-29-community-summary-llm-real-http.json',
    'task-29-community-summary-llm-real-seed.json',
    'task-29-community-summary-llm-real.png',
    'task-29-community-summary-llm-real-error.txt',
    'task-29-community-summary-llm-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-community-summary-llm-real-'))
  const backendPort = await findAvailablePort(Number(process.env.T29_BACKEND_PORT ?? '38290'))
  const ollamaPort = await findAvailablePort(Number(process.env.T29_OLLAMA_PORT ?? '38291'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const ollamaBaseUrl = buildBaseUrl(ollamaPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: ollamaBaseUrl,
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-29-community-summary-llm-real-seed.json')

  const fakeOllama = await startFakeOllamaServer(ollamaPort)
  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'large_summary',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-29-community-summary-llm-real-backend.log',
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
      command: 'npm --prefix frontend run qa:real-stack-smoke:communities:summary:llm',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      profile: seedPayload.profile,
      community_id: seedPayload.community_id,
      initial_summary: httpEvidence.beforeSummary.json?.summary,
      refreshed_summary: httpEvidence.afterSummary.json?.summary,
      entity_count: httpEvidence.beforeSummary.json?.entity_count,
      fake_ollama_generate_requests: httpEvidence.counts.generateRequests,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-29-community-summary-llm-real.png',
      backend_log: '.sisyphus/evidence/task-29-community-summary-llm-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-29-community-summary-llm-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `profile=${summaryPayload.profile}`,
      `community_id=${summaryPayload.community_id}`,
      `entity_count=${summaryPayload.entity_count}`,
      `initial_summary=${summaryPayload.initial_summary}`,
      `refreshed_summary=${summaryPayload.refreshed_summary}`,
      `fake_ollama_generate_requests=${summaryPayload.fake_ollama_generate_requests}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-29-community-summary-llm-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-29-community-summary-llm-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-29-community-summary-llm-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        before_summary: httpEvidence.beforeSummary.json,
        regenerate: httpEvidence.regenerate.json,
        after_summary: httpEvidence.afterSummary.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-29-community-summary-llm-real-error.txt'),
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
