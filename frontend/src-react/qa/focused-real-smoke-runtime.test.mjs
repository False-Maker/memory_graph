import test from 'node:test'
import assert from 'node:assert/strict'

import { buildTempSettingsYaml } from './focused-real-smoke-runtime.mjs'

test('buildTempSettingsYaml returns stable default openai-oriented config', () => {
  const yaml = buildTempSettingsYaml()

  assert.match(yaml, /provider: "openai"/)
  assert.match(yaml, /base_url: "https:\/\/api\.openai\.com\/v1"/)
  assert.match(yaml, /model: "gpt-4o"/)
  assert.match(yaml, /type: "faiss"/)
  assert.match(yaml, /persist_directory: "\.\/data\/faiss"/)
})

test('buildTempSettingsYaml applies focused override values', () => {
  const yaml = buildTempSettingsYaml({
    provider: 'ollama',
    ollamaUrl: 'http://127.0.0.1:38231',
    ollamaModel: 'qwen2.5:32b',
    embeddingProviderPreference: 'remote_only',
    faissPersistDirectory: './data/faiss-search-real-smoke',
    appPort: 38230,
  })

  assert.match(yaml, /provider: "ollama"/)
  assert.match(yaml, /url: "http:\/\/127\.0\.0\.1:38231"/)
  assert.match(yaml, /model: "qwen2\.5:32b"/)
  assert.match(yaml, /provider_preference: "remote_only"/)
  assert.match(yaml, /persist_directory: "\.\/data\/faiss-search-real-smoke"/)
  assert.match(yaml, /port: 38230/)
})
