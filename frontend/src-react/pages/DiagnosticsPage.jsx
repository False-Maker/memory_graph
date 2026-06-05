import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { diagnosticsApi } from '../api/diagnostics'
import { DIAGNOSTICS_SMOKE_TEST_IDS } from './DiagnosticsPage.smoke-helpers'
import {
  buildDiagnosticsHref,
  buildQueryRunsRequestParams,
  normalizeDiagnosticsTab,
  normalizeMcpStatus,
  normalizeOperatorSummary,
  normalizeQueryRunDetail,
  normalizeQueryRunsResponse,
  normalizeRecentFailures,
} from './DiagnosticsPage.helpers'
import { buildRuntimeDiagnosticsSummary, normalizeRuntimeDiagnostics } from './settings-runtime-diagnostics'
import './DiagnosticsPage.css'

const QUERY_RUN_FILTER_DEFAULTS = {
  status: '',
  strategy: '',
  layerUsed: '',
  sessionId: '',
  limit: 20,
}

function formatDateTime(value) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function normalizeDisplayValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (Array.isArray(value)) return value.length ? value.join(', ') : '-'
  if (typeof value === 'boolean') return value ? '是' : '否'
  return String(value)
}

function RuntimeSection({ runtimeDiagnostics }) {
  const summary = buildRuntimeDiagnosticsSummary(runtimeDiagnostics)
  const normalized = normalizeRuntimeDiagnostics(runtimeDiagnostics)

  return (
    <section className="diagnostics-panel" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.runtimeSection}>
      <header className="diagnostics-panel-header">
        <h2>Runtime</h2>
        <span className={`diagnostics-status diagnostics-status--${summary.tone}`}>{summary.message}</span>
      </header>

      {summary.detail ? <p className="diagnostics-panel-copy">{summary.detail}</p> : null}

      <div className="diagnostics-grid">
        <article className="diagnostics-card">
          <h3>Provider</h3>
          <dl>
            <div><dt>当前 Provider</dt><dd>{normalizeDisplayValue(normalized.checks.provider.current_provider)}</dd></div>
            <div><dt>健康</dt><dd>{normalized.checks.provider.ok ? 'OK' : 'ATTN'}</dd></div>
            <div><dt>当前错误</dt><dd>{normalizeDisplayValue(normalized.checks.provider.current_error)}</dd></div>
          </dl>
        </article>

        <article className="diagnostics-card">
          <h3>Stores</h3>
          <dl>
            <div><dt>SQLite</dt><dd>{normalized.checks.sqlite.ok ? 'OK' : 'ATTN'}</dd></div>
            <div><dt>Vector Store</dt><dd>{normalized.checks.vector_store.ok ? 'OK' : 'ATTN'}</dd></div>
            <div><dt>索引文档</dt><dd>{normalizeDisplayValue(normalized.checks.vector_store.state?.indexed_documents)}</dd></div>
          </dl>
        </article>

        <article className="diagnostics-card">
          <h3>Sidecar</h3>
          <dl>
            <div><dt>状态</dt><dd>{runtimeDiagnostics?.sidecar?.ok ? 'OK' : 'ATTN'}</dd></div>
            <div><dt>Health</dt><dd>{normalizeDisplayValue(runtimeDiagnostics?.sidecar?.health?.status)}</dd></div>
            <div><dt>Ready</dt><dd>{normalizeDisplayValue(runtimeDiagnostics?.sidecar?.ready?.status)}</dd></div>
            <div><dt>细节</dt><dd>{normalizeDisplayValue(runtimeDiagnostics?.sidecar?.detail)}</dd></div>
          </dl>
        </article>

        <article className="diagnostics-card">
          <h3>Task Chain / Collectors</h3>
          <dl>
            <div><dt>Task Chain</dt><dd>{normalizeDisplayValue(normalized.task_chain.status)}</dd></div>
            <div><dt>Configured Sources</dt><dd>{normalizeDisplayValue(normalized.task_chain.configured_sources)}</dd></div>
            <div><dt>Collectors Running</dt><dd>{normalizeDisplayValue(runtimeDiagnostics?.collectors?.running)}</dd></div>
            <div><dt>Official Collectors</dt><dd>{normalizeDisplayValue(runtimeDiagnostics?.collectors?.official_collectors)}</dd></div>
          </dl>
        </article>
      </div>
    </section>
  )
}

