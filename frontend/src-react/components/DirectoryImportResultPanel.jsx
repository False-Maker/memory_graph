function toSafeNumber(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function normalizeFailures(value) {
  if (!Array.isArray(value)) return []
  return value
    .filter((item) => item && typeof item === 'object')
    .map((item) => ({
      path: item.path ? String(item.path) : '-',
      reason: item.reason ? String(item.reason) : '-',
      attempts: toSafeNumber(item.attempts, 0),
      retryExhausted: Boolean(item.retry_exhausted),
    }))
}

function buildStatusBadge(status) {
  const normalized = String(status || '').toLowerCase()
  if (normalized === 'completed') {
    return { className: 'directory-import-result__badge directory-import-result__badge--ok', label: 'completed' }
  }
  if (normalized === 'no_files') {
    return { className: 'directory-import-result__badge directory-import-result__badge--muted', label: 'no_files' }
  }
  return { className: 'directory-import-result__badge directory-import-result__badge--warn', label: normalized || 'unknown' }
}

function buildSummary(result) {
  return {
    status: String(result?.status || 'unknown'),
    imported: toSafeNumber(result?.imported, 0),
    attempted: toSafeNumber(result?.attempted, 0),
    failed: toSafeNumber(result?.failed, 0),
    skipped: toSafeNumber(result?.skipped, 0),
    duplicatesSkipped: toSafeNumber(result?.duplicates_skipped, 0),
    retryableCount: toSafeNumber(result?.retryable_count, 0),
    retryableFailedFiles: normalizeFailures(result?.retryable_failed_files),
    message: result?.message ? String(result.message) : '',
  }
}

export default function DirectoryImportResultPanel({ result }) {
  if (!result || typeof result !== 'object') {
    return null
  }

  const summary = buildSummary(result)
  const badge = buildStatusBadge(summary.status)

  return (
    <section className="directory-import-result" aria-label="Directory import result">
      <header className="directory-import-result__header">
        <h3>目录导入结果</h3>
        <span className={badge.className}>{badge.label}</span>
      </header>

      {summary.message ? (
        <p className="directory-import-result__message">{summary.message}</p>
      ) : null}

      <div className="directory-import-result__metrics">
        <div className="directory-import-result__metric">
          <span>imported</span>
          <strong>{summary.imported}</strong>
        </div>
        <div className="directory-import-result__metric">
          <span>attempted</span>
          <strong>{summary.attempted}</strong>
        </div>
        <div className="directory-import-result__metric">
          <span>failed</span>
          <strong>{summary.failed}</strong>
        </div>
        <div className="directory-import-result__metric">
          <span>skipped</span>
          <strong>{summary.skipped}</strong>
        </div>
        <div className="directory-import-result__metric">
          <span>duplicates_skipped</span>
          <strong>{summary.duplicatesSkipped}</strong>
        </div>
        <div className="directory-import-result__metric">
          <span>retryable_count</span>
          <strong>{summary.retryableCount}</strong>
        </div>
      </div>

      <div className="directory-import-result__failures">
        <h4>retryable_failed_files</h4>
        {summary.retryableFailedFiles.length ? (
          <ul>
            {summary.retryableFailedFiles.map((item, index) => (
              <li key={`${item.path}-${index}`}>
                <div className="directory-import-result__failure-path">{item.path}</div>
                <div className="directory-import-result__failure-meta">
                  reason={item.reason} | attempts={item.attempts} | retry_exhausted={String(item.retryExhausted)}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="directory-import-result__empty">暂无可重试失败文件</p>
        )}
      </div>
    </section>
  )
}
