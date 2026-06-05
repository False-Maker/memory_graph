export const DEFAULT_RUNTIME_DIAGNOSTICS = Object.freeze({
  status: 'unknown',
  generated_at: null,
  checks: {
    config: { ok: false },
    provider: {
      ok: false,
      current_provider: null,
      providers: {},
      provider_errors: {},
      current_error: null
    },
    sqlite: { ok: false },
    vector_store: { ok: false, state: null }
  },
  task_chain: {
    status: 'not_configured',
    configured_sources: 0,
    sources: [],
    detail: null
  },
  recent_failures: []
})

const CORE_CHECK_LABELS = Object.freeze({
  config: '配置',
  sqlite: '图存储',
  vector_store: '向量索引'
})

function normalizeObject(value) {
  return value && typeof value === 'object' ? value : {}
}

function normalizeProviderCheck(value) {
  const normalized = normalizeObject(value)
  return {
    ok: Boolean(normalized.ok),
    current_provider: typeof normalized.current_provider === 'string' && normalized.current_provider.trim()
      ? normalized.current_provider.trim()
      : null,
    providers: normalizeObject(normalized.providers),
    provider_errors: normalizeObject(normalized.provider_errors),
    current_error: typeof normalized.current_error === 'string' && normalized.current_error.trim()
      ? normalized.current_error.trim()
      : null
  }
}

function normalizeVectorStoreCheck(value) {
  const normalized = normalizeObject(value)
  return {
    ok: Boolean(normalized.ok),
    state: normalized.state && typeof normalized.state === 'object'
      ? normalized.state
      : DEFAULT_RUNTIME_DIAGNOSTICS.checks.vector_store.state
  }
}

function normalizeTaskChain(value) {
  const normalized = normalizeObject(value)
  return {
    status: typeof normalized.status === 'string' && normalized.status.trim()
      ? normalized.status.trim()
      : DEFAULT_RUNTIME_DIAGNOSTICS.task_chain.status,
    configured_sources: Number.isFinite(Number(normalized.configured_sources))
      ? Number(normalized.configured_sources)
      : DEFAULT_RUNTIME_DIAGNOSTICS.task_chain.configured_sources,
    sources: Array.isArray(normalized.sources) ? normalized.sources : [],
    detail: typeof normalized.detail === 'string' && normalized.detail.trim()
      ? normalized.detail.trim()
      : null
  }
}