function QueryRunsSection({ filters, onFiltersChange, queryRuns, selectedRun, onSelectRun }) {
  return (
    <section className="diagnostics-panel" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.queryRunsSection}>
      <header className="diagnostics-panel-header">
        <h2>Query Runs</h2>
      </header>

      <div className="diagnostics-filter-grid">
        <label>
          状态
          <input value={filters.status} onChange={(event) => onFiltersChange({ ...filters, status: event.target.value })} />
        </label>
        <label>
          Strategy
          <input value={filters.strategy} onChange={(event) => onFiltersChange({ ...filters, strategy: event.target.value })} />
        </label>
        <label>
          Layer
          <input value={filters.layerUsed} onChange={(event) => onFiltersChange({ ...filters, layerUsed: event.target.value })} />
        </label>
        <label>
          Session
          <input value={filters.sessionId} onChange={(event) => onFiltersChange({ ...filters, sessionId: event.target.value })} />
        </label>
      </div>

      <div className="diagnostics-query-layout">
        <div className="diagnostics-query-list">
          {queryRuns.runs.map((run) => (
            <button
              type="button"
              key={run.run_id}
              className={`diagnostics-query-item ${selectedRun?.run_id === run.run_id ? 'is-active' : ''}`}
              data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.queryRunItem}
              onClick={() => onSelectRun(run.run_id)}
            >
              <span className="diagnostics-query-title">{run.question || run.run_id}</span>
              <span className="diagnostics-query-meta">{run.status} / {run.strategy} / {run.layer_used || '-'}</span>
            </button>
          ))}
          {!queryRuns.runs.length ? <div className="diagnostics-empty">暂无 query run。</div> : null}
        </div>

        <article className="diagnostics-query-detail" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.queryRunDetail}>
          {selectedRun ? (
            <dl>
              <div><dt>run_id</dt><dd>{normalizeDisplayValue(selectedRun.run_id)}</dd></div>
              <div><dt>question</dt><dd>{normalizeDisplayValue(selectedRun.question)}</dd></div>
              <div><dt>status</dt><dd>{normalizeDisplayValue(selectedRun.status)}</dd></div>
              <div><dt>strategy</dt><dd>{normalizeDisplayValue(selectedRun.strategy)}</dd></div>
              <div><dt>layer_requested</dt><dd>{normalizeDisplayValue(selectedRun.layer_requested)}</dd></div>
              <div><dt>layer_used</dt><dd>{normalizeDisplayValue(selectedRun.layer_used)}</dd></div>
              <div><dt>fallback</dt><dd>{normalizeDisplayValue(selectedRun.layer_fallback_chain)}</dd></div>
              <div><dt>session_id</dt><dd>{normalizeDisplayValue(selectedRun.session_id)}</dd></div>
              <div><dt>started_at</dt><dd>{formatDateTime(selectedRun.started_at)}</dd></div>
              <div><dt>completed_at</dt><dd>{formatDateTime(selectedRun.completed_at)}</dd></div>
              <div><dt>failure_reason</dt><dd>{normalizeDisplayValue(selectedRun.failure_reason)}</dd></div>
            </dl>
          ) : (
            <div className="diagnostics-empty">选择一条 query run 查看详情。</div>
          )}
        </article>
      </div>
    </section>
  )
}

