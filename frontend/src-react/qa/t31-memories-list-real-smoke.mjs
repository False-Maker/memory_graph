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
import { runSeedFixture } from './search-real-smoke-fixtures.mjs'
import { MEMORIES_SMOKE_TEST_IDS } from '../pages/MemoriesPage.smoke-helpers.js'

const FRONTEND_ROOT = path.resolve(process.cwd())
const REPO_ROOT = path.resolve(FRONTEND_ROOT, '..')
const EVIDENCE_DIR = path.resolve(REPO_ROOT, '.sisyphus', 'evidence')

async function verifyHttpContract({ backendBaseUrl, seedPayload }) {
  const health = await waitForStatus(
    `${backendBaseUrl}/health`,
    (response) => response.statusCode === 200 && response.json?.status === 'healthy'
  )

  const active = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=active`)
  assertSmoke(active.statusCode === 200, `GET /memories active failed: ${active.raw}`)
  assertSmoke(active.json?.total === 19, `Expected 19 active memories, got ${active.json?.total}`)

  const archived = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=archived`)
  assertSmoke(archived.statusCode === 200, `GET /memories archived failed: ${archived.raw}`)
  assertSmoke(archived.json?.total === 4, `Expected 4 archived memories, got ${archived.json?.total}`)

  const allPage1 = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=0&status=all`)
  assertSmoke(allPage1.statusCode === 200, `GET /memories all page1 failed: ${allPage1.raw}`)
  assertSmoke(allPage1.json?.total === 23, `Expected 23 total memories, got ${allPage1.json?.total}`)
  assertSmoke(allPage1.json?.memories?.length === 20, `Expected 20 page1 memories, got ${allPage1.json?.memories?.length}`)

  const allPage2 = await requestJson(`${backendBaseUrl}/api/v1/memories?limit=20&offset=20&status=all`)
  assertSmoke(allPage2.statusCode === 200, `GET /memories all page2 failed: ${allPage2.raw}`)
  assertSmoke(allPage2.json?.memories?.length === 3, `Expected 3 page2 memories, got ${allPage2.json?.memories?.length}`)

  const returnedIds = allPage1.json?.memories?.concat(allPage2.json?.memories ?? []).map((item) => item.id) ?? []
  assertSmoke(
    seedPayload.memory_ids.every((memoryId) => returnedIds.includes(memoryId)),
    `Expected all seeded memory ids in paginated list, got ${returnedIds.join(',')}`
  )

  return { health, active, archived, allPage1, allPage2 }
}

async function runBrowserFlow({ backendBaseUrl }) {
  const browser = await chromium.launch({
    env: buildSmokeBrowserEnv(FRONTEND_ROOT, process.env),
  })

  try {
    const page = await browser.newPage()
    await page.goto(`${backendBaseUrl}/memories`, { waitUntil: 'networkidle' })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.page).waitFor({ timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.list).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=1 / 1', { timeout: 30000 })
    await page.waitForSelector('text=List memory 21', { timeout: 30000 })

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.allFilter).click()
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.pageLabel).waitFor({ timeout: 30000 })
    await page.waitForSelector('text=1 / 2', { timeout: 30000 })
    await page.waitForSelector('text=List memory 22', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.item).count()) === 20, 'Expected 20 memories on all/page1')

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.nextPageButton).click()
    await page.waitForSelector('text=2 / 2', { timeout: 30000 })
    await page.waitForSelector('text=Launch ownership note', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.item).count()) === 3, 'Expected 3 memories on all/page2')

    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.prevPageButton).click()
    await page.waitForSelector('text=1 / 2', { timeout: 30000 })
    await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.archivedFilter).click()
    await page.waitForSelector('text=List memory 22', { timeout: 30000 })
    await page.waitForSelector('text=List memory 05', { timeout: 30000 })
    assertSmoke((await page.getByTestId(MEMORIES_SMOKE_TEST_IDS.item).count()) === 4, 'Expected 4 archived memories')

    await page.screenshot({
      path: path.join(EVIDENCE_DIR, 'task-31-memories-list-real.png'),
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
    'task-31-memories-list-real-summary.txt',
    'task-31-memories-list-real-summary.json',
    'task-31-memories-list-real-http.json',
    'task-31-memories-list-real-seed.json',
    'task-31-memories-list-real.png',
    'task-31-memories-list-real-error.txt',
    'task-31-memories-list-real-backend.log',
  ].map((fileName) => rm(path.join(EVIDENCE_DIR, fileName), { force: true })))

  await runBuildWeb(FRONTEND_ROOT)

  const workspaceRoot = await mkdtemp(path.join(os.tmpdir(), 'memory-graph-memories-list-real-'))
  const backendPort = await findAvailablePort(Number(process.env.T31_BACKEND_PORT ?? '38310'))
  const backendBaseUrl = buildBaseUrl(backendPort)
  const configPath = await writeTempSettingsConfig(workspaceRoot, {
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:11434',
    ollamaModel: 'qwen2.5:14b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
  })
  const seedOutputPath = path.join(EVIDENCE_DIR, 'task-31-memories-list-real-seed.json')

  const seedPayload = await runSeedFixture({
    workspaceRoot,
    configPath,
    outputPath: seedOutputPath,
    repoRoot: REPO_ROOT,
    profile: 'memories_list',
  })
  const backend = startBackendService({
    workspaceRoot,
    repoRoot: REPO_ROOT,
    evidenceDir: EVIDENCE_DIR,
    logFileName: 'task-31-memories-list-real-backend.log',
    backendPort,
    extraEnv: {
      MEMORY_GRAPH_SETTINGS_PATH: configPath,
    },
  })

  try {
    const httpEvidence = await verifyHttpContract({ backendBaseUrl, seedPayload })
    const browserEvidence = await runBrowserFlow({ backendBaseUrl })

    const summaryPayload = {
      generated_at: new Date().toISOString(),
      command: 'npm --prefix frontend run qa:real-stack-smoke:memories:list',
      status: 'passed',
      backend_base_url: backendBaseUrl,
      config_path: configPath,
      profile: seedPayload.profile,
      total_memories: httpEvidence.allPage1.json?.total,
      active_total: httpEvidence.active.json?.total,
      archived_total: httpEvidence.archived.json?.total,
      page1_count: httpEvidence.allPage1.json?.memories?.length,
      page2_count: httpEvidence.allPage2.json?.memories?.length,
      final_url: browserEvidence.finalUrl,
      screenshot: '.sisyphus/evidence/task-31-memories-list-real.png',
      backend_log: '.sisyphus/evidence/task-31-memories-list-real-backend.log',
      seed_fixture: '.sisyphus/evidence/task-31-memories-list-real-seed.json',
    }

    const summaryText = [
      `generated_at=${summaryPayload.generated_at}`,
      `command=${summaryPayload.command}`,
      `status=${summaryPayload.status}`,
      `profile=${summaryPayload.profile}`,
      `total_memories=${summaryPayload.total_memories}`,
      `active_total=${summaryPayload.active_total}`,
      `archived_total=${summaryPayload.archived_total}`,
      `page1_count=${summaryPayload.page1_count}`,
      `page2_count=${summaryPayload.page2_count}`,
      `final_url=${summaryPayload.final_url}`,
      `config_path=${summaryPayload.config_path}`,
    ].join('\n')

    await writeFile(path.join(EVIDENCE_DIR, 'task-31-memories-list-real-summary.txt'), `${summaryText}\n`, 'utf8')
    await writeFile(path.join(EVIDENCE_DIR, 'task-31-memories-list-real-summary.json'), `${JSON.stringify(summaryPayload, null, 2)}\n`, 'utf8')
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-31-memories-list-real-http.json'),
      `${JSON.stringify({
        health: httpEvidence.health.json,
        active: httpEvidence.active.json,
        archived: httpEvidence.archived.json,
        all_page_1: httpEvidence.allPage1.json,
        all_page_2: httpEvidence.allPage2.json,
      }, null, 2)}\n`,
      'utf8'
    )

    process.stdout.write(`${summaryText}\n`)
  } catch (error) {
    await writeFile(
      path.join(EVIDENCE_DIR, 'task-31-memories-list-real-error.txt'),
      `${error.stack || error.message}\n`,
      'utf8'
    )
    throw error
  } finally {
    await stopPreviewServer(backend.child)
    await backend.flushLog()
    await rm(workspaceRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || error.message}\n`)
  process.exitCode = 1
})
