import './ImportRunHistoryPanel.css'
import {
  buildRunKey,
  buildRunSourceSummary,
  buildRunStatusBadge,
  buildRunSummary,
  buildRunTypeLabel,
  canRetryRun,
  formatDateTime,
  normalizeDisplayValue,
} from './ImportRunHistoryPanel.helpers'

export default function ImportRunHistoryPanel({
  runs = [],
  loading = false,
  error = null,
  onRefresh = null,
  onRetry = null,
  retryingRunId = null,
  title = 'Recent Import Runs',
}) {
  const normalizedRuns = Array.isArray(runs) ? runs : []

  return (
    <section className="import-run-history-panel" aria-label="Recent import runs">
      <div className="import-run-history-head">
        <div>
          <h2>{title}</h2>
          <p>展示最近导入批次时间、类型与结果摘要，便于快速定位失败批次。</p>
        </div>
        {typeof onRefresh === 'function' ? (
          <button
            type="button"
            className="import-run-history-refresh"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? '刷新中...' : '刷新'}
          </button>
        ) : null}
      </div>

      {error ? (
        <div className="import-run-history-alert import-run-history-alert--error" role="alert">
          {normalizeDisplayValue(error)}
        </div>
      ) : null}

      {loading && normalizedRuns.length === 0 ? (
        <div className="import-run-history-empty" role="status">
          正在加载 recent import runs...
        </div>
      ) : null}

      {!loading && !error && normalizedRuns.length === 0 ? (
        <div className="import-run-history-empty">
          暂无导入记录。完成一次导入后这里会显示最近批次摘要。
        </div>
      ) : null}

      {normalizedRuns.length > 0 ? (
        <ul className="import-run-history-list">
          {normalizedRuns.map((run, index) => {
            const badge = buildRunStatusBadge(run)
            const runKey = buildRunKey(run, index)
            const isRetrying = retryingRunId === runKey
            return (
              <li key={runKey}>
                <div className="import-run-history-item-head">
                  <strong>{normalizeDisplayValue(buildRunTypeLabel(run))}</strong>
                  <span className={badge.className}>{badge.label}</span>
                </div>
                <div className="import-run-history-item-submeta">{buildRunSourceSummary(run)}</div>
                <div className="import-run-history-item-meta">
                  started_at={formatDateTime(run?.started_at || run?.created_at)} | finished_at=
                  {formatDateTime(run?.finished_at || run?.updated_at)}
                </div>
                <div className="import-run-history-item-summary">{buildRunSummary(run)}</div>
                {run?.message ? (
                  <div className="import-run-history-item-message">{normalizeDisplayValue(run.message)}</div>
                ) : null}
                {typeof onRetry === 'function' && canRetryRun(run) ? (
                  <div className="import-run-history-item-actions">
                    <button
                      type="button"
                      className="import-run-history-retry"
                      onClick={() => onRetry(run)}
                      disabled={loading || isRetrying}
                    >
                      {isRetrying ? '重试中...' : '重试目录导入'}
                    </button>
                  </div>
                ) : null}
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}
