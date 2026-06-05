import { spawn } from 'node:child_process'
import http from 'node:http'
import https from 'node:https'
import path from 'node:path'
import { writeFile } from 'node:fs/promises'

export const SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV = 'SETTINGS_SMOKE_MATRIX_SKIP_BUILD'
export const SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV = 'SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW'
export const SETTINGS_SMOKE_MATRIX_BASE_URL_ENV = 'SETTINGS_SMOKE_MATRIX_BASE_URL'
export const SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV = 'SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH'
export const SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV = 'SETTINGS_SMOKE_MATRIX_SKIP_BROWSER'
export const SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV = 'SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT'

const DEFAULT_PLAYWRIGHT_PREVIEW_PORT_STARTS = Object.freeze({
  t7: 4233,
  t8: 4243,
  t9: 4253,
  t10: 4263,
  t11: 4173,
  t13: 4183,
  t18: 4273,
  t12: 4193,
  t19: 4203,
  t20: 4213,
  t21: 4223,
})

function normalizeEnvValue(value) {
  return typeof value === 'string' ? value.trim() : ''
}

export function buildBaseUrl(port) {
  return `http://127.0.0.1:${port}`
}

export function getDefaultPlaywrightPreviewStartPort(taskId) {
  return DEFAULT_PLAYWRIGHT_PREVIEW_PORT_STARTS[normalizeEnvValue(taskId)] || 4173
}

export function resolvePlaywrightPreviewStartPort(taskId, envVarName, env = process.env) {
  const override = normalizeEnvValue(env?.[envVarName])
  if (override) {
    const parsed = Number(override)
    if (!Number.isInteger(parsed) || parsed <= 0) {
      throw new Error(`Invalid preview port override for ${envVarName}: ${override}`)
    }
    return parsed
  }

  return getDefaultPlaywrightPreviewStartPort(taskId)
}

export function previewServerOutputIndicatesReady(text) {
  return typeof text === 'string' && text.includes('Local:')
}

export function resolveCommand(command) {
  if (process.platform === 'win32' && command === 'npm') {
    return 'npm.cmd'
  }
  return command
}

export function buildBrowserLibDir(frontendRoot) {
  const repoRoot = path.resolve(frontendRoot, '..')
  return path.resolve(repoRoot, '.cache', 'browser-libs', 'extracted', 'usr', 'lib', 'x86_64-linux-gnu')
}

export function applyBrowserLibEnv(browserLibDir, env = process.env) {
  if (process.platform === 'win32') {
    return { ...env }
  }

  const nextEnv = { ...env }
  nextEnv.LD_LIBRARY_PATH = nextEnv.LD_LIBRARY_PATH
    ? `${browserLibDir}:${nextEnv.LD_LIBRARY_PATH}`
    : browserLibDir
  return nextEnv
}

export function shouldSkipSettingsSmokeBuild(env = process.env) {
  return normalizeEnvValue(env[SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV]) === '1'
}

export function shouldSkipSettingsSmokePreview(env = process.env) {
  return normalizeEnvValue(env[SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV]) === '1'
}

export function shouldSkipSettingsSmokeBrowser(env = process.env) {
  return normalizeEnvValue(env[SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV]) === '1'
}

export function getSettingsSmokeMatrixBaseUrl(env = process.env) {
  return normalizeEnvValue(env[SETTINGS_SMOKE_MATRIX_BASE_URL_ENV])
}

export function getSettingsSmokeMatrixPreviewLogPath(env = process.env) {
  return normalizeEnvValue(env[SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV])
}

export function getSettingsSmokeMatrixBrowserWsEndpoint(env = process.env) {
  return normalizeEnvValue(env[SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV])
}

