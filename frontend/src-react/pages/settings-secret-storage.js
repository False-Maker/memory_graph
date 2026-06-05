export const DEFAULT_SECRET_STORAGE = Object.freeze({
  available: false,
  storage_type: 'environment_only',
  backend: null,
  message: '',
  fallback_env_vars: ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY']
})

function normalizeFallbackEnvVars(value) {
  if (!Array.isArray(value)) {
    return [...DEFAULT_SECRET_STORAGE.fallback_env_vars]
  }

  const normalized = value
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => item.trim())

  return normalized.length ? normalized : [...DEFAULT_SECRET_STORAGE.fallback_env_vars]
}

export function normalizeSecretStorage(value) {
  return {
    available: Boolean(value?.available),
    storage_type: value?.storage_type === 'system_keyring' ? 'system_keyring' : 'environment_only',
    backend: typeof value?.backend === 'string' && value.backend.trim() ? value.backend.trim() : null,
    message: typeof value?.message === 'string' ? value.message.trim() : '',
    fallback_env_vars: normalizeFallbackEnvVars(value?.fallback_env_vars)
  }
}

function formatFallbackEnvVars(value) {
  return normalizeFallbackEnvVars(value).join(' / ')
}

export function hasPendingSecretValues(formData) {
  return Boolean(formData?.openai_api_key?.trim() || formData?.anthropic_api_key?.trim())
}

export function buildSecretStorageUnavailableMessage(secretStorage) {
  const normalized = normalizeSecretStorage(secretStorage)
  const envVars = formatFallbackEnvVars(normalized.fallback_env_vars)

  return (
    `当前环境没有可用系统密钥库${normalized.backend ? `（${normalized.backend}）` : ''}；` +
    `设置页不能保存新的 API Key。请清空 API Key 输入框后仅保存其他字段，或改用 ${envVars} 环境变量。`
  )
}

export function buildSecretStorageStatusMessage(secretStorage) {
  const normalized = normalizeSecretStorage(secretStorage)
  if (normalized.available) {
    return (
      `系统密钥库可用${normalized.backend ? `（${normalized.backend}）` : ''}；` +
      '新的 API Key 会写入系统密钥库，不会落盘到 config/settings.yaml。'
    )
  }

  return buildSecretStorageUnavailableMessage(normalized)
}

export function getConfigSaveBlockingMessage({ formData, secretStorage }) {
  if (!normalizeSecretStorage(secretStorage).available && hasPendingSecretValues(formData)) {
    return buildSecretStorageUnavailableMessage(secretStorage)
  }

  return null
}

export function normalizeSettingsApiErrorMessage(error, fallback) {
  const payload = error?.response?.data

  if (payload?.code === 'secure_secret_store_unavailable') {
    return buildSecretStorageUnavailableMessage(payload?.secret_storage || payload)
  }

  return payload?.detail || payload?.message || error?.message || fallback
}
