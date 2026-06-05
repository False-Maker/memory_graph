export function formatDateTime(value) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

export function normalizeCount(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

export function normalizeDisplayValue(value, fallback = '-') {
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

export function buildRunStatusBadge(run) {
  const status = String(run?.status || '').toLowerCase()
  if (status === 'completed' || status === 'success' || status === 'succeeded') {
    return { label: status || 'completed', className: 'import-run-history-badge import-run-history-badge--success' }
  }
  if (status === 'partial') {
    return { label: 'partial', className: 'import-run-history-badge import-run-history-badge--neutral' }
  }
  if (status === 'failed' || status === 'error') {
    return { label: status || 'failed', className: 'import-run-history-badge import-run-history-badge--error' }
  }
  return { label: status || 'unknown', className: 'import-run-history-badge import-run-history-badge--neutral' }
}

export function buildRunSummary(run) {
  const runType = normalizeRunType(run)
  const summary = run?.summary
  if (runType === 'source_push' || runType === 'source_restore') {
    return `matched=${normalizeCount(summary?.matched_files)} | scanned=${normalizeCount(summary?.scanned_records)} | created=${normalizeCount(summary?.created)} | updated=${normalizeCount(summary?.updated)} | conflicts=${normalizeCount(summary?.conflicts)}`
  }
  if (runType === 'source_pull') {
    return `processed=${normalizeCount(summary?.processed_changes)} | creates=${normalizeCount(summary?.applied_creates)} | updates=${normalizeCount(summary?.applied_updates)} | deletes=${normalizeCount(summary?.applied_deletes)} | conflicts=${normalizeCount(summary?.written_conflicts)}`
  }
  if (runType === 'source_sync') {
    return `push(created=${normalizeCount(summary?.push?.created)}, updated=${normalizeCount(summary?.push?.updated)}, conflicts=${normalizeCount(summary?.push?.conflicts)}) | pull(processed=${normalizeCount(summary?.pull?.processed_changes)}, conflicts=${normalizeCount(summary?.pull?.written_conflicts)})`
  }

  const imported = normalizeCount(run?.imported)
  const attempted = normalizeCount(run?.attempted)
  const failed = normalizeCount(run?.failed)
  const skipped = normalizeCount(run?.skipped)
  return `imported=${imported} | attempted=${attempted} | failed=${failed} | skipped=${skipped}`
}

function normalizeRunType(run) {
  return String(run?.run_type || run?.type || '').toLowerCase()
}

export function buildRunTypeLabel(run) {
  const runType = normalizeRunType(run)
  if (runType === 'directory_import') return '目录导入'
  if (runType === 'file_import') return '文件导入'
  if (runType === 'conversation_import') return '会话导入'
  if (runType === 'text_import') return '文本导入'
  if (runType === 'source_push') return '同步源推送'
  if (runType === 'source_pull') return '同步源拉取'
  if (runType === 'source_sync') return '同步源双向同步'
  if (runType === 'source_restore') return '同步源恢复'
  return runType || 'unknown'
}

export function buildRunSourceSummary(run) {
  const runType = normalizeRunType(run)
  const directoryPath = run?.directory_path || run?.source_path
  if (runType === 'directory_import' && directoryPath) {
    return `目录: ${String(directoryPath)}`
  }

  if (runType.startsWith('source_')) {
    if (run?.label && run?.workspace_id) {
      return `同步源: ${String(run.label)} | workspace=${String(run.workspace_id)}`
    }
    if (run?.label) {
      return `同步源: ${String(run.label)}`
    }
    if (run?.source_id) {
      return `同步源 ID: ${String(run.source_id)}`
    }
  }

  if (run?.filename) {
    return `文件: ${String(run.filename)}`
  }

  if (run?.source) {
    return `来源: ${String(run.source)}`
  }

  if (run?.detail) {
    return `详情: ${String(run.detail)}`
  }

  return '-'
}

export function buildRunKey(run, index) {
  if (run?.run_id) return String(run.run_id)
  if (run?.id) return String(run.id)
  if (run?.started_at) return `${run.started_at}-${index}`
  return `import-run-${index}`
}

export function canRetryRun(run) {
  return String(run?.run_type || run?.type || '').toLowerCase() === 'directory_import' && run?.retryable === true && Boolean(run?.id || run?.run_id)
}
