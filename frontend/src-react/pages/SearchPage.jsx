import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import queryApi from '../api/query'
import { buildDiagnosticsHref } from './DiagnosticsPage.helpers'
import { buildCommunitiesHashHref } from './SearchPage.community-links'
import { SEARCH_SMOKE_TEST_IDS } from './SearchPage.smoke-helpers'
import './SearchPage.css'

const STRATEGY_OPTIONS = [
  {
    value: 'local',
    label: '本地检索',
    description: '基于实体关联的精确搜索'
  },
  {
    value: 'global',
    label: '全局检索',
    description: '跨社区的主题搜索'
  },
  {
    value: 'hybrid',
    label: '混合检索',
    description: '结合本地和全局的全面搜索'
  }
]

const DEFAULT_TOP_K = 10

function normalizeErrorMessage(error) {
  return error?.response?.data?.detail || error?.message || '搜索失败，请稍后重试'
}

function normalizeMemoryDetailError(error) {
  return error?.response?.data?.detail || error?.message || '加载来源详情失败'
}

function formatPercent(value) {
  if (typeof value !== 'number') return '-'
  return `${(value * 100).toFixed(1)}%`
}

function formatDateTime(value) {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return String(value)
  return parsed.toLocaleString('zh-CN', { hour12: false })
}

