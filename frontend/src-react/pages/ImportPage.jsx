import { useEffect, useMemo, useState } from 'react'
import apiClient, { importApi } from '../api/client'
import DirectoryImportResultPanel from '../components/DirectoryImportResultPanel'
import ImportRunHistoryPanel from '../components/ImportRunHistoryPanel'
import { IMPORT_SMOKE_TEST_IDS } from './ImportPage.smoke-helpers'
import { buildImportRuntimeDiagnosticsSummary } from './import-runtime-diagnostics'
import { DEFAULT_RUNTIME_DIAGNOSTICS, normalizeRuntimeDiagnostics } from './settings-runtime-diagnostics'
import './ImportPage.css'

const DIRECTORY_EXTENSIONS = ['.txt', '.md', '.json', '.pdf']
const DIRECTORY_IMPORT_RUN_LIMIT = 10
const SOURCE_FORM_STORAGE_KEY = 'memory_graph_import_source_form'
const DEFAULT_SOURCE_FORM = {
  source_id: '',
  label: '',
  source_system: '',
  workspace_id: '',
  workspace_root: '',
  source_paths_text: ''
}
function normalizeErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
}

function buildTextImportFile(content) {
  return new File([content], 'text-input.txt', { type: 'text/plain' })
}

function buildWordCount(content) {
  return content
    .trim()
    .split(/\s+/)
    .filter(Boolean).length
}

function parseDirectoryExtensions(value) {
  if (!value) return DIRECTORY_EXTENSIONS
  const normalized = String(value)
    .split(',')
    .map((item) => item.trim().toLowerCase())
    .filter(Boolean)
    .map((item) => (item.startsWith('.') ? item : `.${item}`))
  return normalized.length > 0 ? Array.from(new Set(normalized)) : DIRECTORY_EXTENSIONS
}

function normalizeImportRunsResponse(response) {
  if (Array.isArray(response)) return response
  if (Array.isArray(response?.runs)) return response.runs
  if (Array.isArray(response?.items)) return response.items
  if (Array.isArray(response?.data)) return response.data
  return []
}

function getDirectoryScanMatchedCount(result) {
  if (typeof result?.matched === 'number') return result.matched
  if (typeof result?.attempted === 'number') return result.attempted
  if (Array.isArray(result?.conversation_files)) return result.conversation_files.length
  return 0
}

function getDirectoryScanSkippedCount(result) {
  if (typeof result?.skipped === 'number') return result.skipped
  if (Array.isArray(result?.skipped_files)) return result.skipped_files.length
  return 0
}

function normalizeSourceForm(input) {
  return {
    source_id: input?.source_id?.trim() || '',
    label: input?.label?.trim() || '',
    source_system: input?.source_system?.trim() || '',
    workspace_id: input?.workspace_id?.trim() || '',
    workspace_root: input?.workspace_root?.trim() || '',
    source_paths_text: input?.source_paths_text?.trim() || '',
  }
}

function readSourceForm() {
  try {
    const raw = localStorage.getItem(SOURCE_FORM_STORAGE_KEY)
    if (!raw) return DEFAULT_SOURCE_FORM
    return normalizeSourceForm(JSON.parse(raw))
  } catch {
    return DEFAULT_SOURCE_FORM
  }
}

function writeSourceForm(form) {
  localStorage.setItem(SOURCE_FORM_STORAGE_KEY, JSON.stringify(normalizeSourceForm(form)))
}

function parseSourcePathLines(text) {
  return String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
}

function buildSourcePreviewPayload(form) {
  return {
    source_system: form.source_system.trim() || 'external',
    workspace_id: form.workspace_id.trim() || 'default',
    workspace_root: form.workspace_root.trim() || undefined,
    source_paths: parseSourcePathLines(form.source_paths_text),
  }
}

function buildSourceSettingPayload(form) {
  return {
    label: form.label.trim() || undefined,
    source_system: form.source_system.trim() || 'external',
    workspace_id: form.workspace_id.trim() || 'default',
    workspace_root: form.workspace_root.trim() || undefined,
    source_paths: parseSourcePathLines(form.source_paths_text),
  }
}

function buildSourceSettingLabel(setting) {
  return setting?.label || `${setting?.source_system || 'external'}:${setting?.workspace_id || 'default'}`
}

function formatDiagnosticsTime(value) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function buildSourceStatusBadge(status) {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'healthy') {
    return { className: 'import-diagnostics-badge import-diagnostics-badge--healthy', label: 'healthy' }
  }
  if (normalized === 'not_configured') {
    return { className: 'import-diagnostics-badge import-diagnostics-badge--neutral', label: 'not_configured' }
  }
  return { className: 'import-diagnostics-badge import-diagnostics-badge--degraded', label: normalized || 'degraded' }
}

function buildSourceRetryGuidance(source) {
  const conflicts = Number(source?.conflicts ?? 0)
  if (conflicts > 0) {
    return '检测到冲突记录：先在外部源处理冲突，再执行任务链重试。'
  }
  const detail = String(source?.detail || '').toLowerCase()
  if (detail.includes('state file not found') || detail.includes('workspace_root')) {
    return '当前 source 配置不完整：先在“外部记忆源”页签修正路径并重新预览后保存。'
  }
  return '该 source 需要关注：先检查路径/权限，再按任务链流程执行重试。'
}

function formFromSourceSetting(setting) {
  return normalizeSourceForm({
    source_id: setting?.source_id || '',
    label: setting?.label || '',
    source_system: setting?.source_system || '',
    workspace_id: setting?.workspace_id || '',
    workspace_root: setting?.workspace_root || '',
    source_paths_text: Array.isArray(setting?.source_paths) ? setting.source_paths.join('\n') : '',
  })
}

function buildImportRunId(run) {
  return run?.id || run?.run_id || null
}

function buildSourceOperationLabel(kind) {
  if (kind === 'pull') return '拉取'
  if (kind === 'sync') return '双向同步'
  if (kind === 'restore') return '恢复'
  return '推送'
}

function buildSourceOperationAttention(result) {
  if (!result) return null
  const pushSummary = result.operation_kind === 'sync' ? result.push : result.summary
  const pullSummary = result.operation_kind === 'sync' ? result.pull : result.summary

  const pushAttention = Boolean(pushSummary?.needs_attention)
  const pushConflict = Boolean(pushSummary?.needs_conflict_resolution)
  const pushRetry = Boolean(pushSummary?.needs_retry)
  const pullAttention = Boolean(pullSummary?.needs_attention)
  const pullConflict = Boolean(pullSummary?.needs_conflict_resolution)

  if (!(pushAttention || pullAttention || result.operation_kind === 'sync' || result.operation_kind === 'pull' || result.operation_kind === 'push' || result.operation_kind === 'restore')) {
    return null
  }

  if (pushConflict || pullConflict) {
    return {
      tone: 'warning',
      message: '当前结果包含冲突，建议先处理 conflicts_dir 中的冲突文件后再继续同步。',
    }
  }
  if (pushRetry) {
    return {
      tone: 'warning',
      message: '当前结果包含可重试记录，建议先检查源文件或远端拒绝原因后重试。',
    }
  }
  if (pushAttention || pullAttention) {
    return {
      tone: 'warning',
      message: '当前同步结果仍有待处理项，建议先查看状态文件和 recent failures。',
    }
  }
  return {
    tone: 'success',
    message: '当前同步结果未发现额外 attention 项。',
  }
}