export function buildSettingsSmokeMatrixChildEnv(env = process.env, options = {}) {
  const nextEnv = {
    ...env,
    [SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV]: '1',
  }

  const baseUrl = normalizeEnvValue(options.baseUrl)
  const previewLogPath = normalizeEnvValue(options.previewLogPath)
  if (baseUrl || previewLogPath) {
    nextEnv[SETTINGS_SMOKE_MATRIX_SKIP_PREVIEW_ENV] = '1'
    if (baseUrl) {
      nextEnv[SETTINGS_SMOKE_MATRIX_BASE_URL_ENV] = baseUrl
    }
    if (previewLogPath) {
      nextEnv[SETTINGS_SMOKE_MATRIX_PREVIEW_LOG_PATH_ENV] = previewLogPath
    }
  }

  const browserWsEndpoint = normalizeEnvValue(options.browserWsEndpoint)
  if (browserWsEndpoint) {
    nextEnv[SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV] = '1'
    nextEnv[SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV] = browserWsEndpoint
  }

  return nextEnv
}

export function resolveSettingsSmokeBaseUrl(port, env = process.env) {
  if (shouldSkipSettingsSmokePreview(env)) {
    const baseUrl = getSettingsSmokeMatrixBaseUrl(env)
    if (!baseUrl) {
      throw new Error(
        `Missing shared preview base URL: ${SETTINGS_SMOKE_MATRIX_BASE_URL_ENV}`
      )
    }
    return baseUrl
  }

  return buildBaseUrl(port)
}

export async function writeSharedSettingsSmokePreviewLog(previewLogPath, env = process.env) {
  const baseUrl = getSettingsSmokeMatrixBaseUrl(env)
  if (!baseUrl) {
    throw new Error(
      `Missing shared preview base URL: ${SETTINGS_SMOKE_MATRIX_BASE_URL_ENV}`
    )
  }

  const sharedPreviewLogPath = getSettingsSmokeMatrixPreviewLogPath(env)
  const lines = [
    `[settings-playwright] shared preview reused via ${baseUrl}`,
    '[settings-playwright] preview server owned by qa:settings-playwright:matrix',
  ]
  if (sharedPreviewLogPath) {
    lines.push(
      `[settings-playwright] shared_preview_log=${path.basename(sharedPreviewLogPath)}`
    )
  }

  await writeFile(previewLogPath, `${lines.join('\n')}\n`, 'utf8')
}

export async function openSettingsSmokeBrowser(browserType, env = process.env) {
  if (shouldSkipSettingsSmokeBrowser(env)) {
    const wsEndpoint = getSettingsSmokeMatrixBrowserWsEndpoint(env)
    if (!wsEndpoint) {
      throw new Error(
        `Missing shared browser ws endpoint: ${SETTINGS_SMOKE_MATRIX_BROWSER_WS_ENDPOINT_ENV}`
      )
    }

    process.stdout.write(
      `[settings-playwright] reusing browser via ${SETTINGS_SMOKE_MATRIX_SKIP_BROWSER_ENV}=1\n`
    )
    return await browserType.connect(wsEndpoint)
  }

  return await browserType.launch()
}

export async function withSettingsSmokeContext(browser, run) {
  const context = await browser.newContext()
  try {
    return await run(context)
  } finally {
    await context.close()
  }
}

export async function withSettingsSmokePage(context, run) {
  const page = await context.newPage()
  try {
    return await run(page)
  } finally {
    await page.close()
  }
}

export async function resetSettingsSmokePage(page, options = {}) {
  if (options.clearRoutes !== false) {
    await page.unrouteAll({ behavior: 'wait' })
  }
  await page.goto('about:blank', { waitUntil: 'load' })
}

export function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function getStatusCode(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http
    const request = client.get(url, { agent: false }, (response) => {
      resolve(response.statusCode ?? 0)
      response.resume()
    })
    request.on('error', reject)
    request.setTimeout(3000, () => {
      request.destroy(new Error('timeout'))
    })
  })
}

export async function waitForServerReady(url, timeoutMs = 30000) {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const status = await getStatusCode(url)
      if (status >= 200 && status < 500) {
        return
      }
    } catch {
      // retry
    }
    await delay(500)
  }
  throw new Error(`Timed out waiting for preview server: ${url}`)
}