function normalizeMetadataValue(value) {
  if (Array.isArray(value)) return value.length ? value.join(', ') : '-'
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

function hasReadableValue(value) {
  if (Array.isArray(value)) return value.length > 0
  return value !== null && value !== undefined && value !== ''
}

function normalizeSourceProvenance(provenance) {
  if (typeof provenance === 'string') {
    return {
      type: provenance,
      time: '-',
      importedFrom: '-'
    }
  }

  if (!provenance || typeof provenance !== 'object' || Array.isArray(provenance)) {
    return {
      type: '-',
      time: '-',
      importedFrom: '-'
    }
  }

  const typeRaw = [
    provenance.source_type,
    provenance.sourceType,
    provenance.type,
    provenance.record_type,
    provenance.recordType,
    provenance.source,
    provenance.source_system,
    provenance.sourceSystem
  ].find(hasReadableValue)

  const timeRaw = [
    provenance.timestamp,
    provenance.imported_at,
    provenance.importedAt,
    provenance.created_at,
    provenance.createdAt,
    provenance.time
  ].find(hasReadableValue)

  const importedFromRaw = [
    provenance.imported_from,
    provenance.importedFrom,
    provenance.source_path,
    provenance.sourcePath,
    provenance.path,
    provenance.external_id,
    provenance.externalId,
    provenance.origin
  ].find(hasReadableValue)

  return {
    type: normalizeMetadataValue(typeRaw),
    time: timeRaw ? formatDateTime(timeRaw) : '-',
    importedFrom: normalizeMetadataValue(importedFromRaw)
  }
}

function buildSourceItemKey(source, index) {
  return source?.memory_id ? `${source.memory_id}-${index}` : `source-${index}`
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [strategy, setStrategy] = useState('hybrid')
  const [topK, setTopK] = useState(DEFAULT_TOP_K)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [validationError, setValidationError] = useState(null)
  const [expandedSourceMap, setExpandedSourceMap] = useState({})
  const [memoryDetailsById, setMemoryDetailsById] = useState({})
  const [queryRunMeta, setQueryRunMeta] = useState({ runId: null, sessionId: null })

  const hasSearched = useMemo(() => Boolean(result) || Boolean(error), [result, error])

  async function runSearch(nextQuery) {
    const trimmed = nextQuery.trim()
    if (!trimmed) {
      setValidationError('请输入问题后再搜索')
      return
    }

    setValidationError(null)
    setError(null)
    setResult(null)
    setExpandedSourceMap({})
    setMemoryDetailsById({})
    setQueryRunMeta({ runId: null, sessionId: null })
    setLoading(true)

    try {
      const response = await queryApi.graphRagQueryWithMeta(trimmed, {
        mode: strategy,
        topK,
        includeSources: true
      })
      setResult(response.data)
      setQueryRunMeta({
        runId: response.runId,
        sessionId: response.sessionId
      })
    } catch (requestError) {
      setError(normalizeErrorMessage(requestError))
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(event) {
    event.preventDefault()
    runSearch(query)
  }

  async function ensureMemoryDetailLoaded(memoryId) {
    if (!memoryId) return

    const existing = memoryDetailsById[memoryId]
    if (existing?.loading || existing?.data || existing?.error) {
      return
    }

    setMemoryDetailsById((current) => ({
      ...current,
      [memoryId]: {
        loading: true,
        error: null,
        data: null
      }
    }))

    try {
      const detail = await queryApi.getMemory(memoryId)
      setMemoryDetailsById((current) => ({
        ...current,
        [memoryId]: {
          loading: false,
          error: null,
          data: detail
        }
      }))
    } catch (requestError) {
      setMemoryDetailsById((current) => ({
        ...current,
        [memoryId]: {
          loading: false,
          error: normalizeMemoryDetailError(requestError),
          data: null
        }
      }))
    }
  }

  function handleToggleSourceDetail(itemKey, memoryId) {
    const shouldExpand = !Boolean(expandedSourceMap[itemKey])
    setExpandedSourceMap((current) => ({
      ...current,
      [itemKey]: shouldExpand
    }))

    if (shouldExpand && memoryId) {
      ensureMemoryDetailLoaded(memoryId)
    }
  }

  return (
    <section
      className="search-page"
      aria-label="Search page"
      data-testid={SEARCH_SMOKE_TEST_IDS.page}
    >
      <header className="search-header">
        <h1>智能搜索</h1>
        <p className="search-subtitle">基于知识图谱的语义搜索</p>
      </header>

      <form
        className="search-form"
        onSubmit={handleSubmit}
        noValidate
        data-testid={SEARCH_SMOKE_TEST_IDS.form}
      >
        <div className="search-query-row">
          <input
            type="text"
            className="search-input"
            data-testid={SEARCH_SMOKE_TEST_IDS.queryInput}
            value={query}
            onChange={(event) => {
              setQuery(event.target.value)
              if (validationError) {
                setValidationError(null)
              }
            }}
            placeholder="输入您的问题..."
            aria-label="搜索问题"
          />
          <button
            type="submit"
            className="search-submit"
            disabled={loading}
            data-testid={SEARCH_SMOKE_TEST_IDS.submitButton}
          >
            {loading ? '搜索中...' : '搜索'}
          </button>
        </div>

        {validationError ? (
          <div
            className="search-inline-error"
            role="alert"
            data-testid={SEARCH_SMOKE_TEST_IDS.validationError}
          >
            {validationError}
          </div>
        ) : null}

        <div className="search-controls-row">
          <div className="search-control-group">
            <span className="search-control-label">检索模式</span>
            <div className="search-strategy-grid">
              {STRATEGY_OPTIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  className={`search-strategy-button ${strategy === option.value ? 'is-active' : ''}`}
                  onClick={() => setStrategy(option.value)}
                >
                  <span className="search-strategy-title">{option.label}</span>
                  <span className="search-strategy-description">{option.description}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="search-control-group search-control-group--slider">
            <label className="search-control-label" htmlFor="search-top-k">
              返回结果数量: <span className="search-slider-value">{topK}</span>
            </label>
            <input
              id="search-top-k"
              type="range"
              min="5"
              max="20"
              step="1"
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
              className="search-slider"
            />
            <div className="search-slider-range">
              <span>5</span>
              <span>20</span>
            </div>
          </div>
        </div>
      </form>

      <div className="search-results" aria-live="polite">
        {loading ? (
          <div
            className="search-state-panel"
            role="status"
            data-testid={SEARCH_SMOKE_TEST_IDS.loadingPanel}
          >
            <div className="search-spinner" />
            <span>正在搜索...</span>
          </div>
        ) : null}

        {!loading && error ? (
          <div
            className="search-state-panel search-state-panel--error"
            role="alert"
            data-testid={SEARCH_SMOKE_TEST_IDS.errorPanel}
          >
            <p className="search-state-message">{error}</p>
            <button type="button" className="search-retry" onClick={() => runSearch(query)}>
              重试
            </button>
          </div>
        ) : null}

        {!loading && !error && !hasSearched ? (
          <div
            className="search-state-panel search-state-panel--empty"
            data-testid={SEARCH_SMOKE_TEST_IDS.emptyPanel}
          >
            <p className="search-state-message">输入问题开始搜索</p>
            <p className="search-state-hint">支持本地、全局和混合检索模式</p>
          </div>
        ) : null}

        {!loading && !error && result ? (
          <div
            className="search-results-grid"
            data-testid={SEARCH_SMOKE_TEST_IDS.resultsGrid}
          >
            <article className="search-card search-card--answer">
              <div className="search-card-header">
                <h2>AI 回答</h2>
                <div className="search-card-actions">
                  {result.processing_time_ms ? (
                    <span className="search-metric">检索耗时: {result.processing_time_ms}ms</span>
                  ) : null}
                  {queryRunMeta.runId ? (
                    <Link
                      to={buildDiagnosticsHref({ tab: 'query-runs', runId: queryRunMeta.runId })}
                      className="search-source-memory-link"
                      data-testid={SEARCH_SMOKE_TEST_IDS.queryRunLink}
                    >
                      查看本次 trace
                    </Link>
                  ) : null}
                </div>
              </div>
              <div className="search-answer-text">{result.answer || '未找到答案'}</div>
            </article>

            <article className="search-card search-card--evidence">
              <div className="search-card-header">
                <h2>证据总览</h2>
              </div>
              <div className="search-evidence-overview">
                <span className="search-evidence-pill">检索模式: {strategy}</span>
                <span className="search-evidence-pill">命中记忆: {result.sources?.length || 0}</span>
                <span className="search-evidence-pill">命中社区: {result.communities?.length || 0}</span>
                <span className="search-evidence-pill">命中实体: {result.entities?.length || 0}</span>
              </div>
              <div className="search-query-entities">
                <span className="search-evidence-label">实体线索</span>
                {result.entities?.length ? (
                  <div className="search-chip-list">
                    {result.entities.map((entity, index) => (
                      <span className="search-chip" key={`${entity}-${index}`}>
                        {entity}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="search-empty-inline">未返回实体线索</span>
                )}
              </div>
            </article>

            {result.sources?.length ? (
              <article
                className="search-card"
                data-testid={SEARCH_SMOKE_TEST_IDS.memorySourcesCard}
              >
                <div className="search-card-header">
                  <h2>来源记忆</h2>
                  <span className="search-count-badge">{result.sources.length}</span>
                </div>
                <div className="search-source-list">
                  {result.sources.map((source, index) => {
                    const itemKey = buildSourceItemKey(source, index)
                    const provenance = normalizeSourceProvenance(source?.provenance)
                    const communityHref = buildCommunitiesHashHref(source?.community_id)

                    return (
                      <article
                        className="search-source-item"
                        key={source.memory_id || `source-${index}`}
                        data-testid={SEARCH_SMOKE_TEST_IDS.memorySourceItem}
                      >
                        <p className="search-source-content">{source.content}</p>
                        <dl className="search-source-meta-grid">
                          <div>
                            <dt>source_type</dt>
                            <dd>{provenance.type}</dd>
                          </div>
                          <div>
                            <dt>source_time</dt>
                            <dd>{provenance.time}</dd>
                          </div>
                          <div>
                            <dt>imported_from</dt>
                            <dd>{provenance.importedFrom}</dd>
                          </div>
                          <div>
                            <dt>memory_id</dt>
                            <dd>{source.memory_id || '-'}</dd>
                          </div>
                          <div>
                            <dt>relevance</dt>
                            <dd>{formatPercent(source.relevance)}</dd>
                          </div>
                          <div>
                            <dt>community_id</dt>
                            <dd>{source.community_id || '-'}</dd>
                          </div>
                          <div>
                            <dt>community_summary</dt>
                            <dd>{source.community_summary || '-'}</dd>
                          </div>
                        <div>
                          <dt>entities</dt>
                          <dd>{source.entities?.length ? source.entities.join(', ') : '-'}</dd>
                        </div>
                        <div>
                          <dt>source</dt>
                          <dd>{normalizeMetadataValue(source.source)}</dd>
                        </div>
                        <div>
                          <dt>title</dt>
                          <dd>{normalizeMetadataValue(source.title)}</dd>
                        </div>
                        <div>
                          <dt>workspace_id</dt>
                          <dd>{normalizeMetadataValue(source.workspace_id)}</dd>
                        </div>
                        <div>
                          <dt>timestamp</dt>
                          <dd>{formatDateTime(source.timestamp)}</dd>
                        </div>
                      </dl>
                        <div className="search-source-actions">
                          {source.memory_id ? (
                            <Link
                              to={`/memories/${encodeURIComponent(source.memory_id)}`}
                              className="search-source-memory-link"
                              data-testid={SEARCH_SMOKE_TEST_IDS.memoryLink}
                            >
                              跳转到记忆详情
                            </Link>
                          ) : null}
                          {communityHref ? (
                            <Link
                              to={communityHref}
                              className="search-source-community-link"
                              data-testid={SEARCH_SMOKE_TEST_IDS.sourceCommunityLink}
                            >
                              跳转到社区详情
                            </Link>
                          ) : null}
                          <button
                            type="button"
                            className="search-source-detail-toggle"
                            data-testid={SEARCH_SMOKE_TEST_IDS.sourceDetailToggle}
                            onClick={() => handleToggleSourceDetail(itemKey, source.memory_id)}
                          >
                            {expandedSourceMap[itemKey] ? '收起来源详情' : '展开来源详情'}
                          </button>
                        </div>
                        {expandedSourceMap[itemKey] ? (
                          !source.memory_id ? (
                            <div
                              className="search-source-detail-state"
                              data-testid={SEARCH_SMOKE_TEST_IDS.sourceDetailState}
                              role="status"
                              aria-live="polite"
                            >
                              该来源未返回 memory_id，无法拉取详情。
                            </div>
                          ) : memoryDetailsById[source.memory_id]?.loading ? (
                            <div
                              className="search-source-detail-state"
                              data-testid={SEARCH_SMOKE_TEST_IDS.sourceDetailState}
                              role="status"
                              aria-live="polite"
                            >
                              正在加载来源详情...
                            </div>
                          ) : memoryDetailsById[source.memory_id]?.error ? (
                            <div
                              className="search-source-detail-state search-source-detail-state--error"
                              data-testid={SEARCH_SMOKE_TEST_IDS.sourceDetailState}
                              role="alert"
                            >
                              {memoryDetailsById[source.memory_id].error}
                            </div>
                          ) : memoryDetailsById[source.memory_id]?.data ? (
                            <div
                              className="search-source-detail-panel"
                              data-testid={SEARCH_SMOKE_TEST_IDS.sourceDetailPanel}
                            >
                              <dl className="search-source-meta-grid search-source-meta-grid--details">
                                <div>
                                  <dt>id</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.id)}</dd>
                                </div>
                                <div>
                                  <dt>source</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.source)}</dd>
                                </div>
                                <div>
                                  <dt>workspace_id</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.workspace_id)}</dd>
                                </div>
                                <div>
                                  <dt>external_id</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.external_id)}</dd>
                                </div>
                                <div>
                                  <dt>source_path</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.source_path)}</dd>
                                </div>
                                <div>
                                  <dt>record_type</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.record_type)}</dd>
                                </div>
                                <div>
                                  <dt>title</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.title)}</dd>
                                </div>
                                <div>
                                  <dt>tags</dt>
                                  <dd>{normalizeMetadataValue(memoryDetailsById[source.memory_id].data.metadata?.tags)}</dd>
                                </div>
                                <div>
                                  <dt>timestamp</dt>
                                  <dd>{formatDateTime(memoryDetailsById[source.memory_id].data.metadata?.timestamp)}</dd>
                                </div>
                                <div>
                                  <dt>created_at</dt>
                                  <dd>{formatDateTime(memoryDetailsById[source.memory_id].data.created_at)}</dd>
                                </div>
                              </dl>
                            </div>
                          ) : null
                        ) : null}
                      </article>
                    )
                  })}
                </div>
              </article>
            ) : (
              <article
                className="search-card"
                data-testid={SEARCH_SMOKE_TEST_IDS.communitiesCard}
              >
                <div className="search-card-header">
                  <h2>来源记忆</h2>
                </div>
                <div className="search-empty-sources">暂无来源记忆</div>
              </article>
            )}

            {result.communities?.length ? (
              <article className="search-card">
                <div className="search-card-header">
                  <h2>命中社区</h2>
                  <span className="search-count-badge">{result.communities.length}</span>
                </div>
                <div className="search-source-list">
                  {result.communities.map((community, index) => {
                    const communityHref = buildCommunitiesHashHref(community.community_id)
                    return (
                      <article
                        className="search-source-item"
                        key={community.community_id || `community-${index}`}
                        data-testid={SEARCH_SMOKE_TEST_IDS.communitySourceItem}
                      >
                        <p className="search-source-content">{community.summary || '无社区摘要'}</p>
                        <dl className="search-source-meta-grid">
                          <div>
                            <dt>community_id</dt>
                            <dd>{community.community_id || '-'}</dd>
                          </div>
                          <div>
                            <dt>title</dt>
                            <dd>{community.title || '-'}</dd>
                          </div>
                          <div>
                            <dt>level</dt>
                            <dd>{typeof community.level === 'number' ? community.level : '-'}</dd>
                          </div>
                          <div>
                            <dt>relevance</dt>
                            <dd>{formatPercent(community.relevance)}</dd>
                          </div>
                          <div>
                            <dt>entities</dt>
                            <dd>{community.entities?.length ? community.entities.join(', ') : '-'}</dd>
                          </div>
                        </dl>
                        <div className="search-source-actions">
                          {communityHref ? (
                            <Link
                              to={communityHref}
                              className="search-source-community-link"
                              data-testid={SEARCH_SMOKE_TEST_IDS.communityLink}
                            >
                              跳转到社区详情
                            </Link>
                          ) : (
                            <span className="search-source-link-disabled">该社区缺少 community_id</span>
                          )}
                        </div>
                      </article>
                    )
                  })}
                </div>
              </article>
            ) : (
              <article className="search-card">
                <div className="search-card-header">
                  <h2>命中社区</h2>
                </div>
                <div className="search-empty-sources">暂无社区证据</div>
              </article>
            )}
          </div>
        ) : null}
      </div>
    </section>
  )
}
