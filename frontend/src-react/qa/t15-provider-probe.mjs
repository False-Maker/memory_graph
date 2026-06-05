import { spawn } from 'node:child_process'
import http from 'node:http'
import https from 'node:https'
import path from 'node:path'

import {
  PROVIDER_SMOKE_PROVIDERS,
  resolveApiKeyEnvValue,
} from './t15-provider-real-stack-smoke-helpers.mjs'

const REPO_ROOT = path.resolve(process.cwd(), '..')

function resolveCommand(command) {
  if (process.platform === 'win32' && command === 'python3') {
    return 'python'
  }
  return command
}

function requestStatus(url, timeoutMs = 3000) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https:') ? https : http
    const request = client.get(url, { agent: false }, (response) => {
      resolve(response.statusCode ?? 0)
      response.resume()
    })
    request.on('error', reject)
    request.setTimeout(timeoutMs, () => {
      request.destroy(new Error('timeout'))
    })
  })
}

async function runPythonJson(script, env = process.env) {
  return await new Promise((resolve, reject) => {
    const child = spawn(resolveCommand('python3'), ['-c', script], {
      cwd: REPO_ROOT,
      env: { ...env, PYTHONPATH: '.' },
      stdio: ['ignore', 'pipe', 'pipe'],
      shell: false
    })

    let stdout = ''
    let stderr = ''
    child.stdout.on('data', (chunk) => {
      stdout += String(chunk)
    })
    child.stderr.on('data', (chunk) => {
      stderr += String(chunk)
    })

    child.on('exit', (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `python exited with code ${code}`))
        return
      }

      try {
        resolve(JSON.parse(stdout))
      } catch (error) {
        reject(error)
      }
    })

    child.on('error', reject)
  })
}

export async function loadProviderProbe(overrides = {}) {
  const probe = await runPythonJson(`
import json
from src.core.config import get_settings

s = get_settings()
print(json.dumps({
    "openai": {
        "apiKeyConfigured": bool(s.llm.openai.api_key),
        "baseUrl": s.llm.openai.base_url,
        "model": s.llm.openai.model,
    },
    "anthropic": {
        "apiKeyConfigured": bool(s.llm.anthropic.api_key),
        "model": s.llm.anthropic.model,
    },
    "ollama": {
        "url": s.llm.ollama.url,
        "model": s.llm.ollama.model,
    },
}))
  `)

  const ollamaUrl = overrides.url || probe?.ollama?.url
  if (probe?.ollama) {
    probe.ollama.url = ollamaUrl
  }
  if (typeof ollamaUrl === 'string' && ollamaUrl) {
    try {
      const status = await requestStatus(`${ollamaUrl.replace(/\/$/, '')}/api/tags`)
      probe.ollama.reachable = status === 200
    } catch {
      probe.ollama.reachable = false
    }
  }

  return probe
}

function buildProviderConnectionPayload(provider, overrides = {}, env = process.env) {
  return {
    provider,
    overrides: {
      model: overrides.model || '',
      url: overrides.url || '',
      baseUrl: overrides.baseUrl || '',
      apiKeyEnv: overrides.apiKeyEnv || '',
    },
    resolvedApiKey: resolveApiKeyEnvValue(overrides, env) || '',
  }
}

export async function loadProviderConnectionProbe(
  providerOverrides = {},
  env = process.env,
  providers = PROVIDER_SMOKE_PROVIDERS
) {
  const results = {}

  for (const provider of providers) {
    const overrides = providerOverrides[provider] || {}
    const payload = buildProviderConnectionPayload(provider, overrides, env)
    results[provider] = await runPythonJson(
      `
import asyncio
import json
import os

from src.core.config import get_settings
from src.core.llm_manager import LLMManager

payload = json.loads(os.environ["T15_PROVIDER_CONNECTION_PAYLOAD"])
settings = get_settings()
config_dict = settings.model_dump()
provider = payload["provider"]
overrides = payload.get("overrides", {})
resolved_api_key = payload.get("resolvedApiKey", "")

config_dict["llm"]["provider"] = provider

if provider == "openai":
    if overrides.get("baseUrl"):
        config_dict["llm"]["openai"]["base_url"] = overrides["baseUrl"]
    if overrides.get("model"):
        config_dict["llm"]["openai"]["model"] = overrides["model"]
    if resolved_api_key:
        config_dict["llm"]["openai"]["api_key"] = resolved_api_key
elif provider == "anthropic":
    if overrides.get("baseUrl"):
        config_dict["llm"]["anthropic"]["base_url"] = overrides["baseUrl"]
    if overrides.get("model"):
        config_dict["llm"]["anthropic"]["model"] = overrides["model"]
    if resolved_api_key:
        config_dict["llm"]["anthropic"]["api_key"] = resolved_api_key
elif provider == "ollama":
    if overrides.get("url"):
        config_dict["llm"]["ollama"]["url"] = overrides["url"]
    if overrides.get("model"):
        config_dict["llm"]["ollama"]["model"] = overrides["model"]

updated_settings = type(settings)(**config_dict)
manager = LLMManager(settings=updated_settings)

async def main():
    provider_impl = manager.provider
    try:
        ok = await provider_impl.test_connection()
        print(json.dumps({
            "checked": True,
            "ok": bool(ok),
            "error": getattr(provider_impl, "last_error", None) or "",
        }))
    except Exception as exc:
        print(json.dumps({
            "checked": True,
            "ok": False,
            "error": str(exc),
        }))
    finally:
        await manager.close()

asyncio.run(main())
      `,
      {
        ...env,
        T15_PROVIDER_CONNECTION_PAYLOAD: JSON.stringify(payload),
      }
    )
  }

  return results
}