export async function waitForProcessExit(child, timeoutMs = 5000) {
  if (!child || child.exitCode !== null) return
  await new Promise((resolve) => {
    const timer = setTimeout(resolve, timeoutMs)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve()
    })
  })
}

export async function isPortAvailable(port) {
  return await new Promise((resolve) => {
    const server = http.createServer()
    server.unref()
    server.on('error', () => resolve(false))
    server.listen({ host: '127.0.0.1', port }, () => {
      server.close(() => resolve(true))
    })
  })
}

export async function findAvailablePort(startPort, attempts = 10) {
  for (let offset = 0; offset < attempts; offset += 1) {
    const port = startPort + offset
    if (await isPortAvailable(port)) {
      return port
    }
  }

  throw new Error(`Could not find an available preview port starting from ${startPort}`)
}

export function startPreviewServer({ frontendRoot, previewLogPath, port }) {
  let ready = false
  let resolveReady = null
  let rejectReady = null
  const readyPromise = new Promise((resolve, reject) => {
    resolveReady = resolve
    rejectReady = reject
  })

  const child = spawn(
    resolveCommand('npm'),
    ['run', 'preview', '--', '--strictPort', '--host', '127.0.0.1', '--port', String(port)],
    {
      cwd: frontendRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false
    }
  )

  child.stdout.on('data', (chunk) => {
    const text = String(chunk)
    process.stdout.write(`[preview] ${text}`)
    if (!ready && previewServerOutputIndicatesReady(text)) {
      ready = true
      resolveReady?.()
    }
  })
  child.stderr.on('data', (chunk) => {
    process.stderr.write(`[preview] ${chunk}`)
  })

  child.on('error', (error) => {
    if (!ready) {
      rejectReady?.(error)
    }
  })
  child.on('exit', (code, signal) => {
    if (!ready) {
      rejectReady?.(
        new Error(
          `preview exited before ready (code=${code ?? 'null'}, signal=${signal ?? 'null'})`
        )
      )
    }
  })

  const logChunks = []
  child.stdout.on('data', (chunk) => {
    logChunks.push(String(chunk))
  })
  child.stderr.on('data', (chunk) => {
    logChunks.push(String(chunk))
  })

  return {
    child,
    waitUntilReady: async () => {
      await readyPromise
    },
    flushLog: async () => {
      if (!previewLogPath) return
      await writeFile(previewLogPath, logChunks.join(''), 'utf8')
    }
  }
}

export async function waitForManagedPreviewServerReady(previewServer, url, timeoutMs = 30000) {
  await previewServer.waitUntilReady()
  await waitForServerReady(url, timeoutMs)
}

export async function runBuildWeb(frontendRoot) {
  await new Promise((resolve, reject) => {
    const child = spawn(resolveCommand('npm'), ['run', 'build:web'], {
      cwd: frontendRoot,
      stdio: 'inherit',
      shell: false
    })

    child.on('exit', (code) => {
      if (code === 0) {
        resolve()
        return
      }
      reject(new Error(`build:web failed with exit code ${code}`))
    })

    child.on('error', reject)
  })
}

export async function ensureSettingsSmokeBuild(frontendRoot, env = process.env) {
  if (shouldSkipSettingsSmokeBuild(env)) {
    process.stdout.write(
      `[settings-playwright] skipping build:web because ${SETTINGS_SMOKE_MATRIX_SKIP_BUILD_ENV}=1\n`
    )
    return
  }

  await runBuildWeb(frontendRoot)
}

export async function stopPreviewServer(child) {
  if (!child || child.killed) return

  if (process.platform === 'win32') {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/pid', String(child.pid), '/t', '/f'], {
        stdio: 'ignore',
        shell: false
      })
      killer.on('exit', () => resolve())
      killer.on('error', () => resolve())
    })
    child.stdout?.destroy()
    child.stderr?.destroy()
    return
  }

  child.kill('SIGTERM')
  await waitForProcessExit(child)
  if (child.exitCode === null) {
    child.kill('SIGKILL')
    await waitForProcessExit(child, 1000)
  }
  child.stdout?.destroy()
  child.stderr?.destroy()
}
