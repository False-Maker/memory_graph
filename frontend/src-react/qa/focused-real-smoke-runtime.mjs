import { spawn } from 'node:child_process'
import { mkdir, writeFile } from 'node:fs/promises'
import http from 'node:http'
import https from 'node:https'
import path from 'node:path'

import { applyBrowserLibEnv, buildBrowserLibDir } from './settings-playwright-runtime.mjs'

export function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export function assertSmoke(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

export function requestJson(url, options = {}) {
  const { body, timeoutMs = 5000, ...requestOptions } = options
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http
    const request = client.request(url, requestOptions, (response) => {
      const chunks = []
      response.on('data', (chunk) => chunks.push(chunk))
      response.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8')
        let json = null
        try {
          json = raw ? JSON.parse(raw) : null
        } catch {
          json = null
        }
        resolve({
          statusCode: response.statusCode ?? 0,
          raw,
          json,
        })
      })
    })
    request.on('error', reject)
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error(`timeout requesting ${url}`))
    })
    if (body) {
      request.write(body)
    }
    request.end()
  })
}

export async function waitForStatus(url, predicate, timeoutMs = 30000) {
  const start = Date.now()
  let lastError = null
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await requestJson(url)
      if (predicate(response)) {
        return response
      }
      lastError = new Error(`unexpected status ${response.statusCode}: ${response.raw}`)
    } catch (error) {
      lastError = error
    }
    await delay(500)
  }
  throw lastError || new Error(`Timed out waiting for ${url}`)
}

export function startBackendService({
  workspaceRoot,
  repoRoot,
  evidenceDir,
  logFileName,
  backendPort,
  extraEnv = {},
}) {
  const logChunks = []
  const child = spawn(
    'python3',
    ['-m', 'uvicorn', 'src.api.main:app', '--host', '127.0.0.1', '--port', String(backendPort)],
    {
      cwd: workspaceRoot,
      env: {
        ...process.env,
        PYTHONPATH: repoRoot,
        ...extraEnv,
      },
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false,
    }
  )

  child.stdout.on('data', (chunk) => {
    logChunks.push(String(chunk))
  })
  child.stderr.on('data', (chunk) => {
    logChunks.push(String(chunk))
  })

  return {
    child,
    async flushLog() {
      await mkdir(evidenceDir, { recursive: true })
      await writeFile(path.join(evidenceDir, logFileName), logChunks.join(''), 'utf8')
    },
  }
}

export function buildTempSettingsYaml({
  provider = 'openai',
  openaiBaseUrl = 'https://api.openai.com/v1',
  openaiModel = 'gpt-4o',
  anthropicBaseUrl = 'https://api.anthropic.com',
  anthropicModel = 'claude-sonnet-4-20250514',
  ollamaUrl = 'http://localhost:11434',
  ollamaModel = 'qwen2.5:14b',
  embeddingModel = 'Qwen/Qwen3-Embedding-0.6B',
  embeddingProviderPreference = 'local_first',
  vectorType = 'faiss',
  faissPersistDirectory = './data/faiss',
  appHost = '127.0.0.1',
  appPort = 8000,
} = {}) {
  return [
    'llm:',
    `  provider: "${provider}"`,
    '  openai:',
    '    api_key: ""',
    `    base_url: "${openaiBaseUrl}"`,
    `    model: "${openaiModel}"`,
    '  anthropic:',
    '    api_key: ""',
    `    base_url: "${anthropicBaseUrl}"`,
    `    model: "${anthropicModel}"`,
    '  ollama:',
    `    url: "${ollamaUrl}"`,
    `    model: "${ollamaModel}"`,
    'embedding:',
    `  model: "${embeddingModel}"`,
    `  provider_preference: "${embeddingProviderPreference}"`,
    'database:',
    '  vector:',
    `    type: "${vectorType}"`,
    '    faiss:',
    `      persist_directory: "${faissPersistDirectory}"`,
    'app:',
    `  host: "${appHost}"`,
    `  port: ${appPort}`,
    '',
  ].join('\n')
}

export async function writeTempSettingsConfig(workspaceRoot, options = {}) {
  const configDir = path.join(workspaceRoot, 'config')
  await mkdir(configDir, { recursive: true })
  const configPath = path.join(configDir, 'settings.yaml')
  await writeFile(configPath, buildTempSettingsYaml(options), 'utf8')
  return configPath
}

export function buildSmokeBrowserEnv(frontendRoot, env = process.env) {
  return applyBrowserLibEnv(buildBrowserLibDir(frontendRoot), env)
}
