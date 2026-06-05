import { useEffect, useMemo, useState } from 'react'
import apiClient from '../api/client'
import { SETTINGS_SMOKE_TEST_IDS } from './SettingsPage.smoke-helpers'
import {
  DEFAULT_SECRET_STORAGE,
  buildSecretStorageStatusMessage,
  getConfigSaveBlockingMessage,
  normalizeSecretStorage,
  normalizeSettingsApiErrorMessage,
} from './settings-secret-storage'
import {
  DEFAULT_RUNTIME_DIAGNOSTICS,
  buildConfigSavedMessage,
  buildRuntimeDiagnosticsSummary,
  hasRuntimeDiagnostics,
  normalizeRuntimeDiagnostics,
} from './settings-runtime-diagnostics'
import './SettingsPage.css'

const DEFAULT_CONFIG = {
  llm_provider: 'openai',
  embedding_model: '',
  graph_backend: 'NetworkX + SQLite',
  vector_store_type: '',
  app_host: 'localhost',
  app_port: 8000,
  openai_base_url: 'https://api.openai.com/v1',
  openai_model: 'gpt-4o',
  openai_api_key_configured: false,
  anthropic_base_url: 'https://api.anthropic.com',
  anthropic_model: 'claude-sonnet-4-20250514',
  anthropic_api_key_configured: false,
  ollama_url: 'http://localhost:11434',
  ollama_model: 'qwen2.5:14b',
  secret_storage: DEFAULT_SECRET_STORAGE
}

const DEFAULT_FORM_DATA = {
  llm_provider: 'openai',
  openai_api_key: '',
  openai_base_url: 'https://api.openai.com/v1',
  openai_model: 'gpt-4o',
  anthropic_api_key: '',
  anthropic_base_url: 'https://api.anthropic.com',
  anthropic_model: 'claude-sonnet-4-20250514',
  ollama_url: 'http://localhost:11434',
  ollama_model: 'qwen2.5:14b'
}

const DEFAULT_VISUALIZATION = {
  defaultLayout: 'force',
  nodeSize: 8,
  showLabels: true
}
const VALID_VISUALIZATION_LAYOUTS = new Set(['force', 'circular', 'hierarchical', 'clustered'])
const VISUALIZATION_NODE_SIZE_MIN = 4
const VISUALIZATION_NODE_SIZE_MAX = 24

const DEFAULT_CONNECTION_STATUS = {
  success: false,
  providers: {},
  provider_errors: {},
  graph_store: false,
  vector_store: false,
  current_error: null,
  tested: false
}

const DEFAULT_RESTORE_DRY_RUN_OPTIONS = {
  clear_existing: true,
  reindex: true,
  reembed: false,
  batch_size: 32
}

const DEFAULT_REINDEX_OPTIONS = {
  reembed: false,
  batch_size: 32
}

const DEFAULT_RETRIEVAL_EVAL_RESULT = {
  success: false,
  summary: null,
  regressions: [],
  expectation_passes: [],
  expectation_failures: [],
  baseline_path: null,
  expectations_path: null,
  strict_passed: null
}

const WEB_OPERATION_NOTES = [
  {
    capability: '自动启动后端',
    status: 'disabled',
    webReplacement: '浏览器环境无法管理本地进程；请使用系统服务或手动启动后端。'
  },
  {
    capability: '最小化到托盘',
    status: 'disabled',
    webReplacement: '浏览器标签页不支持托盘行为；请使用浏览器固定标签或系统窗口管理。'
  },
  {
    capability: '系统开机自启动',
    status: 'disabled',
    webReplacement: '浏览器应用无法注册系统开机项；请通过系统任务计划器实现。'
  },
  {
    capability: '进程控制面板',
    status: 'disabled',
    webReplacement: '当前界面不直接控制进程；改为展示连接测试结果并依赖外部运维启动。'
  },
  {
    capability: '打开配置目录',
    status: 'degraded',
    webReplacement: '浏览器不可直接打开系统目录；请按部署文档手动进入配置目录。'
  }
]

function normalizeTextSetting(value, fallback) {
  return value?.trim() || fallback
}

function buildConfigPayload(formData) {
  const payload = {
    llm_provider: formData.llm_provider,
    openai_base_url: normalizeTextSetting(formData.openai_base_url, DEFAULT_FORM_DATA.openai_base_url),
    openai_model: normalizeTextSetting(formData.openai_model, DEFAULT_FORM_DATA.openai_model),
    anthropic_base_url: normalizeTextSetting(formData.anthropic_base_url, DEFAULT_FORM_DATA.anthropic_base_url),
    anthropic_model: normalizeTextSetting(formData.anthropic_model, DEFAULT_FORM_DATA.anthropic_model),
    ollama_url: normalizeTextSetting(formData.ollama_url, DEFAULT_FORM_DATA.ollama_url),
    ollama_model: normalizeTextSetting(formData.ollama_model, DEFAULT_FORM_DATA.ollama_model)
  }

  if (formData.openai_api_key.trim()) {
    payload.openai_api_key = formData.openai_api_key.trim()
  }

  if (formData.anthropic_api_key.trim()) {
    payload.anthropic_api_key = formData.anthropic_api_key.trim()
  }

  return payload
}