function MpcSection({ mcpStatus }) {
  return (
    <section className="diagnostics-panel" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.mcpSection}>
      <header className="diagnostics-panel-header">
        <h2>MCP</h2>
      </header>
      <dl className="diagnostics-detail-list">
        <div><dt>transport</dt><dd>{normalizeDisplayValue(mcpStatus.transport)}</dd></div>
        <div><dt>reachable</dt><dd>{normalizeDisplayValue(mcpStatus.reachable)}</dd></div>
        <div><dt>auth_enabled</dt><dd>{normalizeDisplayValue(mcpStatus.auth_enabled)}</dd></div>
        <div><dt>tools_count</dt><dd>{normalizeDisplayValue(mcpStatus.tools_count)}</dd></div>
        <div><dt>missing_core_tools</dt><dd>{normalizeDisplayValue(mcpStatus.missing_core_tools)}</dd></div>
        <div><dt>detail</dt><dd>{normalizeDisplayValue(mcpStatus.detail)}</dd></div>
        <div><dt>base_url</dt><dd>{normalizeDisplayValue(mcpStatus.base_url)}</dd></div>
      </dl>
    </section>
  )
}

function FailuresSection({ failures }) {
  return (
    <section className="diagnostics-panel" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.failuresSection}>
      <header className="diagnostics-panel-header">
        <h2>Recent Failures</h2>
      </header>
      {failures.length ? (
        <div className="diagnostics-failures-list">
          {failures.map((item, index) => (
            <article key={`${item.component}-${index}`} className={`diagnostics-failure diagnostics-failure--${item.severity}`} data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.failureItem}>
              <h3>{item.component} / {item.category}</h3>
              <p>{item.detail || '无 detail'}</p>
              <p>建议：{item.suggested_action || '无'}</p>
              <p>最近出现：{formatDateTime(item.last_seen_at)}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="diagnostics-empty">暂无 recent failures。</div>
      )}
    </section>
  )
}

export default function DiagnosticsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const search = useMemo(() => new URLSearchParams(location.search), [location.search])
  const activeTab = normalizeDiagnosticsTab(search.get('tab'))
  const selectedRunId = search.get('run_id')

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [operatorSummary, setOperatorSummary] = useState(normalizeOperatorSummary(null))
  const [runtimeDiagnostics, setRuntimeDiagnostics] = useState(normalizeRuntimeDiagnostics(null))
  const [mcpStatus, setMcpStatus] = useState(normalizeMcpStatus(null))
  const [queryRuns, setQueryRuns] = useState(normalizeQueryRunsResponse(null))
  const [selectedRun, setSelectedRun] = useState(null)
  const [queryRunFilters, setQueryRunFilters] = useState(QUERY_RUN_FILTER_DEFAULTS)

  async function loadOverview() {
    const [summary, runtime, mcp] = await Promise.all([
      diagnosticsApi.getOperatorSummary(),
      diagnosticsApi.getRuntimeDiagnostics(),
      diagnosticsApi.getMcpStatus(),
    ])
    setOperatorSummary(normalizeOperatorSummary(summary))
    setRuntimeDiagnostics(normalizeRuntimeDiagnostics(runtime))
    setMcpStatus(normalizeMcpStatus(mcp))
  }

  async function loadQueryRuns(nextFilters = queryRunFilters) {
    const payload = await diagnosticsApi.listQueryRuns(buildQueryRunsRequestParams(nextFilters))
    setQueryRuns(normalizeQueryRunsResponse(payload))
  }

  async function refreshPage() {
    setLoading(true)
    setError(null)
    try {
      await Promise.all([
        loadOverview(),
        loadQueryRuns(queryRunFilters),
      ])
    } catch (requestError) {
      setError(requestError?.message || '加载 diagnostics 失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshPage()
  }, [])

  useEffect(() => {
    loadQueryRuns(queryRunFilters).catch(() => {})
  }, [queryRunFilters.status, queryRunFilters.strategy, queryRunFilters.layerUsed, queryRunFilters.sessionId, queryRunFilters.limit])

  useEffect(() => {
    if (!selectedRunId) {
      setSelectedRun(null)
      return
    }
    diagnosticsApi.getQueryRun(selectedRunId)
      .then((payload) => setSelectedRun(normalizeQueryRunDetail(payload)))
      .catch(() => setSelectedRun(null))
  }, [selectedRunId])

  function handleTabChange(tab) {
    navigate(buildDiagnosticsHref({ tab, runId: tab === 'query-runs' ? selectedRunId : null }))
  }

  function handleSelectRun(runId) {
    navigate(buildDiagnosticsHref({ tab: 'query-runs', runId }))
  }

  const recentFailures = useMemo(
    () => normalizeRecentFailures(runtimeDiagnostics),
    [runtimeDiagnostics]
  )

  return (
    <section className="diagnostics-page" aria-label="Diagnostics page" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.page}>
      <header className="diagnostics-page-header">
        <div>
          <h1>Diagnostics</h1>
          <p className="diagnostics-subtitle">运营、诊断与 query trace 统一入口。</p>
        </div>
        <button
          type="button"
          className="diagnostics-refresh-button"
          data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.refreshButton}
          onClick={refreshPage}
          disabled={loading}
        >
          {loading ? '刷新中...' : '刷新'}
        </button>
      </header>

      {error ? <div className="diagnostics-error">{error}</div> : null}

      <div className="diagnostics-tabs">
        <button type="button" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.tabOverview} className={activeTab === 'overview' ? 'is-active' : ''} onClick={() => handleTabChange('overview')}>Overview</button>
        <button type="button" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.tabQueryRuns} className={activeTab === 'query-runs' ? 'is-active' : ''} onClick={() => handleTabChange('query-runs')}>Query Runs</button>
        <button type="button" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.tabRuntime} className={activeTab === 'runtime' ? 'is-active' : ''} onClick={() => handleTabChange('runtime')}>Runtime</button>
        <button type="button" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.tabMcp} className={activeTab === 'mcp' ? 'is-active' : ''} onClick={() => handleTabChange('mcp')}>MCP</button>
        <button type="button" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.tabFailures} className={activeTab === 'failures' ? 'is-active' : ''} onClick={() => handleTabChange('failures')}>Failures</button>
      </div>

      {activeTab === 'overview' ? (
        <section className="diagnostics-panel" data-testid={DIAGNOSTICS_SMOKE_TEST_IDS.summarySection}>
          <header className="diagnostics-panel-header">
            <h2>Operator Summary</h2>
          </header>
          <div className="diagnostics-grid">
            <article className="diagnostics-card">
              <h3>Runtime</h3>
              <p>{normalizeDisplayValue(operatorSummary.runtime.status)}</p>
              <Link to={buildDiagnosticsHref({ tab: 'runtime' })}>查看 Runtime</Link>
            </article>
            <article className="diagnostics-card">
              <h3>Query Runs</h3>
              <p>{normalizeDisplayValue(operatorSummary.query_runs.total_recent)}</p>
              <Link to={buildDiagnosticsHref({ tab: 'query-runs' })}>查看 Query Runs</Link>
            </article>
            <article className="diagnostics-card">
              <h3>Recent Failures</h3>
              <p>{normalizeDisplayValue(operatorSummary.runtime.recent_failures_count)}</p>
              <Link to={buildDiagnosticsHref({ tab: 'failures' })}>查看 Failures</Link>
            </article>
            <article className="diagnostics-card">
              <h3>MCP</h3>
              <p>{normalizeDisplayValue(operatorSummary.mcp.tools_count)}</p>
              <Link to={buildDiagnosticsHref({ tab: 'mcp' })}>查看 MCP</Link>
            </article>
          </div>
        </section>
      ) : null}

      {activeTab === 'query-runs' ? (
        <QueryRunsSection
          filters={queryRunFilters}
          onFiltersChange={setQueryRunFilters}
          queryRuns={queryRuns}
          selectedRun={selectedRun}
          onSelectRun={handleSelectRun}
        />
      ) : null}

      {activeTab === 'runtime' ? <RuntimeSection runtimeDiagnostics={runtimeDiagnostics} /> : null}
      {activeTab === 'mcp' ? <MpcSection mcpStatus={mcpStatus} /> : null}
      {activeTab === 'failures' ? <FailuresSection failures={recentFailures} /> : null}
    </section>
  )
}