function buildSourceStatusAttention(statusResult) {
  if (!statusResult) return null
  if (statusResult.needs_conflict_resolution) {
    return {
      tone: 'warning',
      message: statusResult.attention_reason || '当前 source 存在冲突记录，需要先处理再继续同步。',
    }
  }
  if (statusResult.needs_attention) {
    return {
      tone: 'warning',
      message: statusResult.attention_reason || '当前 source 仍有待处理项。',
    }
  }
  return {
    tone: 'success',
    message: '当前 source 状态健康，没有额外待处理项。',
  }
}

export default function ImportPage() {
  const [activeTab, setActiveTab] = useState('file')
  const [selectedFile, setSelectedFile] = useState(null)
  const [selectedConversationFile, setSelectedConversationFile] = useState(null)
  const [directoryPath, setDirectoryPath] = useState('')
  const [directoryExtensionsText, setDirectoryExtensionsText] = useState(DIRECTORY_EXTENSIONS.join(','))
  const [directoryScanLoading, setDirectoryScanLoading] = useState(false)
  const [directoryScanResult, setDirectoryScanResult] = useState(null)
  const [directoryBatchResult, setDirectoryBatchResult] = useState(null)
  const [importRuns, setImportRuns] = useState([])
  const [importRunsLoading, setImportRunsLoading] = useState(false)
  const [importRunsError, setImportRunsError] = useState(null)
  const [retryingRunId, setRetryingRunId] = useState(null)
  const [textContent, setTextContent] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [sourceForm, setSourceForm] = useState(() => readSourceForm())
  const [sourcePreview, setSourcePreview] = useState(null)
  const [sourceSyncResult, setSourceSyncResult] = useState(null)
  const [sourceStatusResult, setSourceStatusResult] = useState(null)
  const [savedSources, setSavedSources] = useState([])
  const [selectedSourceId, setSelectedSourceId] = useState('')
  const [sourceSettingsLoading, setSourceSettingsLoading] = useState(false)
  const [sourceSyncRunningAction, setSourceSyncRunningAction] = useState(null)
  const [sourceStatusLoading, setSourceStatusLoading] = useState(false)
  const [sourceStatusError, setSourceStatusError] = useState(null)
  const [runtimeDiagnostics, setRuntimeDiagnostics] = useState(DEFAULT_RUNTIME_DIAGNOSTICS)
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false)
  const [diagnosticsError, setDiagnosticsError] = useState(null)
  const sourcePathCount = useMemo(() => parseSourcePathLines(sourceForm.source_paths_text).length, [sourceForm.source_paths_text])
  const sourcePreviewFileCount = Array.isArray(sourcePreview?.matched_files) ? sourcePreview.matched_files.length : 0
  const sourcePreviewRecordCount = typeof sourcePreview?.record_count === 'number' ? sourcePreview.record_count : null
  const sourceOperationRuns = useMemo(() => {
    const runs = Array.isArray(importRuns) ? importRuns : []
    return runs.filter((run) => {
      const runType = String(run?.run_type || '').toLowerCase()
      if (!runType.startsWith('source_')) return false
      if (!selectedSourceId) return true
      return run?.source_id === selectedSourceId
    })
  }, [importRuns, selectedSourceId])
  const diagnosticsSources = Array.isArray(runtimeDiagnostics?.task_chain?.sources) ? runtimeDiagnostics.task_chain.sources : []
  const attentionSources = diagnosticsSources.filter((source) => source?.state_status !== 'healthy')
  const diagnosticsRecentFailures = Array.isArray(runtimeDiagnostics?.recent_failures)
    ? runtimeDiagnostics.recent_failures.slice(0, 5)
    : []
  const diagnosticsSummary = useMemo(
    () => buildImportRuntimeDiagnosticsSummary(runtimeDiagnostics),
    [runtimeDiagnostics]
  )
  const sourceSyncAttention = useMemo(() => buildSourceOperationAttention(sourceSyncResult), [sourceSyncResult])
  const sourceStatusAttention = useMemo(() => buildSourceStatusAttention(sourceStatusResult), [sourceStatusResult])

  const canSubmit = useMemo(() => {
    if (loading) return false
    if (activeTab === 'file') return Boolean(selectedFile)
    if (activeTab === 'text') return Boolean(textContent.trim())
    if (activeTab === 'conversations') return Boolean(selectedConversationFile)
    if (activeTab === 'directory') return Boolean(directoryPath.trim())
    if (activeTab === 'source') return sourcePathCount > 0
    return false
  }, [activeTab, directoryPath, loading, selectedConversationFile, selectedFile, sourcePathCount, textContent])

  useEffect(() => {
    writeSourceForm(sourceForm)
  }, [sourceForm])

  useEffect(() => {
    let mounted = true

    async function loadSavedSources() {
      setSourceSettingsLoading(true)
      try {
        const data = await apiClient.get('/sync/sources/settings')
        if (!mounted) return
        const sources = Array.isArray(data?.sources) ? data.sources : []
        setSavedSources(sources)
        if (sources.length === 0) {
          setSelectedSourceId('')
          return
        }

        const preferredSourceId = sourceForm.source_id && sources.some((source) => source.source_id === sourceForm.source_id)
          ? sourceForm.source_id
          : selectedSourceId && sources.some((source) => source.source_id === selectedSourceId)
            ? selectedSourceId
            : sources[0].source_id

        setSelectedSourceId(preferredSourceId)
        const selectedSource = sources.find((source) => source.source_id === preferredSourceId)
        if (selectedSource) {
          setSourceForm((current) => ({
            ...current,
            ...formFromSourceSetting(selectedSource),
          }))
          loadSourceStatus(selectedSource.source_id, { showError: false })
        }
      } catch {
        if (!mounted) return
        setSavedSources([])
        setSelectedSourceId('')
      } finally {
        if (mounted) {
          setSourceSettingsLoading(false)
        }
      }
    }

    loadSavedSources()

    return () => {
      mounted = false
    }
  }, [])

  async function loadRuntimeDiagnostics({ showError = true } = {}) {
    setDiagnosticsLoading(true)
    if (showError) {
      setDiagnosticsError(null)
    }

    try {
      const data = await apiClient.get('/diagnostics/runtime')
      setRuntimeDiagnostics(normalizeRuntimeDiagnostics(data))
      setDiagnosticsError(null)
    } catch (requestError) {
      if (showError) {
        setDiagnosticsError(normalizeErrorMessage(requestError, '加载导入/同步状态失败'))
      }
    } finally {
      setDiagnosticsLoading(false)
    }
  }

  useEffect(() => {
    loadRuntimeDiagnostics({ showError: false })
  }, [])

  async function loadImportRuns({ showError = true } = {}) {
    setImportRunsLoading(true)
    if (showError) {
      setImportRunsError(null)
    }
    try {
      const response = await importApi.listImportRuns(DIRECTORY_IMPORT_RUN_LIMIT)
      setImportRuns(normalizeImportRunsResponse(response))
    } catch (requestError) {
      if (showError) {
        setImportRunsError(normalizeErrorMessage(requestError, '加载 recent import runs 失败'))
      }
    } finally {
      setImportRunsLoading(false)
    }
  }

  async function loadSourceStatus(sourceId = selectedSourceId, { showError = true } = {}) {
    if (!sourceId) {
      setSourceStatusResult(null)
      if (showError) {
        setSourceStatusError(null)
      }
      return
    }

    setSourceStatusLoading(true)
    if (showError) {
      setSourceStatusError(null)
    }

    try {
      const data = await apiClient.get(`/sync/sources/settings/${sourceId}/status`)
      setSourceStatusResult(data)
    } catch (requestError) {
      if (showError) {
        setSourceStatusError(normalizeErrorMessage(requestError, '加载当前源状态失败'))
      }
    } finally {
      setSourceStatusLoading(false)
    }
  }

  useEffect(() => {
    loadImportRuns({ showError: false })
  }, [])

  async function runFileImport() {
    if (!selectedFile) return
    const response = await importApi.importFile(selectedFile)
    const imported = Number(response?.imported ?? 0)
    setResult({
      success: true,
      message: `文件导入成功：${selectedFile.name}`,
      details: imported > 0 ? `已导入 ${imported} 条记忆` : '文件已处理，未新增记忆（可能已存在）'
    })
    setSelectedFile(null)
    loadImportRuns({ showError: false })
  }

  async function runTextImport() {
    const content = textContent.trim()
    if (!content) return

    const file = buildTextImportFile(content)
    const response = await importApi.importFile(file)
    const imported = Number(response?.imported ?? 0)
    const wordCount = buildWordCount(content)
    setResult({
      success: true,
      message: `文本导入成功：${wordCount} 个词`,
      details: imported > 0 ? `已导入 ${imported} 条记忆` : '文本已处理，未新增记忆（可能已存在）'
    })
    setTextContent('')
    loadImportRuns({ showError: false })
  }

  async function runConversationsImport() {
    if (!selectedConversationFile) return

    const response = await importApi.importConversations(selectedConversationFile)
    setResult({
      success: true,
      message: `会话导入成功：${selectedConversationFile.name}`,
      details:
        typeof response?.imported_memories === 'number'
          ? `成功导入 ${response.imported_memories} 条会话记忆`
          : '会话文件已完成导入'
    })
    setSelectedConversationFile(null)
    loadImportRuns({ showError: false })
  }

  async function runDirectoryScan() {
    const trimmedPath = directoryPath.trim()
    if (!trimmedPath) return

    setDirectoryScanLoading(true)
    setDirectoryScanResult(null)
    setError(null)
    try {
      const response = await importApi.scanDirectory(trimmedPath, parseDirectoryExtensions(directoryExtensionsText))
      setDirectoryScanResult(response)
    } catch (requestError) {
      setError(normalizeErrorMessage(requestError, '目录预扫描失败，请重试'))
    } finally {
      setDirectoryScanLoading(false)
    }
  }

  async function runDirectoryImport() {
    const trimmedPath = directoryPath.trim()
    if (!trimmedPath) return

    const response = await importApi.importDirectory(trimmedPath, parseDirectoryExtensions(directoryExtensionsText))
    setDirectoryBatchResult(response)

    const importedMemories = Number(response?.imported ?? 0)
    const attemptedFiles = Number(response?.attempted ?? 0)
    const failedFiles = Number(response?.failed ?? 0)

    setResult({
      success: true,
      message: `目录批量导入完成：${trimmedPath}`,
      details: `imported=${importedMemories} | attempted=${attemptedFiles} | failed=${failedFiles}`
    })
    loadImportRuns({ showError: false })
  }

  async function runSourcePreview() {
    const response = await apiClient.post('/sync/sources/preview', buildSourcePreviewPayload(sourceForm))
    setSourcePreview(response)
    setResult({
      success: true,
      message: `同步源预览完成：${response.source_system}`,
      details: `匹配 ${response.matched_files.length} 个文件，预计解析 ${response.record_count} 条记录`
    })
  }

  async function saveSourceSetting() {
    const payload = buildSourceSettingPayload(sourceForm)
    const response = selectedSourceId
      ? await apiClient.put(`/sync/sources/settings/${selectedSourceId}`, payload)
      : await apiClient.post('/sync/sources/settings', payload)

    const sourcesResponse = await apiClient.get('/sync/sources/settings')
    const sources = Array.isArray(sourcesResponse?.sources) ? sourcesResponse.sources : []
    setSavedSources(sources)
    setSelectedSourceId(response.source_id)
    setSourceForm(formFromSourceSetting(response))
    setSourceSyncResult(null)
    setSourceStatusResult(null)
    setResult({
      success: true,
      message: `同步源已保存：${buildSourceSettingLabel(response)}`,
      details: `已保存 ${response.source_paths.length} 条路径配置`
    })
    await loadSourceStatus(response.source_id, { showError: false })
    await loadRuntimeDiagnostics({ showError: false })
  }

  async function deleteSourceSetting() {
    if (!selectedSourceId) return

    await apiClient.delete(`/sync/sources/settings/${selectedSourceId}`)
    const sourcesResponse = await apiClient.get('/sync/sources/settings')
    const sources = Array.isArray(sourcesResponse?.sources) ? sourcesResponse.sources : []
    setSavedSources(sources)
    setSelectedSourceId('')
    setSourceForm(DEFAULT_SOURCE_FORM)
    setSourcePreview(null)
    setSourceSyncResult(null)
    setSourceStatusResult(null)
    setResult({
      success: true,
      message: '同步源已删除',
      details: '当前同步源配置已从本地项目设置中移除'
    })
    await loadRuntimeDiagnostics({ showError: false })
  }

  function handleCreateNewSource() {
    setSelectedSourceId('')
    setSourcePreview(null)
    setSourceSyncResult(null)
    setSourceStatusResult(null)
    setSourceStatusError(null)
    setSourceForm(DEFAULT_SOURCE_FORM)
    setResult(null)
    setError(null)
  }

  function handleSelectSource(setting) {
    setSelectedSourceId(setting.source_id)
    setSourcePreview(null)
    setSourceSyncResult(null)
    setSourceStatusResult(null)
    setSourceStatusError(null)
    setSourceForm(formFromSourceSetting(setting))
    setResult(null)
    setError(null)
    loadSourceStatus(setting.source_id, { showError: false })
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (!canSubmit) return

    setLoading(true)
    setResult(null)
    setError(null)

    try {
      if (activeTab === 'file') {
        await runFileImport()
      } else if (activeTab === 'text') {
        await runTextImport()
      } else if (activeTab === 'conversations') {
        await runConversationsImport()
      } else if (activeTab === 'directory') {
        await runDirectoryImport()
      } else if (activeTab === 'source') {
        await saveSourceSetting()
      }
    } catch (requestError) {
      const message = normalizeErrorMessage(requestError, '导入失败，请重试')
      setError(message)
      setResult({
        success: false,
        message: '导入失败',
        details: message
      })
    } finally {
      setLoading(false)
    }
  }

  async function handleRetryImportRun(run) {
    const runId = buildImportRunId(run)
    if (!runId) return

    setRetryingRunId(String(runId))
    setError(null)
    setResult(null)

    try {
      const response = await importApi.retryImportRun(runId)
      const retryResult = response?.result || {}
      const imported = Number(retryResult?.imported ?? 0)
      const attempted = Number(retryResult?.attempted ?? 0)
      const failed = Number(retryResult?.failed ?? 0)
      const retryLabel = run?.directory_path || run?.filename || String(runId)

      setResult({
        success: true,
        message: `目录导入重试完成：${retryLabel}`,
        details: `imported=${imported} | attempted=${attempted} | failed=${failed}`
      })
      await loadImportRuns({ showError: false })
      await loadRuntimeDiagnostics({ showError: false })
    } catch (requestError) {
      const message = normalizeErrorMessage(requestError, '重试目录导入失败')
      setError(message)
      setResult({
        success: false,
        message: '重试失败',
        details: message
      })
      await loadImportRuns({ showError: false })
    } finally {
      setRetryingRunId(null)
    }
  }

  async function handlePushSourceSetting() {
    if (!selectedSourceId) return

    setSourceSyncRunningAction('push')
    setError(null)
    setResult(null)

    try {
      const response = await apiClient.post(`/sync/sources/settings/${selectedSourceId}/push`, {
        batch_size: 50,
        delete_missing: true
      })
      const nextResult = { ...response, operation_kind: 'push' }
      const summary = response?.summary || {}
      setSourceSyncResult(nextResult)
      setResult({
        success: true,
        message: `同步源执行完成：${response?.label || selectedSourceId}`,
        details: `matched=${Number(summary.matched_files ?? 0)} | scanned=${Number(summary.scanned_records ?? 0)} | created=${Number(summary.created ?? 0)} | updated=${Number(summary.updated ?? 0)} | conflicts=${Number(summary.conflicts ?? 0)}`
      })
      await loadImportRuns({ showError: false })
      await loadRuntimeDiagnostics({ showError: false })
      await loadSourceStatus(selectedSourceId, { showError: false })
    } catch (requestError) {
      const message = normalizeErrorMessage(requestError, '执行同步源失败')
      setSourceSyncResult(null)
      setError(message)
      setResult({
        success: false,
        message: '同步执行失败',
        details: message
      })
    } finally {
      setSourceSyncRunningAction(null)
    }
  }

  async function handlePullSourceSetting() {
    if (!selectedSourceId) return

    setSourceSyncRunningAction('pull')
    setError(null)
    setResult(null)

    try {
      const response = await apiClient.post(`/sync/sources/settings/${selectedSourceId}/pull`, {
        change_limit: 100
      })
      const nextResult = { ...response, operation_kind: 'pull' }
      const summary = response?.summary || {}
      setSourceSyncResult(nextResult)
      setResult({
        success: true,
        message: `远端变更拉取完成：${response?.label || selectedSourceId}`,
        details: `processed=${Number(summary.processed_changes ?? 0)} | creates=${Number(summary.applied_creates ?? 0)} | updates=${Number(summary.applied_updates ?? 0)} | deletes=${Number(summary.applied_deletes ?? 0)} | conflicts=${Number(summary.written_conflicts ?? 0)}`
      })
      await loadImportRuns({ showError: false })
      await loadRuntimeDiagnostics({ showError: false })
      await loadSourceStatus(selectedSourceId, { showError: false })
    } catch (requestError) {
      const message = normalizeErrorMessage(requestError, '拉取远端变更失败')
      setSourceSyncResult(null)
      setError(message)
      setResult({
        success: false,
        message: '拉取失败',
        details: message
      })
    } finally {
      setSourceSyncRunningAction(null)
    }
  }

  async function handleSyncSourceSetting() {
    if (!selectedSourceId) return

    setSourceSyncRunningAction('sync')
    setError(null)
    setResult(null)

    try {
      const response = await apiClient.post(`/sync/sources/settings/${selectedSourceId}/sync`, {
        batch_size: 50,
        change_limit: 100,
        delete_missing: true
      })
      const nextResult = { ...response, operation_kind: 'sync' }
      setSourceSyncResult(nextResult)
      setResult({
        success: true,
        message: `双向同步完成：${response?.label || selectedSourceId}`,
        details: `push(created=${Number(response?.push?.created ?? 0)}, updated=${Number(response?.push?.updated ?? 0)}, conflicts=${Number(response?.push?.conflicts ?? 0)}) | pull(processed=${Number(response?.pull?.processed_changes ?? 0)}, conflicts=${Number(response?.pull?.written_conflicts ?? 0)})`
      })
      await loadImportRuns({ showError: false })
      await loadRuntimeDiagnostics({ showError: false })
      await loadSourceStatus(selectedSourceId, { showError: false })
    } catch (requestError) {
      const message = normalizeErrorMessage(requestError, '双向同步失败')
      setSourceSyncResult(null)
      setError(message)
      setResult({
        success: false,
        message: '双向同步失败',
        details: message
      })
    } finally {
      setSourceSyncRunningAction(null)
    }
  }

  async function handleRestoreSourceSetting() {
    if (!selectedSourceId) return

    setSourceSyncRunningAction('restore')
    setError(null)
    setResult(null)

    try {
      const response = await apiClient.post(`/sync/sources/settings/${selectedSourceId}/restore`, {
        batch_size: 50
      })
      const nextResult = { ...response, operation_kind: 'restore' }
      const summary = response?.summary || {}
      setSourceSyncResult(nextResult)
      setResult({
        success: true,
        message: `已删除记录恢复完成：${response?.label || selectedSourceId}`,
        details: `restore_candidates=${Number(summary.restore_candidates ?? 0)} | pushed=${Number(summary.pushed_records ?? 0)} | created=${Number(summary.created ?? 0)} | updated=${Number(summary.updated ?? 0)}`
      })
      await loadImportRuns({ showError: false })
      await loadRuntimeDiagnostics({ showError: false })
      await loadSourceStatus(selectedSourceId, { showError: false })
    } catch (requestError) {
      const message = normalizeErrorMessage(requestError, '恢复已删除记录失败')
      setSourceSyncResult(null)
      setError(message)
      setResult({
        success: false,
        message: '恢复失败',
        details: message
      })
    } finally {
      setSourceSyncRunningAction(null)
    }
  }

  return (
    <section className="import-page" aria-label="Import page">
      <header className="import-header">
        <h1>Inbox</h1>
        <p className="import-subtitle">接入数据源、预览命中范围，并查看最近一次导入或配置结果</p>
      </header>

      <section
        className="import-diagnostics-card"
        aria-label="Import diagnostics"
        data-testid={IMPORT_SMOKE_TEST_IDS.diagnosticsCard}
      >
        <div className="import-diagnostics-head">
          <div>
            <h2>导入/同步状态</h2>
            <p>
              生成时间：{formatDiagnosticsTime(runtimeDiagnostics.generated_at)}，Task Chain:
              {' '}{runtimeDiagnostics.task_chain?.status || 'not_configured'}
            </p>
          </div>
          <button
            type="button"
            className="import-secondary-btn"
            data-testid={IMPORT_SMOKE_TEST_IDS.diagnosticsRefreshButton}
            onClick={() => loadRuntimeDiagnostics({ showError: true })}
            disabled={diagnosticsLoading}
          >
            {diagnosticsLoading ? '刷新中...' : '刷新状态'}
          </button>
        </div>

        <div
          className={`import-diagnostics-alert import-diagnostics-alert--summary import-diagnostics-alert--${diagnosticsSummary.tone}`}
          data-testid={IMPORT_SMOKE_TEST_IDS.diagnosticsSummary}
        >
          <div>{diagnosticsSummary.message}</div>
          {diagnosticsSummary.detail ? (
            <div className="import-diagnostics-summary-detail">{diagnosticsSummary.detail}</div>
          ) : null}
        </div>

        <div className="import-diagnostics-overview">
          <div className="import-diagnostics-pill">
            runtime_status: {runtimeDiagnostics.status || 'unknown'}
          </div>
          <div className="import-diagnostics-pill">
            current_provider: {runtimeDiagnostics.checks?.provider?.current_provider || '-'}
          </div>
          <div className="import-diagnostics-pill">
            configured_sources: {runtimeDiagnostics.task_chain?.configured_sources ?? 0}
          </div>
          <div className="import-diagnostics-pill">
            attention_sources: {attentionSources.length}
          </div>
          <div className="import-diagnostics-pill">
            recent_failures: {diagnosticsRecentFailures.length}
          </div>
        </div>

        {diagnosticsError ? (
          <div className="import-diagnostics-alert import-diagnostics-alert--error" role="alert">
            {diagnosticsError}
          </div>
        ) : null}

        {runtimeDiagnostics.task_chain?.detail ? (
          <div className="import-diagnostics-alert" role="status">
            {runtimeDiagnostics.task_chain.detail}
          </div>
        ) : null}

        <div className="import-diagnostics-grid">
          <article className="import-diagnostics-panel">
            <h3>Sync Sources</h3>
            {diagnosticsSources.length ? (
              <ul className="import-diagnostics-source-list">
                {diagnosticsSources.map((source, index) => {
                  const badge = buildSourceStatusBadge(source?.state_status)
                  return (
                    <li key={source?.source_id || `${source?.workspace_id || 'source'}-${index}`}>
                      <div className="import-diagnostics-source-head">
                        <strong>{source?.label || source?.source_id || '未命名 source'}</strong>
                        <span className={badge.className}>{badge.label}</span>
                      </div>
                      <div className="import-diagnostics-source-meta">
                        system={source?.source_system || '-'} | workspace={source?.workspace_id || '-'} | records=
                        {source?.record_count ?? 0} | conflicts={source?.conflicts ?? 0} | deleted=
                        {source?.deleted_records ?? 0}
                      </div>
                      {source?.detail ? (
                        <div className="import-diagnostics-source-detail">{source.detail}</div>
                      ) : null}
                      {source?.state_status !== 'healthy' ? (
                        <div className="import-diagnostics-source-guidance">
                          retry guidance: {buildSourceRetryGuidance(source)}
                        </div>
                      ) : null}
                    </li>
                  )
                })}
              </ul>
            ) : (
              <div className="import-diagnostics-empty">
                当前没有可诊断的 source。先在“外部记忆源”页签保存至少一个 source。
              </div>
            )}
          </article>

          <article className="import-diagnostics-panel">
            <h3>Recent Failures</h3>
            {diagnosticsRecentFailures.length ? (
              <ul className="import-diagnostics-failure-list">
                {diagnosticsRecentFailures.map((item, index) => (
                  <li key={`${item?.component || 'unknown'}-${item?.last_seen_at || index}`}>
                    <div className="import-diagnostics-failure-main">
                      <strong>{item?.component || 'unknown'}</strong>
                      <span>{item?.detail || '-'}</span>
                    </div>
                    <div className="import-diagnostics-failure-meta">
                      source={item?.source || '-'} | count={item?.count ?? 1} | last_seen=
                      {formatDiagnosticsTime(item?.last_seen_at)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="import-diagnostics-empty">最近没有失败记录</div>
            )}
          </article>
        </div>
      </section>

      <div className="import-tabs" role="tablist" aria-label="导入类型">
        <button
          type="button"
          className={`import-tab ${activeTab === 'file' ? 'is-active' : ''}`}
          data-tab="file"
          onClick={() => setActiveTab('file')}
        >
          文件
        </button>
        <button
          type="button"
          className={`import-tab ${activeTab === 'directory' ? 'is-active' : ''}`}
          data-tab="directory"
          onClick={() => setActiveTab('directory')}
        >
          文件夹
        </button>
        <button
          type="button"
          className={`import-tab ${activeTab === 'text' ? 'is-active' : ''}`}
          data-tab="text"
          onClick={() => setActiveTab('text')}
        >
          文本
        </button>
        <button
          type="button"
          className={`import-tab ${activeTab === 'conversations' ? 'is-active' : ''}`}
          data-tab="conversations"
          onClick={() => setActiveTab('conversations')}
        >
          会话
        </button>
        <button
          type="button"
          className={`import-tab ${activeTab === 'source' ? 'is-active' : ''}`}
          data-tab="source"
          onClick={() => setActiveTab('source')}
        >
          外部记忆源
        </button>
      </div>

      <form className="import-card" onSubmit={handleSubmit}>
        {activeTab === 'file' ? (
          <div className="import-section">
            <label className="import-label" htmlFor="import-file-input">
              选择文件
            </label>
            <input
              id="import-file-input"
              className="import-file-input"
              type="file"
              accept=".txt,.md,.json,.pdf,.doc,.docx"
              onChange={(event) => setSelectedFile(event.target.files?.[0] || null)}
            />
            {selectedFile ? <div className="import-file-meta">已选择：{selectedFile.name}</div> : null}
          </div>
        ) : null}

        {activeTab === 'directory' ? (
          <div className="import-section">
            <label className="import-label" htmlFor="import-directory-path-input">
              目录路径
            </label>
            <input
              id="import-directory-path-input"
              className="import-directory-input"
              type="text"
              value={directoryPath}
              placeholder="/home/you/notes"
              onChange={(event) => setDirectoryPath(event.target.value)}
            />

            <label className="import-label" htmlFor="import-directory-extensions-input">
              导入后缀（逗号分隔）
            </label>
            <input
              id="import-directory-extensions-input"
              className="import-directory-input"
              type="text"
              value={directoryExtensionsText}
              onChange={(event) => setDirectoryExtensionsText(event.target.value)}
            />
            <div className="import-hint">默认后缀：{DIRECTORY_EXTENSIONS.join(', ')}</div>

            <div className="import-directory-actions">
              <button
                type="button"
                className="import-secondary-btn"
                onClick={runDirectoryScan}
                disabled={directoryScanLoading || loading || !directoryPath.trim()}
              >
                {directoryScanLoading ? '预扫描中...' : '预扫描目录'}
              </button>
            </div>

            {directoryScanResult ? (
              <div className="import-file-meta">
                预扫描结果：matched={getDirectoryScanMatchedCount(directoryScanResult)}
                {' '}| skipped={getDirectoryScanSkippedCount(directoryScanResult)}
              </div>
            ) : null}

            <DirectoryImportResultPanel result={directoryBatchResult} />
            <ImportRunHistoryPanel
              runs={importRuns}
              loading={importRunsLoading}
              error={importRunsError}
              onRefresh={() => loadImportRuns({ showError: true })}
              onRetry={handleRetryImportRun}
              retryingRunId={retryingRunId}
              title="Recent Import Runs"
            />
          </div>
        ) : null}

        {activeTab === 'text' ? (
          <div className="import-section">
            <label className="import-label" htmlFor="import-textarea">
              输入文本
            </label>
            <textarea
              id="import-textarea"
              className="import-textarea"
              rows={8}
              value={textContent}
              placeholder="输入或粘贴要导入的文本内容"
              onChange={(event) => setTextContent(event.target.value)}
            />
            <div className="import-hint">字符数：{textContent.length}</div>
          </div>
        ) : null}

        {activeTab === 'conversations' ? (
          <div className="import-section">
            <label className="import-label" htmlFor="import-conversations-input">
              上传会话导出文件
            </label>
            <input
              id="import-conversations-input"
              className="import-conversations-input"
              type="file"
              accept=".json,.jsonl,.zip"
              onChange={(event) => setSelectedConversationFile(event.target.files?.[0] || null)}
            />
            {selectedConversationFile ? <div className="import-file-meta">已选择：{selectedConversationFile.name}</div> : null}
          </div>
        ) : null}

        {activeTab === 'source' ? (
          <div className="import-section import-section--source">
            <div className="import-source-layout">
              <aside className="import-source-sidebar">
                <div className="import-source-panel">
                  <div className="import-source-panel-header">
                    <div>
                      <h2 className="import-source-panel-title">已保存同步源</h2>
                      <p className="import-source-panel-copy">先选择一个已有配置，或者新建一个项目源再填写路径。</p>
                    </div>
                    <button type="button" className="import-secondary-btn" onClick={handleCreateNewSource}>
                      新建同步源
                    </button>
                  </div>

                  <div className="import-source-stats">
                    <div className="import-source-stat">
                      <span className="import-source-stat-label">已保存</span>
                      <strong className="import-source-stat-value">{savedSources.length}</strong>
                    </div>
                    <div className="import-source-stat">
                      <span className="import-source-stat-label">当前路径</span>
                      <strong className="import-source-stat-value">{sourcePathCount}</strong>
                    </div>
                  </div>

                  <div className="import-source-settings-list">
                    {sourceSettingsLoading ? (
                      <div className="import-file-meta">加载同步源中...</div>
                    ) : savedSources.length > 0 ? (
                      savedSources.map((setting) => (
                        <button
                          type="button"
                          key={setting.source_id}
                          className={`import-source-setting-item ${selectedSourceId === setting.source_id ? 'is-selected' : ''}`}
                          onClick={() => handleSelectSource(setting)}
                        >
                          <span className="import-source-setting-body">
                            <span className="import-source-setting-title">{buildSourceSettingLabel(setting)}</span>
                            <span className="import-source-setting-paths">{setting.source_paths.length} 条路径</span>
                          </span>
                          <span className="import-source-setting-meta">
                            {selectedSourceId === setting.source_id ? '当前编辑' : (setting.source_system || 'external')}
                          </span>
                        </button>
                      ))
                    ) : (
                      <div className="import-source-list-empty">还没有已保存的同步源配置</div>
                    )}
                  </div>
                </div>
              </aside>

              <div className="import-source-main">
                <div className="import-source-panel">
                  <div className="import-source-panel-header">
                    <div>
                      <h2 className="import-source-panel-title">{selectedSourceId ? '编辑同步源' : '创建同步源'}</h2>
                      <p className="import-source-panel-copy">填写来源标识和路径，先预览命中结果，再决定是否保存。</p>
                    </div>
                    <span className="import-source-badge">{selectedSourceId ? '已选中配置' : '未保存配置'}</span>
                  </div>

                  <div className="import-source-form-grid">
                    <div className="import-source-field">
                      <label className="import-label" htmlFor="import-source-label">
                        显示名称（可选）
                      </label>
                      <input
                        id="import-source-label"
                        className="import-file-input"
                        type="text"
                        value={sourceForm.label}
                        placeholder="例如：项目 A 记忆源"
                        onChange={(event) => setSourceForm((current) => ({ ...current, label: event.target.value }))}
                      />
                      <div className="import-hint">用于区分不同项目源，显示在左侧列表中。</div>
                    </div>

                    <div className="import-source-field">
                      <label className="import-label" htmlFor="import-source-system">
                        来源标识
                      </label>
                      <input
                        id="import-source-system"
                        className="import-file-input"
                        type="text"
                        value={sourceForm.source_system}
                        placeholder="例如：project-notes / openclaw-main / journal"
                        onChange={(event) => setSourceForm((current) => ({ ...current, source_system: event.target.value }))}
                      />
                      <div className="import-hint">建议使用稳定、可读的项目代号。</div>
                    </div>

                    <div className="import-source-field">
                      <label className="import-label" htmlFor="import-source-workspace-id">
                        工作区 ID
                      </label>
                      <input
                        id="import-source-workspace-id"
                        className="import-file-input"
                        type="text"
                        value={sourceForm.workspace_id}
                        placeholder="例如：workspace-main / project-alpha"
                        onChange={(event) => setSourceForm((current) => ({ ...current, workspace_id: event.target.value }))}
                      />
                      <div className="import-hint">同一来源下可用不同工作区 ID 做隔离。</div>
                    </div>

                    <div className="import-source-field">
                      <label className="import-label" htmlFor="import-source-workspace-root">
                        根目录（可选）
                      </label>
                      <input
                        id="import-source-workspace-root"
                        className="import-file-input"
                        type="text"
                        value={sourceForm.workspace_root}
                        placeholder="/home/you/project"
                        onChange={(event) => setSourceForm((current) => ({ ...current, workspace_root: event.target.value }))}
                      />
                      <div className="import-hint">用于给相对路径提供统一根目录。</div>
                    </div>

                    <div className="import-source-field import-source-field--full">
                      <div className="import-source-field-head">
                        <label className="import-label" htmlFor="import-source-paths">
                          路径列表（每行一个，可输入多个路径）
                        </label>
                        <span className="import-source-field-meta">当前 {sourcePathCount} 条</span>
                      </div>
                      <textarea
                        id="import-source-paths"
                        className="import-textarea"
                        rows={6}
                        value={sourceForm.source_paths_text}
                        placeholder={'MEMORY.md\nmemory/**/*.md\n/home/you/notes/**/*.md'}
                        onChange={(event) => setSourceForm((current) => ({ ...current, source_paths_text: event.target.value }))}
                      />
                      <div className="import-hint">支持相对路径、绝对路径和 glob；保存后可直接执行当前源同步。</div>
                    </div>
                  </div>
                </div>

                <div className="import-source-panel">
                  <div className="import-source-panel-header">
                    <div>
                      <h2 className="import-source-panel-title">预览结果</h2>
                      <p className="import-source-panel-copy">这里会展示当前配置命中的文件数量，以及预计可解析的记录数。</p>
                    </div>
                  </div>

                  <div className="import-source-stats import-source-stats--preview">
                    <div className="import-source-stat">
                      <span className="import-source-stat-label">匹配文件</span>
                      <strong className="import-source-stat-value">{sourcePreviewFileCount}</strong>
                    </div>
                    <div className="import-source-stat">
                      <span className="import-source-stat-label">预计记录</span>
                      <strong className="import-source-stat-value">
                        {sourcePreviewRecordCount === null ? '—' : sourcePreviewRecordCount}
                      </strong>
                    </div>
                  </div>

                  {sourcePreview ? (
                    <div className="import-source-preview" role="status">
                      <div className="import-source-preview-grid">
                        <div><strong>来源标识：</strong>{sourcePreview.source_system}</div>
                        <div><strong>工作区 ID：</strong>{sourcePreview.workspace_id}</div>
                        <div><strong>根目录：</strong>{sourcePreview.workspace_root || '未设置'}</div>
                        <div><strong>匹配文件：</strong>{sourcePreviewFileCount}</div>
                        <div><strong>解析记录：</strong>{sourcePreview.record_count}</div>
                      </div>
                      {sourcePreviewFileCount > 0 ? (
                        <div className="import-source-preview-files">
                          {sourcePreview.matched_files.slice(0, 12).map((filePath) => (
                            <code key={filePath}>{filePath}</code>
                          ))}
                          {sourcePreviewFileCount > 12 ? (
                            <span>... 还有 {sourcePreviewFileCount - 12} 个</span>
                          ) : null}
                        </div>
                      ) : (
                        <div className="import-hint">当前路径没有匹配到 markdown 文件。</div>
                      )}
                    </div>
                  ) : (
                    <div className="import-source-preview import-source-preview--placeholder">
                      <p className="import-source-placeholder-title">还没有预览结果</p>
                      <p className="import-source-placeholder-copy">填写至少 1 条路径后点击“预览当前源”，这里会显示命中的文件和预计解析记录。</p>
                    </div>
                  )}

                  {sourceSyncResult ? (
                    <div className="import-source-sync-summary" role="status">
                      <div className="import-source-sync-summary-head">
                        <strong>最近一次{buildSourceOperationLabel(sourceSyncResult.operation_kind)}</strong>
                        <span>{sourceSyncResult.label || sourceSyncResult.source_system}</span>
                      </div>
                      {sourceSyncResult.operation_kind === 'pull' ? (
                        <div className="import-source-preview-grid">
                          <div><strong>processed_changes：</strong>{sourceSyncResult.summary?.processed_changes ?? 0}</div>
                          <div><strong>applied_creates：</strong>{sourceSyncResult.summary?.applied_creates ?? 0}</div>
                          <div><strong>applied_updates：</strong>{sourceSyncResult.summary?.applied_updates ?? 0}</div>
                          <div><strong>applied_deletes：</strong>{sourceSyncResult.summary?.applied_deletes ?? 0}</div>
                          <div><strong>written_conflicts：</strong>{sourceSyncResult.summary?.written_conflicts ?? 0}</div>
                          <div><strong>skipped_echoes：</strong>{sourceSyncResult.summary?.skipped_echoes ?? 0}</div>
                        </div>
                      ) : sourceSyncResult.operation_kind === 'sync' ? (
                        <div className="import-source-sync-split">
                          <div className="import-source-sync-block">
                            <strong className="import-source-sync-block-title">Push</strong>
                            <div className="import-source-preview-grid">
                              <div><strong>匹配文件：</strong>{sourceSyncResult.push?.matched_files ?? 0}</div>
                              <div><strong>扫描记录：</strong>{sourceSyncResult.push?.scanned_records ?? 0}</div>
                              <div><strong>created：</strong>{sourceSyncResult.push?.created ?? 0}</div>
                              <div><strong>updated：</strong>{sourceSyncResult.push?.updated ?? 0}</div>
                              <div><strong>noop：</strong>{sourceSyncResult.push?.noop ?? 0}</div>
                              <div><strong>conflicts：</strong>{sourceSyncResult.push?.conflicts ?? 0}</div>
                              <div><strong>marker_updates：</strong>{sourceSyncResult.push?.marker_updates ?? 0}</div>
                              <div><strong>deleted_remote：</strong>{sourceSyncResult.push?.deleted_remote_records?.length ?? 0}</div>
                            </div>
                          </div>
                          <div className="import-source-sync-block">
                            <strong className="import-source-sync-block-title">Pull</strong>
                            <div className="import-source-preview-grid">
                              <div><strong>processed_changes：</strong>{sourceSyncResult.pull?.processed_changes ?? 0}</div>
                              <div><strong>applied_creates：</strong>{sourceSyncResult.pull?.applied_creates ?? 0}</div>
                              <div><strong>applied_updates：</strong>{sourceSyncResult.pull?.applied_updates ?? 0}</div>
                              <div><strong>applied_deletes：</strong>{sourceSyncResult.pull?.applied_deletes ?? 0}</div>
                              <div><strong>written_conflicts：</strong>{sourceSyncResult.pull?.written_conflicts ?? 0}</div>
                              <div><strong>skipped_echoes：</strong>{sourceSyncResult.pull?.skipped_echoes ?? 0}</div>
                            </div>
                          </div>
                        </div>
                      ) : (
                        <div className="import-source-preview-grid">
                          <div><strong>匹配文件：</strong>{sourceSyncResult.summary?.matched_files ?? 0}</div>
                          <div><strong>扫描记录：</strong>{sourceSyncResult.summary?.scanned_records ?? 0}</div>
                          <div><strong>created：</strong>{sourceSyncResult.summary?.created ?? 0}</div>
                          <div><strong>updated：</strong>{sourceSyncResult.summary?.updated ?? 0}</div>
                          <div><strong>noop：</strong>{sourceSyncResult.summary?.noop ?? 0}</div>
                          <div><strong>conflicts：</strong>{sourceSyncResult.summary?.conflicts ?? 0}</div>
                          <div><strong>marker_updates：</strong>{sourceSyncResult.summary?.marker_updates ?? 0}</div>
                          <div><strong>deleted_remote：</strong>{sourceSyncResult.summary?.deleted_remote_records?.length ?? 0}</div>
                        </div>
                      )}
                      <div className="import-hint">
                        状态文件：{sourceSyncResult.state_path}；冲突目录：{sourceSyncResult.conflicts_dir}
                        {sourceSyncResult.inbox_dir ? `；Inbox：${sourceSyncResult.inbox_dir}` : ''}
                      </div>
                      {sourceSyncAttention ? (
                        <div className={`import-diagnostics-alert import-diagnostics-alert--${sourceSyncAttention.tone}`} role="status">
                          {sourceSyncAttention.message}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="import-source-panel">
                <div className="import-source-panel-header">
                  <div>
                    <h2 className="import-source-panel-title">当前源状态</h2>
                    <p className="import-source-panel-copy">聚合当前源的本地 state 与远端 workspace 状态，便于判断是否需要拉取、恢复或处理冲突。</p>
                  </div>
                  <button
                    type="button"
                    className="import-secondary-btn"
                    onClick={() => loadSourceStatus(selectedSourceId, { showError: true })}
                    disabled={!selectedSourceId || sourceStatusLoading}
                  >
                    {sourceStatusLoading ? '刷新中...' : '刷新当前状态'}
                  </button>
                </div>

                {sourceStatusError ? (
                  <div className="import-error-inline" role="alert">{sourceStatusError}</div>
                ) : null}

                {sourceStatusResult ? (
                  <div className="import-source-status-card" role="status">
                    <div className="import-source-preview-grid">
                      <div><strong>匹配文件：</strong>{sourceStatusResult.matched_files ?? 0}</div>
                      <div><strong>last_pulled_seq：</strong>{sourceStatusResult.local_state?.last_pulled_seq ?? 0}</div>
                    </div>
                    <div className="import-source-sync-split">
                      <div className="import-source-sync-block">
                        <strong className="import-source-sync-block-title">Local State</strong>
                        <div className="import-source-preview-grid">
                          <div><strong>tracked：</strong>{sourceStatusResult.local_state?.tracked_records ?? 0}</div>
                          <div><strong>synced：</strong>{sourceStatusResult.local_state?.synced_records ?? 0}</div>
                          <div><strong>deleted：</strong>{sourceStatusResult.local_state?.deleted_records ?? 0}</div>
                          <div><strong>conflicts：</strong>{sourceStatusResult.local_state?.conflict_records ?? 0}</div>
                          <div><strong>recent_mutations：</strong>{sourceStatusResult.local_state?.recent_mutation_ids ?? 0}</div>
                        </div>
                      </div>
                      <div className="import-source-sync-block">
                        <strong className="import-source-sync-block-title">Remote State</strong>
                        <div className="import-source-preview-grid">
                          <div><strong>active：</strong>{sourceStatusResult.remote_state?.active_records ?? 0}</div>
                          <div><strong>tombstones：</strong>{sourceStatusResult.remote_state?.tombstones ?? 0}</div>
                          <div><strong>conflicts：</strong>{sourceStatusResult.remote_state?.conflicts ?? 0}</div>
                          <div><strong>last_change_seq：</strong>{sourceStatusResult.remote_state?.last_change_seq ?? 0}</div>
                        </div>
                      </div>
                    </div>
                    <div className="import-hint">
                      状态={sourceStatusResult.status || 'healthy'}；状态文件：{sourceStatusResult.state_path}；冲突目录：{sourceStatusResult.conflicts_dir}；Inbox：{sourceStatusResult.inbox_dir}
                    </div>
                    {sourceStatusAttention ? (
                      <div className={`import-diagnostics-alert import-diagnostics-alert--${sourceStatusAttention.tone}`} role="status">
                        {sourceStatusAttention.message}
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="import-source-list-empty">
                    {selectedSourceId ? '点击“刷新当前状态”后，这里会显示本地与远端状态摘要。' : '先选择一个已保存同步源，再查看当前状态。'}
                  </div>
                )}
              </div>

              <ImportRunHistoryPanel
                runs={sourceOperationRuns}
                loading={importRunsLoading}
                error={importRunsError}
                onRefresh={() => loadImportRuns({ showError: true })}
                title={selectedSourceId ? 'Recent Source Operations' : 'Recent Source Operations (All)'}
              />
            </div>
          </div>
        ) : null}

        {result ? (
          <div className={`import-result ${result.success ? 'import-result--success' : 'import-result--error'}`} role={result.success ? 'status' : 'alert'}>
            <p className="import-result-title">最近结果</p>
            <p className="import-result-details">{result.message}</p>
            {result.details ? <p className="import-result-details">{result.details}</p> : null}
          </div>
        ) : (
          <div className="import-result" role="status">
            <p className="import-result-title">最近结果</p>
            <p className="import-result-details">完成 source 预览、保存配置或执行导入后，这里会显示最新状态。</p>
          </div>
        )}

        {error ? <div className="import-error-inline">{error}</div> : null}

        <div className={`import-actions ${activeTab === 'source' ? 'import-actions--source' : ''}`}>
          {activeTab === 'source' ? (
            <>
              <div className="import-actions-note">
                预览只读取路径匹配结果；push / pull / sync / restore 都使用当前已保存配置，未保存改动不会参与本次执行。
              </div>
              <div className="import-actions-group">
                <button
                  type="button"
                  className="import-secondary-btn"
                  onClick={runSourcePreview}
                  disabled={!canSubmit || loading}
                >
                  {loading ? '处理中...' : '预览当前源'}
                </button>
                <button
                  type="button"
                  className="import-secondary-btn"
                  onClick={handlePushSourceSetting}
                  disabled={!selectedSourceId || loading || Boolean(sourceSyncRunningAction)}
                >
                  {sourceSyncRunningAction === 'push' ? '推送中...' : '推送当前源'}
                </button>
                <button
                  type="button"
                  className="import-secondary-btn"
                  onClick={handlePullSourceSetting}
                  disabled={!selectedSourceId || loading || Boolean(sourceSyncRunningAction)}
                >
                  {sourceSyncRunningAction === 'pull' ? '拉取中...' : '拉取远端变更'}
                </button>
                <button
                  type="button"
                  className="import-secondary-btn"
                  onClick={handleSyncSourceSetting}
                  disabled={!selectedSourceId || loading || Boolean(sourceSyncRunningAction)}
                >
                  {sourceSyncRunningAction === 'sync' ? '双向同步中...' : '双向同步'}
                </button>
                <button
                  type="button"
                  className="import-secondary-btn"
                  onClick={handleRestoreSourceSetting}
                  disabled={!selectedSourceId || loading || Boolean(sourceSyncRunningAction)}
                >
                  {sourceSyncRunningAction === 'restore' ? '恢复中...' : '恢复已删除记录'}
                </button>
                <button
                  type="button"
                  className="import-secondary-btn import-secondary-btn--danger"
                  onClick={deleteSourceSetting}
                  disabled={!selectedSourceId || loading}
                >
                  删除当前源
                </button>
                <button type="submit" className="import-submit" disabled={!canSubmit || loading}>
                  {loading ? '保存中...' : (selectedSourceId ? '更新同步源' : '保存同步源')}
                </button>
              </div>
            </>
          ) : (
            <button type="submit" className="import-submit" disabled={!canSubmit}>
              {loading ? '导入中...' : '开始导入'}
            </button>
          )}
        </div>
      </form>
    </section>
  )
}