function parseStoredSettings(raw) {
  if (!raw) return {}

  try {
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function normalizeVisualizationSettings(input) {
  const defaultLayout = VALID_VISUALIZATION_LAYOUTS.has(input?.defaultLayout)
    ? input.defaultLayout
    : DEFAULT_VISUALIZATION.defaultLayout

  const parsedNodeSize = Number(input?.nodeSize)
  const nodeSize = Number.isFinite(parsedNodeSize)
    ? Math.min(VISUALIZATION_NODE_SIZE_MAX, Math.max(VISUALIZATION_NODE_SIZE_MIN, Math.round(parsedNodeSize)))
    : DEFAULT_VISUALIZATION.nodeSize

  const showLabels = typeof input?.showLabels === 'boolean'
    ? input.showLabels
    : DEFAULT_VISUALIZATION.showLabels

  return {
    defaultLayout,
    nodeSize,
    showLabels
  }
}

function readVisualizationSettings() {
  const parsed = parseStoredSettings(localStorage.getItem('memory_graph_settings'))
  return normalizeVisualizationSettings(parsed?.graph || {})
}

function writeVisualizationSettings(visualization) {
  const parsed = parseStoredSettings(localStorage.getItem('memory_graph_settings'))
  const currentGraph = parsed?.graph || {}
  const normalizedVisualization = normalizeVisualizationSettings(visualization)
  const next = {
    ...parsed,
    graph: {
      ...currentGraph,
      defaultLayout: normalizedVisualization.defaultLayout,
      nodeSize: normalizedVisualization.nodeSize,
      showLabels: normalizedVisualization.showLabels
    }
  }
  localStorage.setItem('memory_graph_settings', JSON.stringify(next))
}

function buildConnectionBadge(status, tested) {
  if (!tested) {
    return { className: 'settings-status settings-status--untested', text: '⏳ 未测试' }
  }
  if (status) {
    return { className: 'settings-status settings-status--success', text: '✅ 已连接' }
  }
  return { className: 'settings-status settings-status--failed', text: '❌ 失败' }
}

function formatDiagnosticsTime(value) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function normalizeBatchSize(value) {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return 32
  return Math.min(256, Math.max(1, Math.round(parsed)))
}

function buildRestoreParams({ dryRun, options }) {
  const normalizedBatchSize = normalizeBatchSize(options.batch_size)
  return new URLSearchParams({
    dry_run: String(Boolean(dryRun)),
    clear_existing: String(Boolean(options.clear_existing)),
    reindex: String(Boolean(options.reindex)),
    reembed: String(Boolean(options.reindex && options.reembed)),
    batch_size: String(normalizedBatchSize)
  })
}

function formatJsonBlock(value) {
  if (!value) return ''
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function normalizeRetrievalEvalResult(payload) {
  return {
    ...DEFAULT_RETRIEVAL_EVAL_RESULT,
    ...(payload && typeof payload === 'object' ? payload : {}),
    regressions: Array.isArray(payload?.regressions) ? payload.regressions : [],
    expectation_passes: Array.isArray(payload?.expectation_passes) ? payload.expectation_passes : [],
    expectation_failures: Array.isArray(payload?.expectation_failures) ? payload.expectation_failures : [],
  }
}

export default function SettingsPage() {
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)

  const [config, setConfig] = useState(DEFAULT_CONFIG)
  const [formData, setFormData] = useState(DEFAULT_FORM_DATA)
  const [visualization, setVisualization] = useState(DEFAULT_VISUALIZATION)
  const [connectionStatus, setConnectionStatus] = useState(DEFAULT_CONNECTION_STATUS)
  const [runtimeDiagnostics, setRuntimeDiagnostics] = useState(DEFAULT_RUNTIME_DIAGNOSTICS)
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false)
  const [diagnosticsError, setDiagnosticsError] = useState(null)
  const [restoreFile, setRestoreFile] = useState(null)
  const [exportingData, setExportingData] = useState(false)
  const [exportResult, setExportResult] = useState(null)
  const [exportError, setExportError] = useState(null)
  const [restoreDryRunning, setRestoreDryRunning] = useState(false)
  const [restoreDryRunOptions, setRestoreDryRunOptions] = useState(DEFAULT_RESTORE_DRY_RUN_OPTIONS)
  const [restoreDryRunResult, setRestoreDryRunResult] = useState(null)
  const [restoreDryRunError, setRestoreDryRunError] = useState(null)
  const [restoreRunning, setRestoreRunning] = useState(false)
  const [restoreResult, setRestoreResult] = useState(null)
  const [restoreError, setRestoreError] = useState(null)
  const [reindexing, setReindexing] = useState(false)
  const [reindexOptions, setReindexOptions] = useState(DEFAULT_REINDEX_OPTIONS)
  const [reindexResult, setReindexResult] = useState(null)
  const [reindexError, setReindexError] = useState(null)
  const [retrievalEvalRunning, setRetrievalEvalRunning] = useState(false)
  const [retrievalEvalResult, setRetrievalEvalResult] = useState(null)
  const [retrievalEvalError, setRetrievalEvalError] = useState(null)

  const isOpenAI = useMemo(() => formData.llm_provider === 'openai', [formData.llm_provider])
  const isAnthropic = useMemo(() => formData.llm_provider === 'anthropic', [formData.llm_provider])
  const isOllama = useMemo(() => formData.llm_provider === 'ollama', [formData.llm_provider])
  const secretStorageMessage = useMemo(
    () => buildSecretStorageStatusMessage(config.secret_storage),
    [config.secret_storage]
  )
  const hasDiagnostics = useMemo(
    () => hasRuntimeDiagnostics(runtimeDiagnostics),
    [runtimeDiagnostics]
  )
  const diagnosticsSummary = useMemo(
    () => buildRuntimeDiagnosticsSummary(runtimeDiagnostics),
    [runtimeDiagnostics]
  )

  async function loadRuntimeDiagnostics({ showError = true } = {}) {
    setDiagnosticsLoading(true)
    if (showError) {
      setDiagnosticsError(null)
    }

    try {
      const data = await apiClient.get('/diagnostics/runtime')
      const normalized = normalizeRuntimeDiagnostics(data)
      setRuntimeDiagnostics(normalized)
      setDiagnosticsError(null)
      return { ok: true, data: normalized }
    } catch (requestError) {
      const normalizedError = normalizeSettingsApiErrorMessage(requestError, '无法加载运行诊断')
      if (showError) {
        setDiagnosticsError(normalizedError)
      }
      return { ok: false, error: normalizedError }
    } finally {
      setDiagnosticsLoading(false)
    }
  }

  useEffect(() => {
    let mounted = true

    async function loadConfig() {
      setLoading(true)
      setError(null)

      try {
        const data = await apiClient.get('/config')
        if (!mounted) return

        setConfig({
          llm_provider: data?.llm_provider || 'openai',
          embedding_model: data?.embedding_model || '',
          graph_backend: data?.graph_backend || 'NetworkX + SQLite',
          vector_store_type: data?.vector_store_type || '',
          app_host: data?.app_host || 'localhost',
          app_port: data?.app_port || 8000,
          openai_base_url: data?.openai_base_url || 'https://api.openai.com/v1',
          openai_model: data?.openai_model || 'gpt-4o',
          openai_api_key_configured: data?.openai_api_key_configured ?? false,
          anthropic_base_url: data?.anthropic_base_url || 'https://api.anthropic.com',
          anthropic_model: data?.anthropic_model || 'claude-sonnet-4-20250514',
          anthropic_api_key_configured: data?.anthropic_api_key_configured ?? false,
          ollama_url: data?.ollama_url || 'http://localhost:11434',
          ollama_model: data?.ollama_model || 'qwen2.5:14b',
          secret_storage: normalizeSecretStorage(data?.secret_storage)
        })

        setFormData((current) => ({
          ...current,
          llm_provider: data?.llm_provider || 'openai',
          openai_base_url: data?.openai_base_url || 'https://api.openai.com/v1',
          openai_model: data?.openai_model || 'gpt-4o',
          anthropic_base_url: data?.anthropic_base_url || 'https://api.anthropic.com',
          anthropic_model: data?.anthropic_model || 'claude-sonnet-4-20250514',
          ollama_url: data?.ollama_url || 'http://localhost:11434',
          ollama_model: data?.ollama_model || 'qwen2.5:14b',
          openai_api_key: '',
          anthropic_api_key: ''
        }))

        setVisualization(readVisualizationSettings())
      } catch (requestError) {
        if (!mounted) return
        setError(normalizeSettingsApiErrorMessage(requestError, '无法加载配置，请确保后端服务正在运行'))
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    loadConfig()
    loadRuntimeDiagnostics({ showError: false })

    return () => {
      mounted = false
    }
  }, [])

  async function loadLatestConfig() {
    const data = await apiClient.get('/config')
    setConfig({
      llm_provider: data?.llm_provider || 'openai',
      embedding_model: data?.embedding_model || '',
      graph_backend: data?.graph_backend || 'NetworkX + SQLite',
      vector_store_type: data?.vector_store_type || '',
      app_host: data?.app_host || 'localhost',
      app_port: data?.app_port || 8000,
      openai_base_url: data?.openai_base_url || 'https://api.openai.com/v1',
      openai_model: data?.openai_model || 'gpt-4o',
      openai_api_key_configured: data?.openai_api_key_configured ?? false,
      anthropic_base_url: data?.anthropic_base_url || 'https://api.anthropic.com',
      anthropic_model: data?.anthropic_model || 'claude-sonnet-4-20250514',
      anthropic_api_key_configured: data?.anthropic_api_key_configured ?? false,
      ollama_url: data?.ollama_url || 'http://localhost:11434',
      ollama_model: data?.ollama_model || 'qwen2.5:14b',
      secret_storage: normalizeSecretStorage(data?.secret_storage)
    })
    setFormData((current) => ({
      ...current,
      llm_provider: data?.llm_provider || 'openai',
      openai_base_url: data?.openai_base_url || 'https://api.openai.com/v1',
      openai_model: data?.openai_model || 'gpt-4o',
      anthropic_base_url: data?.anthropic_base_url || 'https://api.anthropic.com',
      anthropic_model: data?.anthropic_model || 'claude-sonnet-4-20250514',
      ollama_url: data?.ollama_url || 'http://localhost:11434',
      ollama_model: data?.ollama_model || 'qwen2.5:14b',
      openai_api_key: '',
      anthropic_api_key: ''
    }))
  }

  async function handleTestConnection() {
    setTesting(true)
    setError(null)
    setSuccessMessage(null)
    setConnectionStatus((current) => ({ ...current, tested: false }))

    try {
      const data = await apiClient.post('/config/test-connection', buildConfigPayload(formData))
      setConnectionStatus({
        ...DEFAULT_CONNECTION_STATUS,
        ...data,
        tested: true
      })

      if (data?.success) {
        setSuccessMessage('连接测试成功！')
      } else {
        setError(data?.current_error || data?.error || '部分连接失败，请检查配置')
      }
    } catch (requestError) {
      setError(normalizeSettingsApiErrorMessage(requestError, '连接测试失败，请确保后端服务正在运行'))
      setConnectionStatus((current) => ({ ...current, tested: true }))
    } finally {
      setTesting(false)
    }
  }

  async function handleSaveConfig() {
    setError(null)
    setSuccessMessage(null)

    const blockedMessage = getConfigSaveBlockingMessage({
      formData,
      secretStorage: config.secret_storage
    })
    if (blockedMessage) {
      setError(blockedMessage)
      return
    }

    setSaving(true)

    try {
      await apiClient.put('/config', buildConfigPayload(formData))
      writeVisualizationSettings(visualization)
      await loadLatestConfig()
      const diagnosticsResult = await loadRuntimeDiagnostics({ showError: false })
      if (!diagnosticsResult?.ok) {
        setSuccessMessage('配置已保存，但运行诊断刷新失败，请手动刷新诊断确认运行态。')
        return
      }
      setSuccessMessage(buildConfigSavedMessage(diagnosticsResult.data))
    } catch (requestError) {
      setError(normalizeSettingsApiErrorMessage(requestError, '保存配置失败'))
    } finally {
      setSaving(false)
    }
  }

  async function handleExportData() {
    setExportingData(true)
    setExportError(null)
    setExportResult(null)

    try {
      const data = await apiClient.get('/data/export')
      const timestamp = new Date().toISOString().replace(/[:.]/g, '-')
      const fileName = `memory-graph-export-${timestamp}.json`
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const downloadUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = fileName
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(downloadUrl)

      const manifestCounts = data?.manifest?.counts
      const fallbackCounts = {
        memories: Array.isArray(data?.memories) ? data.memories.length : 0,
        entities: Array.isArray(data?.entities) ? data.entities.length : 0,
        relationships: Array.isArray(data?.relationships) ? data.relationships.length : 0
      }
      setExportResult({
        fileName,
        exportedAt: data?.manifest?.exported_at || new Date().toISOString(),
        counts: manifestCounts || fallbackCounts
      })
    } catch (requestError) {
      setExportError(normalizeSettingsApiErrorMessage(requestError, '导出失败'))
    } finally {
      setExportingData(false)
    }
  }

  async function handleRestoreDryRun() {
    if (!restoreFile) {
      setRestoreDryRunError('请先选择 restore JSON 文件')
      setRestoreDryRunResult(null)
      return
    }

    setRestoreDryRunning(true)
    setRestoreDryRunError(null)
    setRestoreDryRunResult(null)

    try {
      const formDataPayload = new FormData()
      formDataPayload.append('file', restoreFile)

      const params = buildRestoreParams({ dryRun: true, options: restoreDryRunOptions })

      const data = await apiClient.post(`/data/restore?${params.toString()}`, formDataPayload, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      setRestoreDryRunResult(data)
    } catch (requestError) {
      setRestoreDryRunError(normalizeSettingsApiErrorMessage(requestError, '恢复 dry-run 失败'))
    } finally {
      setRestoreDryRunning(false)
    }
  }

  async function handleRestoreApply() {
    if (!restoreFile) {
      setRestoreError('请先选择 restore JSON 文件')
      setRestoreResult(null)
      return
    }

    const normalizedBatchSize = normalizeBatchSize(restoreDryRunOptions.batch_size)
    const confirmed = window.confirm(
      [
        '将执行真实 restore（会写入本地存储）。',
        `clear_existing=${Boolean(restoreDryRunOptions.clear_existing)}`,
        `reindex=${Boolean(restoreDryRunOptions.reindex)}`,
        `reembed=${Boolean(restoreDryRunOptions.reindex && restoreDryRunOptions.reembed)}`,
        `batch_size=${normalizedBatchSize}`,
        '',
        '请确认已经完成导出备份，是否继续？'
      ].join('\n')
    )
    if (!confirmed) {
      return
    }

    setRestoreRunning(true)
    setRestoreError(null)
    setRestoreResult(null)
    setSuccessMessage(null)

    try {
      const formDataPayload = new FormData()
      formDataPayload.append('file', restoreFile)
      const params = buildRestoreParams({ dryRun: false, options: restoreDryRunOptions })

      const data = await apiClient.post(`/data/restore?${params.toString()}`, formDataPayload, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      setRestoreResult(data)
      setSuccessMessage('restore 执行完成，请检查恢复结果并确认关键检索路径。')
      await loadRuntimeDiagnostics({ showError: false })
    } catch (requestError) {
      setRestoreError(normalizeSettingsApiErrorMessage(requestError, 'restore 执行失败'))
    } finally {
      setRestoreRunning(false)
    }
  }

  async function handleReindex() {
    setReindexing(true)
    setReindexError(null)
    setReindexResult(null)

    try {
      const normalizedBatchSize = normalizeBatchSize(reindexOptions.batch_size)
      const params = new URLSearchParams({
        reembed: String(Boolean(reindexOptions.reembed)),
        batch_size: String(normalizedBatchSize)
      })
      const data = await apiClient.post(`/data/reindex?${params.toString()}`)
      setReindexResult(data)
    } catch (requestError) {
      setReindexError(normalizeSettingsApiErrorMessage(requestError, '重建索引失败'))
    } finally {
      setReindexing(false)
    }
  }

  async function handleRunRetrievalEval() {
    setRetrievalEvalRunning(true)
    setRetrievalEvalError(null)
    setRetrievalEvalResult(null)

    try {
      const data = await apiClient.get('/evals/retrieval')
      setRetrievalEvalResult(normalizeRetrievalEvalResult(data))
    } catch (requestError) {
      setRetrievalEvalError(normalizeSettingsApiErrorMessage(requestError, '检索评测执行失败'))
    } finally {
      setRetrievalEvalRunning(false)
    }
  }

  return (
    <section className="settings-page" aria-label="Settings page">
      <header className="settings-header">
        <h1>系统设置</h1>
        <p className="settings-subtitle">配置 AI 连接参数并管理 Web 端可用设置</p>
      </header>

      {loading ? (
        <div className="settings-state-panel" role="status">
          <div className="settings-spinner" />
          <span>加载配置中...</span>
        </div>
      ) : null}

      {!loading && error ? (
        <div
          className="settings-alert settings-alert--error"
          role="alert"
          data-testid={SETTINGS_SMOKE_TEST_IDS.globalErrorAlert}
        >
          {error}
        </div>
      ) : null}

      {!loading && successMessage ? (
        <div className="settings-alert settings-alert--success" role="status">
          {successMessage}
        </div>
      ) : null}

      {!loading ? (
        <div className="settings-content">
          <section className="settings-section">
            <div className="settings-section-head">
              <h2>运行诊断</h2>
              <button
                type="button"
                className="settings-secondary-btn"
                data-testid={SETTINGS_SMOKE_TEST_IDS.diagnosticsRefreshButton}
                onClick={() => loadRuntimeDiagnostics({ showError: true })}
                disabled={diagnosticsLoading}
              >
                {diagnosticsLoading ? '刷新中...' : '刷新诊断'}
              </button>
            </div>
            <div className="settings-card" data-testid={SETTINGS_SMOKE_TEST_IDS.diagnosticsSection}>
              <p className="settings-card-note">
                最近诊断时间：{formatDiagnosticsTime(runtimeDiagnostics.generated_at)}
              </p>
              <div
                className={[
                  diagnosticsSummary.tone === 'error'
                    ? 'settings-inline-alert settings-inline-alert--tight'
                    : 'settings-inline-note settings-inline-note--summary',
                  diagnosticsSummary.tone === 'warning' ? 'settings-inline-note--warning' : '',
                  diagnosticsSummary.tone === 'success' ? 'settings-inline-note--success' : '',
                ].filter(Boolean).join(' ')}
                role={diagnosticsSummary.tone === 'error' ? 'alert' : 'status'}
                data-testid={SETTINGS_SMOKE_TEST_IDS.diagnosticsSummary}
              >
                <div>{diagnosticsSummary.message}</div>
                {diagnosticsSummary.detail ? (
                  <div className="settings-diagnostics-summary-detail">{diagnosticsSummary.detail}</div>
                ) : null}
              </div>
              {diagnosticsError ? (
                <div className="settings-inline-alert" role="alert">
                  {diagnosticsError}
                </div>
              ) : null}
              <div className="settings-diagnostics-grid">
                {[
                  { key: 'service', label: '核心依赖', value: runtimeDiagnostics.status === 'healthy', tested: hasDiagnostics },
                  {
                    key: 'provider',
                    label: `Provider（${runtimeDiagnostics.checks?.provider?.current_provider || config.llm_provider || '-'}）`,
                    value: runtimeDiagnostics.checks?.provider?.ok,
                    tested: hasDiagnostics
                  },
                  {
                    key: 'graph',
                    label: '图存储',
                    value: runtimeDiagnostics.checks?.sqlite?.ok,
                    tested: hasDiagnostics
                  },
                  {
                    key: 'vector',
                    label: '向量索引',
                    value: runtimeDiagnostics.checks?.vector_store?.ok,
                    tested: hasDiagnostics
                  }
                ].map((item) => {
                  const badge = buildConnectionBadge(Boolean(item.value), item.tested)
                  return (
                    <div className="settings-connection-item" key={item.key}>
                      <span className="settings-connection-label">{item.label}</span>
                      <span className={badge.className}>{badge.text}</span>
                    </div>
                  )
                })}
              </div>
              {runtimeDiagnostics.checks?.provider?.current_error ? (
                <div className="settings-inline-note settings-inline-note--error">
                  当前 provider 错误：{runtimeDiagnostics.checks.provider.current_error}
                </div>
              ) : null}
              {runtimeDiagnostics.checks?.vector_store?.state ? (
                <div className="settings-inline-note">
                  向量状态：indexed={runtimeDiagnostics.checks.vector_store.state.indexed_documents ?? '-'}，stored=
                  {runtimeDiagnostics.checks.vector_store.state.stored_documents ?? '-'}，dimension_mismatch=
                  {String(runtimeDiagnostics.checks.vector_store.state.dimension_mismatch ?? false)}
                </div>
              ) : null}
              <div className="settings-task-chain-block" data-testid={SETTINGS_SMOKE_TEST_IDS.taskChainBlock}>
                <h3>Task Chain</h3>
                <div className="settings-inline-note">
                  状态：{runtimeDiagnostics.task_chain?.status || 'not_configured'}，已配置 source：
                  {runtimeDiagnostics.task_chain?.configured_sources ?? 0}
                </div>
                {runtimeDiagnostics.task_chain?.detail ? (
                  <div className="settings-inline-note settings-inline-note--error">
                    {runtimeDiagnostics.task_chain.detail}
                  </div>
                ) : null}
                {runtimeDiagnostics.task_chain?.sources?.length ? (
                  <ul className="settings-task-chain-list">
                    {runtimeDiagnostics.task_chain.sources.map((source, index) => (
                      <li key={source.source_id || `${source.workspace_id || 'source'}-${index}`}>
                        <div className="settings-task-chain-head">
                          <span className="settings-task-chain-label">{source.label || source.source_id || '未命名 source'}</span>
                          <span
                            className={`settings-task-chain-badge settings-task-chain-badge--${source.state_status || 'degraded'}`}
                          >
                            {source.state_status || 'degraded'}
                          </span>
                        </div>
                        <div className="settings-task-chain-meta">
                          system={source.source_system || '-'} | workspace={source.workspace_id || '-'} | records=
                          {source.record_count ?? 0} | conflicts={source.conflicts ?? 0} | deleted=
                          {source.deleted_records ?? 0} | last_pulled_seq={source.last_pulled_seq ?? 0}
                        </div>
                        {source.workspace_root ? (
                          <div className="settings-task-chain-path">root={source.workspace_root}</div>
                        ) : null}
                        {source.detail ? (
                          <div className="settings-task-chain-detail">{source.detail}</div>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="settings-empty-note">当前没有可诊断的 sync source</p>
                )}
              </div>
              <div className="settings-failure-block" data-testid={SETTINGS_SMOKE_TEST_IDS.recentFailuresBlock}>
                <h3>Recent Failures</h3>
                {runtimeDiagnostics.recent_failures?.length ? (
                  <ul className="settings-failure-list">
                    {runtimeDiagnostics.recent_failures.map((item, index) => (
                      <li key={`${item.component || 'unknown'}-${item.last_seen_at || index}`}>
                        <span className="settings-failure-component">{item.component || 'unknown'}</span>
                        <span className="settings-failure-detail">{item.detail || '-'}</span>
                        <span className="settings-failure-meta">
                          source={item.source || '-'} | last_seen={formatDiagnosticsTime(item.last_seen_at)} | count=
                          {item.count ?? 1}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="settings-empty-note">最近没有失败记录</p>
                )}
              </div>
            </div>
          </section>

          <section className="settings-section">
            <h2>当前状态</h2>
            <div className="settings-status-grid">
              <article className="settings-status-card">
                <span className="settings-status-label">LLM 提供商</span>
                <span className="settings-status-value">{config.llm_provider || '-'}</span>
              </article>
              <article className="settings-status-card">
                <span className="settings-status-label">嵌入模型</span>
                <span className="settings-status-value">{config.embedding_model || '-'}</span>
              </article>
              <article className="settings-status-card">
                <span className="settings-status-label">图存储</span>
                <span className="settings-status-value">{config.graph_backend || '-'}</span>
              </article>
              <article className="settings-status-card">
                <span className="settings-status-label">向量存储</span>
                <span className="settings-status-value">{config.vector_store_type || '-'}</span>
              </article>
            </div>
          </section>

          <section className="settings-section">
            <h2>连接测试</h2>
            <div className="settings-card">
              <p className="settings-card-note">测试当前表单值，不会自动保存配置。</p>
              <div className="settings-connection-grid">
                {[
                  { key: 'openai', label: 'OpenAI', value: connectionStatus.providers?.openai ?? false },
                  { key: 'anthropic', label: 'Anthropic', value: connectionStatus.providers?.anthropic ?? false },
                  { key: 'ollama', label: 'Ollama', value: connectionStatus.providers?.ollama ?? false },
                  { key: 'graph_store', label: '图存储', value: connectionStatus.graph_store },
                  { key: 'vector_store', label: '向量存储', value: connectionStatus.vector_store }
                ].map((item) => {
                  const badge = buildConnectionBadge(item.value, connectionStatus.tested)
                  return (
                    <div className="settings-connection-item" key={item.key}>
                      <span className="settings-connection-label">{item.label}</span>
                      <span className={badge.className}>{badge.text}</span>
                    </div>
                  )
                })}
              </div>
              <button
                type="button"
                className="settings-primary-btn settings-test-btn"
                onClick={handleTestConnection}
                disabled={testing}
              >
                {testing ? '测试中...' : '测试所有连接'}
              </button>
            </div>
          </section>

          <section className="settings-section">
            <h2>LLM 配置</h2>
            <div className="settings-card settings-form-grid">
              <div
                className={`${config.secret_storage?.available ? 'settings-inline-note' : 'settings-inline-alert'} settings-field--full`}
                role={config.secret_storage?.available ? 'status' : 'alert'}
                data-testid={SETTINGS_SMOKE_TEST_IDS.secretStorageStatus}
              >
                {secretStorageMessage}
              </div>
              <label className="settings-field">
                <span>LLM 提供商</span>
                <select
                  id="settings-llm-provider"
                  value={formData.llm_provider}
                  onChange={(event) => setFormData((current) => ({ ...current, llm_provider: event.target.value }))}
                >
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic Claude</option>
                  <option value="ollama">Ollama（本地）</option>
                </select>
              </label>

              {isOpenAI ? (
                <>
                  <label className="settings-field">
                    <span>OpenAI API Key</span>
                    <input
                      type="password"
                      value={formData.openai_api_key}
                      placeholder={config.openai_api_key_configured ? '已配置，留空则保持不变' : 'sk-...'}
                      onChange={(event) => setFormData((current) => ({ ...current, openai_api_key: event.target.value }))}
                    />
                  </label>
                  <label className="settings-field">
                    <span>兼容接口 Base URL</span>
                    <input
                      id="settings-openai-base-url"
                      type="text"
                      value={formData.openai_base_url}
                      placeholder="https://api.openai.com/v1"
                      onChange={(event) => setFormData((current) => ({ ...current, openai_base_url: event.target.value }))}
                    />
                  </label>
                  <label className="settings-field">
                    <span>模型</span>
                    <input
                      id="settings-openai-model"
                      type="text"
                      value={formData.openai_model}
                      placeholder="gpt-4o / glm-4.7 / 其他 OpenAI-compatible 模型名"
                      onChange={(event) => setFormData((current) => ({ ...current, openai_model: event.target.value }))}
                    />
                  </label>
                </>
              ) : null}

              {isAnthropic ? (
                <>
                  <label className="settings-field">
                    <span>Anthropic API Key</span>
                    <input
                      type="password"
                      value={formData.anthropic_api_key}
                      placeholder={config.anthropic_api_key_configured ? '已配置，留空则保持不变' : 'sk-ant-...'}
                      onChange={(event) => setFormData((current) => ({ ...current, anthropic_api_key: event.target.value }))}
                    />
                  </label>
                  <label className="settings-field">
                    <span>模型</span>
                    <input
                      id="settings-anthropic-base-url"
                      type="text"
                      value={formData.anthropic_base_url}
                      placeholder="https://api.anthropic.com"
                      onChange={(event) => setFormData((current) => ({ ...current, anthropic_base_url: event.target.value }))}
                    />
                  </label>
                  <label className="settings-field">
                    <span>模型</span>
                    <input
                      id="settings-anthropic-model"
                      type="text"
                      value={formData.anthropic_model}
                      placeholder="claude-sonnet-4-20250514 / 其他 Anthropic 模型名"
                      onChange={(event) => setFormData((current) => ({ ...current, anthropic_model: event.target.value }))}
                    />
                  </label>
                </>
              ) : null}

              {isOllama ? (
                <>
                  <label className="settings-field">
                    <span>Ollama URL</span>
                    <input
                      id="settings-ollama-url"
                      type="text"
                      value={formData.ollama_url}
                      placeholder="http://localhost:11434"
                      onChange={(event) => setFormData((current) => ({ ...current, ollama_url: event.target.value }))}
                    />
                  </label>
                  <label className="settings-field">
                    <span>模型</span>
                    <input
                      id="settings-ollama-model"
                      type="text"
                      value={formData.ollama_model}
                      placeholder="llama2"
                      onChange={(event) => setFormData((current) => ({ ...current, ollama_model: event.target.value }))}
                    />
                  </label>
                </>
              ) : null}
            </div>
          </section>

          <section className="settings-section">
            <h2>图存储</h2>
            <div className="settings-card">
              <p>当前 Web 版固定使用 <strong>{config.graph_backend}</strong>，不再提供 Neo4j 兼容配置。</p>
            </div>
          </section>

          <section className="settings-section">
            <h2>可视化配置（Web）</h2>
            <div className="settings-card settings-form-grid settings-form-grid--2col">
              <label className="settings-field">
                <span>默认布局</span>
                <select
                  id="settings-visual-layout"
                  value={visualization.defaultLayout}
                  onChange={(event) => setVisualization((current) => ({ ...current, defaultLayout: event.target.value }))}
                >
                  <option value="force">力导向</option>
                  <option value="circular">圆形布局</option>
                  <option value="hierarchical">层级布局</option>
                  <option value="clustered">聚类布局</option>
                </select>
              </label>

              <label className="settings-field">
                <span>节点尺寸：{visualization.nodeSize}</span>
                <input
                  id="settings-visual-node-size"
                  type="range"
                  min="4"
                  max="24"
                  step="1"
                  value={visualization.nodeSize}
                  onChange={(event) => setVisualization((current) => ({ ...current, nodeSize: Number(event.target.value) }))}
                />
              </label>

              <label className="settings-checkbox settings-field--full">
                <input
                  id="settings-visual-show-labels"
                  type="checkbox"
                  checked={visualization.showLabels}
                  onChange={(event) => setVisualization((current) => ({ ...current, showLabels: event.target.checked }))}
                />
                <span>显示节点标签</span>
              </label>
            </div>
          </section>

          <section className="settings-section">
            <h2>数据恢复操作（Settings）</h2>
            <div className="settings-card settings-recovery-grid">
              <div className="settings-recovery-block" data-testid={SETTINGS_SMOKE_TEST_IDS.exportBlock}>
                <h3>导出快照</h3>
                <p className="settings-card-note">调用现有 `/data/export`，下载完整 JSON 快照。</p>
                {exportError ? (
                  <div className="settings-inline-alert" role="alert">
                    {exportError}
                  </div>
                ) : null}
                {exportResult ? (
                  <div className="settings-inline-note" data-testid={SETTINGS_SMOKE_TEST_IDS.exportResult}>
                    导出成功：{exportResult.fileName} | memories={exportResult.counts?.memories ?? 0} | entities=
                    {exportResult.counts?.entities ?? 0} | relationships={exportResult.counts?.relationships ?? 0} | exported_at=
                    {formatDiagnosticsTime(exportResult.exportedAt)}
                  </div>
                ) : null}
                <button
                  type="button"
                  className="settings-secondary-btn"
                  data-testid={SETTINGS_SMOKE_TEST_IDS.exportButton}
                  onClick={handleExportData}
                  disabled={exportingData}
                >
                  {exportingData ? '导出中...' : '导出数据快照'}
                </button>
              </div>

              <div className="settings-recovery-block" data-testid={SETTINGS_SMOKE_TEST_IDS.restoreDryRunBlock}>
                <h3>恢复预检（dry-run）</h3>
                <p className="settings-card-note">调用 `/data/restore?dry_run=true`，仅做 payload 校验，不写入存储。</p>
                <label className="settings-field">
                  <span>Restore JSON 文件</span>
                  <input
                    data-testid={SETTINGS_SMOKE_TEST_IDS.restoreDryRunFile}
                    type="file"
                    accept="application/json,.json"
                    onChange={(event) => {
                      const selected = event.target.files?.[0] || null
                      setRestoreFile(selected)
                      setRestoreDryRunError(null)
                      setRestoreDryRunResult(null)
                      setRestoreError(null)
                      setRestoreResult(null)
                    }}
                  />
                </label>
                <div className="settings-recovery-controls">
                  <label className="settings-checkbox">
                    <input
                      type="checkbox"
                      checked={restoreDryRunOptions.clear_existing}
                      onChange={(event) =>
                        setRestoreDryRunOptions((current) => ({ ...current, clear_existing: event.target.checked }))
                      }
                    />
                    <span>预览时包含 clear_existing</span>
                  </label>
                  <label className="settings-checkbox">
                    <input
                      type="checkbox"
                      checked={restoreDryRunOptions.reindex}
                      onChange={(event) =>
                        setRestoreDryRunOptions((current) => ({
                          ...current,
                          reindex: event.target.checked,
                          reembed: event.target.checked ? current.reembed : false
                        }))
                      }
                    />
                    <span>预览时包含 reindex</span>
                  </label>
                  <label className="settings-checkbox">
                    <input
                      type="checkbox"
                      checked={restoreDryRunOptions.reembed}
                      disabled={!restoreDryRunOptions.reindex}
                      onChange={(event) =>
                        setRestoreDryRunOptions((current) => ({ ...current, reembed: event.target.checked }))
                      }
                    />
                    <span>预览时包含 reembed</span>
                  </label>
                  <label className="settings-field settings-recovery-number">
                    <span>batch_size</span>
                    <input
                      type="number"
                      min="1"
                      max="256"
                      value={restoreDryRunOptions.batch_size}
                      onChange={(event) =>
                        setRestoreDryRunOptions((current) => ({ ...current, batch_size: event.target.value }))
                      }
                    />
                  </label>
                </div>
                {restoreDryRunError ? (
                  <div className="settings-inline-alert" role="alert">
                    {restoreDryRunError}
                  </div>
                ) : null}
                {restoreDryRunResult ? (
                  <pre
                    className="settings-json-result"
                    aria-label="restore dry-run result"
                    data-testid={SETTINGS_SMOKE_TEST_IDS.restoreDryRunResult}
                  >
                    {formatJsonBlock(restoreDryRunResult)}
                  </pre>
                ) : null}
                <button
                  type="button"
                  className="settings-secondary-btn"
                  data-testid={SETTINGS_SMOKE_TEST_IDS.restoreDryRunButton}
                  onClick={handleRestoreDryRun}
                  disabled={restoreDryRunning}
                >
                  {restoreDryRunning ? '预检中...' : '执行 restore dry-run'}
                </button>
              </div>

              <div className="settings-recovery-block">
                <h3>执行恢复（写入）</h3>
                <p className="settings-card-note">调用 `/data/restore` 执行真实写入；参数与上方 dry-run 保持一致。</p>
                <div className="settings-recovery-risk" role="alert">
                  风险提示：若 `clear_existing=true`，当前数据会先清空再恢复。建议先执行导出快照与 dry-run。
                </div>
                <div className="settings-recovery-controls">
                  <div className="settings-recovery-summary">
                    clear_existing={String(Boolean(restoreDryRunOptions.clear_existing))} | reindex=
                    {String(Boolean(restoreDryRunOptions.reindex))} | reembed=
                    {String(Boolean(restoreDryRunOptions.reindex && restoreDryRunOptions.reembed))} | batch_size=
                    {normalizeBatchSize(restoreDryRunOptions.batch_size)}
                  </div>
                </div>
                {restoreError ? (
                  <div className="settings-inline-alert" role="alert">
                    {restoreError}
                  </div>
                ) : null}
                {restoreResult ? (
                  <pre className="settings-json-result" aria-label="restore result">
                    {formatJsonBlock(restoreResult)}
                  </pre>
                ) : null}
                <button
                  type="button"
                  className="settings-secondary-btn settings-secondary-btn--danger"
                  onClick={handleRestoreApply}
                  disabled={restoreRunning}
                >
                  {restoreRunning ? '恢复执行中...' : '执行 restore（写入）'}
                </button>
              </div>

              <div className="settings-recovery-block" data-testid={SETTINGS_SMOKE_TEST_IDS.reindexBlock}>
                <h3>重建索引</h3>
                <p className="settings-card-note">调用现有 `/data/reindex`，可选重算 embedding。</p>
                <div className="settings-recovery-controls">
                  <label className="settings-checkbox">
                    <input
                      type="checkbox"
                      checked={reindexOptions.reembed}
                      onChange={(event) => setReindexOptions((current) => ({ ...current, reembed: event.target.checked }))}
                    />
                    <span>启用 reembed</span>
                  </label>
                  <label className="settings-field settings-recovery-number">
                    <span>batch_size</span>
                    <input
                      type="number"
                      min="1"
                      max="256"
                      value={reindexOptions.batch_size}
                      onChange={(event) => setReindexOptions((current) => ({ ...current, batch_size: event.target.value }))}
                    />
                  </label>
                </div>
                {reindexError ? (
                  <div className="settings-inline-alert" role="alert">
                    {reindexError}
                  </div>
                ) : null}
                {reindexResult ? (
                  <pre
                    className="settings-json-result"
                    aria-label="reindex result"
                    data-testid={SETTINGS_SMOKE_TEST_IDS.reindexResult}
                  >
                    {formatJsonBlock(reindexResult)}
                  </pre>
                ) : null}
                <button
                  type="button"
                  className="settings-secondary-btn"
                  data-testid={SETTINGS_SMOKE_TEST_IDS.reindexButton}
                  onClick={handleReindex}
                  disabled={reindexing}
                >
                  {reindexing ? '重建中...' : '执行 reindex'}
                </button>
              </div>
            </div>
          </section>

          <section className="settings-section">
            <h2>检索评测（Retrieval Eval）</h2>
            <div className="settings-card settings-eval-block">
              <p className="settings-card-note">
                调用 `/api/v1/evals/retrieval`，展示 local/global/hybrid 指标、回归对比和阈值检查结果。
              </p>
              <button
                type="button"
                className="settings-secondary-btn"
                onClick={handleRunRetrievalEval}
                disabled={retrievalEvalRunning}
              >
                {retrievalEvalRunning ? '评测中...' : '运行 retrieval eval'}
              </button>

              {retrievalEvalError ? (
                <div className="settings-inline-alert" role="alert">
                  {retrievalEvalError}
                </div>
              ) : null}

              {retrievalEvalResult ? (
                <div className="settings-eval-result">
                  <div className="settings-eval-meta">
                    <span>strict_passed: {String(Boolean(retrievalEvalResult.strict_passed))}</span>
                    <span>baseline: {retrievalEvalResult.baseline_path || '-'}</span>
                    <span>expectations: {retrievalEvalResult.expectations_path || '-'}</span>
                  </div>

                  {retrievalEvalResult?.summary?.strategies ? (
                    <div className="settings-eval-strategy-grid">
                      {Object.entries(retrievalEvalResult.summary.strategies).map(([strategy, metrics]) => (
                        <article className="settings-eval-strategy-card" key={strategy}>
                          <h3>{strategy}</h3>
                          <div>recall@k: {metrics?.recall_at_k ?? '-'}</div>
                          <div>empty_result_rate: {metrics?.empty_result_rate ?? '-'}</div>
                          <div>avg_latency_ms: {metrics?.avg_latency_ms ?? '-'}</div>
                          <div>p95_latency_ms: {metrics?.p95_latency_ms ?? '-'}</div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="settings-empty-note">未返回 strategy 指标。</p>
                  )}

                  <div className="settings-eval-lists">
                    <div className="settings-eval-list-block">
                      <h3>Regressions</h3>
                      {retrievalEvalResult.regressions.length ? (
                        <ul className="settings-eval-list settings-eval-list--error">
                          {retrievalEvalResult.regressions.map((item, index) => (
                            <li key={`${item}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="settings-empty-note">无回归项。</p>
                      )}
                    </div>

                    <div className="settings-eval-list-block">
                      <h3>Expectation Failures</h3>
                      {retrievalEvalResult.expectation_failures.length ? (
                        <ul className="settings-eval-list settings-eval-list--error">
                          {retrievalEvalResult.expectation_failures.map((item, index) => (
                            <li key={`${item}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="settings-empty-note">无阈值失败项。</p>
                      )}
                    </div>

                    <div className="settings-eval-list-block">
                      <h3>Expectation Passes</h3>
                      {retrievalEvalResult.expectation_passes.length ? (
                        <ul className="settings-eval-list">
                          {retrievalEvalResult.expectation_passes.map((item, index) => (
                            <li key={`${item}-${index}`}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <p className="settings-empty-note">暂无阈值通过项。</p>
                      )}
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          </section>

          <section className="settings-section">
            <h2>运维约束与替代方案</h2>
            <div className="settings-card">
              <table className="settings-mapping-table">
                <thead>
                  <tr>
                    <th>能力</th>
                    <th>当前状态</th>
                    <th>说明 / 替代方案</th>
                  </tr>
                </thead>
                <tbody>
                  {WEB_OPERATION_NOTES.map((item) => (
                    <tr key={item.capability}>
                      <td>{item.capability}</td>
                      <td>
                        <span className={`settings-map-badge settings-map-badge--${item.status}`}>{item.status}</span>
                      </td>
                      <td>{item.webReplacement}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <div className="settings-actions">
            <button
              type="button"
              className="settings-primary-btn settings-save-btn"
              onClick={handleSaveConfig}
              disabled={saving}
            >
              {saving ? '保存中...' : '保存配置'}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  )
}
