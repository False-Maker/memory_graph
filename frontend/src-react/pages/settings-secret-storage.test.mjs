import test from 'node:test'
import assert from 'node:assert/strict'

import {
  DEFAULT_SECRET_STORAGE,
  buildSecretStorageStatusMessage,
  buildSecretStorageUnavailableMessage,
  getConfigSaveBlockingMessage,
  hasPendingSecretValues,
  normalizeSecretStorage,
  normalizeSettingsApiErrorMessage,
} from './settings-secret-storage.js'

test('normalizeSecretStorage returns stable defaults', () => {
  assert.deepEqual(normalizeSecretStorage(null), DEFAULT_SECRET_STORAGE)
})

test('buildSecretStorageStatusMessage describes available keyring backend', () => {
  const message = buildSecretStorageStatusMessage({
    available: true,
    storage_type: 'system_keyring',
    backend: 'keyring.backends.SecretService.Keyring',
  })

  assert.match(message, /系统密钥库可用/)
  assert.match(message, /SecretService/)
  assert.match(message, /config\/settings\.yaml/)
})

test('buildSecretStorageUnavailableMessage includes fallback env vars', () => {
  const message = buildSecretStorageUnavailableMessage({
    available: false,
    storage_type: 'environment_only',
    fallback_env_vars: ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY'],
  })

  assert.match(message, /不能保存新的 API Key/)
  assert.match(message, /OPENAI_API_KEY \/ ANTHROPIC_API_KEY/)
})

test('hasPendingSecretValues detects user-entered secrets only', () => {
  assert.equal(hasPendingSecretValues({ openai_api_key: '  sk-test  ' }), true)
  assert.equal(hasPendingSecretValues({ anthropic_api_key: '   ' }), false)
})

test('getConfigSaveBlockingMessage blocks saving new secrets without keyring', () => {
  const message = getConfigSaveBlockingMessage({
    formData: { openai_api_key: 'sk-test', anthropic_api_key: '' },
    secretStorage: { available: false, fallback_env_vars: ['OPENAI_API_KEY'] },
  })

  assert.match(message, /OPENAI_API_KEY/)
})

test('normalizeSettingsApiErrorMessage maps structured secret store errors to user guidance', () => {
  const message = normalizeSettingsApiErrorMessage(
    {
      response: {
        data: {
          code: 'secure_secret_store_unavailable',
          secret_storage: {
            available: false,
            fallback_env_vars: ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY'],
          },
        },
      },
    },
    '保存配置失败'
  )

  assert.match(message, /设置页不能保存新的 API Key/)
  assert.match(message, /OPENAI_API_KEY \/ ANTHROPIC_API_KEY/)
})