function normalizeRecentFailures(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeRuntimeDiagnostics(value) {
  const normalized = normalizeObject(value)
  const checks = normalizeObject(normalized.checks)

  return {
    ...DEFAULT_RUNTIME_DIAGNOSTICS,
    ...normalized,
    status: typeof normalized.status === 'string' && normalized.status.trim()
      ? normalized.status.trim()
      : DEFAULT_RUNTIME_DIAGNOSTICS.status,
    generated_at: typeof normalized.generated_at === 'string' && normalized.generated_at.trim()
      ? normalized.generated_at.trim()
      : null,
    checks: {
      config: { ...DEFAULT_RUNTIME_DIAGNOSTICS.checks.config, ...normalizeObject(checks.config), ok: Boolean(checks.config?.ok) },
      provider: normalizeProviderCheck(checks.provider),
      sqlite: { ...DEFAULT_RUNTIME_DIAGNOSTICS.checks.sqlite, ...normalizeObject(checks.sqlite), ok: Boolean(checks.sqlite?.ok) },
      vector_store: normalizeVectorStoreCheck(checks.vector_store)
    },
    task_chain: normalizeTaskChain(normalized.task_chain),
    recent_failures: normalizeRecentFailures(normalized.recent_failures)
  }
}

export function hasRuntimeDiagnostics(runtimeDiagnostics) {
  return normalizeRuntimeDiagnostics(runtimeDiagnostics).status !== 'unknown'
}

export function getFailedRuntimeDiagnosticsChecks(runtimeDiagnostics) {
  const normalized = normalizeRuntimeDiagnostics(runtimeDiagnostics)
  const failedChecks = []

  if (!normalized.checks.config.ok) {
    failedChecks.push(CORE_CHECK_LABELS.config)
  }
  if (!normalized.checks.provider.ok) {
    failedChecks.push(
      normalized.checks.provider.current_provider
        ? `Provider（${normalized.checks.provider.current_provider}）`
        : 'Provider'
    )
  }
  if (!normalized.checks.sqlite.ok) {
    failedChecks.push(CORE_CHECK_LABELS.sqlite)
  }
  if (!normalized.checks.vector_store.ok) {
    failedChecks.push(CORE_CHECK_LABELS.vector_store)
  }

  return failedChecks
}

function buildProviderGuidance(normalized) {
  const provider = normalized.checks.provider.current_provider
  const error = normalized.checks.provider.current_error
  if (normalized.checks.provider.ok && !error) return ''
  if (!provider && !error) return ''
  return `建议：到 Settings 检查 ${provider || '当前 provider'} 的 API key / base URL / model，必要时重新执行连接测试。`
}

function buildVectorStoreGuidance(normalized) {
  const state = normalized.checks.vector_store.state
  if (!state || typeof state !== 'object') return ''
  if (state.dimension_mismatch) {
    return '建议：当前向量索引维度不一致，先到 Settings 执行 reindex，再重试检索或导入。'
  }
  return ''
}

function buildTaskChainGuidance(normalized) {
  if (normalized.task_chain.status !== 'degraded') return ''
  return '建议：到 Inbox 的“外部记忆源”页签检查 source 路径、冲突目录和最近一次 push/pull/sync 结果。'
}

function buildRecentFailureGuidance(normalized) {
  if (!normalized.recent_failures.length) return ''
  return '建议：优先处理 recent failures 中最新一条，再刷新运行诊断确认是否恢复。'
}

function buildAttentionDetails(normalized) {
  const details = []
  if (normalized.task_chain.status === 'degraded') {
    details.push(`Task Chain：${normalized.task_chain.detail || '有 source 需要处理'}`)
  }
  if (normalized.recent_failures.length > 0) {
    details.push(`最近失败记录 ${normalized.recent_failures.length} 条`)
  }
  for (const item of [
    buildProviderGuidance(normalized),
    buildVectorStoreGuidance(normalized),
    buildTaskChainGuidance(normalized),
    buildRecentFailureGuidance(normalized),
  ]) {
    if (item) details.push(item)
  }
  return details.join('；')
}

export function buildRuntimeDiagnosticsSummary(runtimeDiagnostics) {
  const normalized = normalizeRuntimeDiagnostics(runtimeDiagnostics)
  const failedChecks = getFailedRuntimeDiagnosticsChecks(normalized)

  if (normalized.status === 'unknown') {
    return {
      tone: 'neutral',
      message: '尚未获取运行诊断。',
      detail: ''
    }
  }

  if (failedChecks.length > 0) {
    const details = []
    if (normalized.checks.provider.current_error) {
      details.push(`当前 Provider 错误：${normalized.checks.provider.current_error}`)
    }
    const vectorGuidance = buildVectorStoreGuidance(normalized)
    if (vectorGuidance) {
      details.push(vectorGuidance)
    }
    const providerGuidance = buildProviderGuidance(normalized)
    if (providerGuidance) {
      details.push(providerGuidance)
    }
    const taskChainGuidance = buildTaskChainGuidance(normalized)
    if (taskChainGuidance) {
      details.push(taskChainGuidance)
    }
    const recentFailureGuidance = buildRecentFailureGuidance(normalized)
    if (recentFailureGuidance) {
      details.push(recentFailureGuidance)
    }
    if (normalized.recent_failures.length > 0) {
      details.push(`最近失败记录 ${normalized.recent_failures.length} 条`)
    }

    return {
      tone: 'error',
      message: `核心运行依赖未通过诊断：${failedChecks.join(' / ')}。`,
      detail: details.join('；')
    }
  }

  const attentionDetail = buildAttentionDetails(normalized)
  if (attentionDetail) {
    return {
      tone: 'warning',
      message: '核心运行依赖健康，但仍有待处理项。',
      detail: attentionDetail
    }
  }

  return {
    tone: 'success',
    message: '核心运行依赖健康，当前没有待处理诊断项。',
    detail: normalized.task_chain.status === 'not_configured'
      ? 'Task Chain 未配置，不影响当前默认 Web 主链路。'
      : ''
  }
}

export function buildConfigSavedMessage(runtimeDiagnostics) {
  const normalized = normalizeRuntimeDiagnostics(runtimeDiagnostics)
  const failedChecks = getFailedRuntimeDiagnosticsChecks(normalized)

  if (normalized.status === 'unknown') {
    return '配置已保存，运行诊断尚未刷新。'
  }

  if (failedChecks.length > 0) {
    return `配置已保存，但运行诊断仍未通过：${failedChecks.join(' / ')}。`
  }

  if (buildAttentionDetails(normalized)) {
    return '配置已保存，但运行诊断仍有待处理项。'
  }

  return '配置已保存，运行诊断已刷新。'
}
