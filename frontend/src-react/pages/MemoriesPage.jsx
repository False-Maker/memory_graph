import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import apiClient from '../api/client'
import { MEMORIES_SMOKE_TEST_IDS } from './MemoriesPage.smoke-helpers'
import {
  buildCommunitiesHashHref,
  buildInitialMemoryContext,
  hasMemoryContextContent,
  normalizeMemoryContextPayload,
} from './MemoriesPage.context-helpers'
import './MemoriesPage.css'

const PAGE_SIZE = 20
const STATUS_FILTERS = [
  { value: 'active', label: 'Active' },
  { value: 'archived', label: 'Archived' },
  { value: 'all', label: 'All' }
]

function normalizeErrorMessage(error) {
  return error?.response?.data?.detail || error?.message || '加载记忆列表失败'
}

function formatCreatedAt(dateString) {
  if (!dateString) return '未知时间'
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) return '未知时间'
  return date.toLocaleString('zh-CN')
}

function buildMemoryTitle(memory) {
  return memory?.title || memory?.metadata?.title || '未命名记忆'
}

function buildMemoryPreview(memory) {
  const preview = memory?.preview || memory?.content || ''
  return preview.length > 240 ? `${preview.slice(0, 240)}...` : preview
}

function normalizeDisplayValue(value, fallback = '-') {
  if (Array.isArray(value)) return value.length ? value.join(', ') : fallback
  if (value === null || value === undefined || value === '') return fallback
  return String(value)
}

function normalizeMemoryProvenance(detailMemory) {
  const provenance = detailMemory?.provenance
  const metadata = detailMemory?.metadata
  return {
    type: normalizeDisplayValue(
      provenance?.type ?? metadata?.record_type ?? metadata?.source
    ),
    time: normalizeDisplayValue(
      provenance?.time ?? metadata?.timestamp ?? metadata?.external_updated_at ?? detailMemory?.created_at
    ),
    importedFrom: normalizeDisplayValue(
      provenance?.imported_from ?? metadata?.source_path ?? metadata?.external_id ?? metadata?.workspace_id
    ),
  }
}

function isMemoryArchived(memory) {
  return memory?.metadata?.archived === true
}

export default function MemoriesPage() {
  const navigate = useNavigate()
  const { memoryId: routeMemoryId } = useParams()
  const [statusFilter, setStatusFilter] = useState('active')
  const [memories, setMemories] = useState([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [refreshToken, setRefreshToken] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [detailMemory, setDetailMemory] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailError, setDetailError] = useState(null)
  const [detailContext, setDetailContext] = useState(() => buildInitialMemoryContext())
  const [detailContextLoading, setDetailContextLoading] = useState(false)
  const [detailContextError, setDetailContextError] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [archivingId, setArchivingId] = useState(null)
  const [actionError, setActionError] = useState(null)
  const [actionMessage, setActionMessage] = useState(null)

  useEffect(() => {
    let mounted = true

    async function loadMemories() {
      setLoading(true)
      setError(null)

      try {
        const response = await apiClient.get('/memories', {
          params: {
            limit: PAGE_SIZE,
            offset,
            status: statusFilter,
          },
        })

        if (!mounted) {
          return
        }

        setMemories(Array.isArray(response?.memories) ? response.memories : [])
        setTotal(Number(response?.total ?? 0))
      } catch (requestError) {
        if (!mounted) {
          return
        }
        setMemories([])
        setTotal(0)
        setError(normalizeErrorMessage(requestError))
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    loadMemories()

    return () => {
      mounted = false
    }
  }, [offset, refreshToken, statusFilter])

  useEffect(() => {
    setOffset(0)
  }, [statusFilter])

  async function loadMemoryDetail(memoryId) {
    if (!memoryId) {
      setDetailMemory(null)
      setDetailError(null)
      setDetailLoading(false)
      return
    }

    setDetailLoading(true)
    setDetailError(null)

    try {
      const response = await apiClient.get(`/memories/${memoryId}`)
      setDetailMemory(response ?? null)
    } catch (requestError) {
      setDetailMemory(null)
      setDetailError(normalizeErrorMessage(requestError))
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    loadMemoryDetail(routeMemoryId)
  }, [routeMemoryId, refreshToken])

  useEffect(() => {
    let mounted = true

    async function loadMemoryContext(memoryId) {
      if (!memoryId) {
        if (!mounted) return
        setDetailContext(buildInitialMemoryContext())
        setDetailContextError(null)
        setDetailContextLoading(false)
        return
      }

      if (mounted) {
        setDetailContextLoading(true)
        setDetailContextError(null)
      }

      try {
        const response = await apiClient.get(`/memories/${memoryId}/context`)
        if (!mounted) return
        setDetailContext(normalizeMemoryContextPayload(response))
      } catch (requestError) {
        if (!mounted) return
        setDetailContext(buildInitialMemoryContext())
        setDetailContextError(normalizeErrorMessage(requestError))
      } finally {
        if (mounted) {
          setDetailContextLoading(false)
        }
      }
    }

    loadMemoryContext(routeMemoryId)

    return () => {
      mounted = false
    }
  }, [routeMemoryId, refreshToken])

  function handleViewDetail(memoryId) {
    navigate(`/memories/${encodeURIComponent(memoryId)}`)
  }

  function handleCloseDetail() {
    navigate('/memories')
  }

  async function handleDeleteMemory(memoryId) {
    const confirmed = window.confirm('确认删除这条记忆吗？此操作不可恢复。')
    if (!confirmed) {
      return
    }

    setActionError(null)
    setActionMessage(null)
    setDeletingId(memoryId)

    try {
      await apiClient.delete(`/memories/${memoryId}`)

      const nextMemories = memories.filter((memory) => memory.id !== memoryId)
      const nextTotal = Math.max(0, total - 1)
      const shouldGoPrev = nextMemories.length === 0 && offset > 0

      if (routeMemoryId === memoryId) {
        navigate('/memories', { replace: true })
      }

      setTotal(nextTotal)

      if (shouldGoPrev) {
        setOffset((current) => Math.max(0, current - PAGE_SIZE))
      } else {
        setMemories(nextMemories)
        setRefreshToken((current) => current + 1)
      }
      setActionMessage('记忆已删除')
    } catch (requestError) {
      setActionError(normalizeErrorMessage(requestError))
    } finally {
      setDeletingId(null)
    }
  }

  async function handleToggleArchive(memoryId, archived) {
    setActionError(null)
    setActionMessage(null)
    setArchivingId(memoryId)

    try {
      if (archived) {
        await apiClient.post(`/memories/${memoryId}/unarchive`)
        setActionMessage('记忆已取消归档')
      } else {
        await apiClient.post(`/memories/${memoryId}/archive`)
        setActionMessage('记忆已归档')
      }
      setRefreshToken((current) => current + 1)
    } catch (requestError) {
      setActionError(normalizeErrorMessage(requestError))
    } finally {
      setArchivingId(null)
    }
  }

  const pageLabel = useMemo(() => {
    if (total === 0) {
      return '0 / 0'
    }

    const page = Math.floor(offset / PAGE_SIZE) + 1
    const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
    return `${page} / ${totalPages}`
  }, [offset, total])

  const canGoPrev = offset > 0
  const canGoNext = offset + PAGE_SIZE < total

  return (
    <section
      className="memories-page"
      aria-label="Memories page"
      data-testid={MEMORIES_SMOKE_TEST_IDS.page}
    >
      <header className="memories-header">
        <div>
          <h1>全部记忆</h1>
          <p className="memories-subtitle">查看当前本地记忆库中的完整记忆列表</p>
        </div>
        <div className="memories-toolbar">
          <span className="memories-total">共 {total} 条</span>
          <div className="memories-filter-group" role="tablist" aria-label="Memory status filters">
            {STATUS_FILTERS.map((filter) => (
              <button
                key={filter.value}
                type="button"
                className={`memories-filter-btn ${statusFilter === filter.value ? 'is-active' : ''}`}
                onClick={() => setStatusFilter(filter.value)}
                disabled={loading}
                data-testid={MEMORIES_SMOKE_TEST_IDS[`${filter.value}Filter`]}
              >
                {filter.label}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="memories-page-btn"
            onClick={() => setOffset((current) => Math.max(0, current - PAGE_SIZE))}
            disabled={!canGoPrev || loading}
            data-testid={MEMORIES_SMOKE_TEST_IDS.prevPageButton}
          >
            上一页
          </button>
          <span
            className="memories-page-label"
            data-testid={MEMORIES_SMOKE_TEST_IDS.pageLabel}
          >
            {pageLabel}
          </span>
          <button
            type="button"
            className="memories-page-btn"
            onClick={() => setOffset((current) => current + PAGE_SIZE)}
            disabled={!canGoNext || loading}
            data-testid={MEMORIES_SMOKE_TEST_IDS.nextPageButton}
          >
            下一页
          </button>
        </div>
      </header>

      {loading ? (
        <div
          className="memories-state-panel"
          role="status"
          data-testid={MEMORIES_SMOKE_TEST_IDS.statePanel}
        >
          加载中...
        </div>
      ) : null}

      {!loading && error ? (
        <div
          className="memories-state-panel memories-state-panel--error"
          role="alert"
          data-testid={MEMORIES_SMOKE_TEST_IDS.statePanel}
        >
          {error}
        </div>
      ) : null}

      {!loading && !error && actionError ? (
        <div
          className="memories-state-panel memories-state-panel--error"
          role="alert"
          data-testid={MEMORIES_SMOKE_TEST_IDS.statePanel}
        >
          {actionError}
        </div>
      ) : null}

      {!loading && !error && actionMessage ? (
        <div
          className="memories-state-panel memories-state-panel--success"
          role="status"
          data-testid={MEMORIES_SMOKE_TEST_IDS.statePanel}
        >
          {actionMessage}
        </div>
      ) : null}

      {!loading && !error && !actionError && !actionMessage && memories.length === 0 ? (
        <div className="memories-state-panel" data-testid={MEMORIES_SMOKE_TEST_IDS.statePanel}>
          暂无记忆数据
        </div>
      ) : null}

      {!loading && !error && memories.length > 0 ? (
        <div className="memories-list" data-testid={MEMORIES_SMOKE_TEST_IDS.list}>
          {memories.map((memory) => (
            <article
              className={`memories-item ${routeMemoryId === memory.id ? 'is-selected' : ''}`}
              key={memory.id}
              data-testid={MEMORIES_SMOKE_TEST_IDS.item}
              data-memory-id={memory.id}
            >
              <div className="memories-item-header">
                <div className="memories-item-title-block">
                  <h2>{buildMemoryTitle(memory)}</h2>
                  {isMemoryArchived(memory) ? (
                    <span className="memories-item-badge">Archived</span>
                  ) : null}
                </div>
                <time>{formatCreatedAt(memory.created_at)}</time>
              </div>
              <div className="memories-item-meta">
                <span>ID: {memory.id}</span>
                {memory?.metadata?.source ? <span>来源: {memory.metadata.source}</span> : null}
                {Array.isArray(memory?.metadata?.tags) && memory.metadata.tags.length > 0 ? (
                  <span>标签: {memory.metadata.tags.join(', ')}</span>
                ) : null}
              </div>
              <p className="memories-item-preview">{buildMemoryPreview(memory) || '暂无内容'}</p>
              <div className="memories-item-actions">
                <button
                  type="button"
                  className="memories-item-btn"
                  onClick={() => handleViewDetail(memory.id)}
                  disabled={deletingId === memory.id || archivingId === memory.id}
                  data-testid={MEMORIES_SMOKE_TEST_IDS.itemViewButton}
                >
                  查看详情
                </button>
                <button
                  type="button"
                  className="memories-item-btn"
                  onClick={() => handleToggleArchive(memory.id, isMemoryArchived(memory))}
                  disabled={deletingId === memory.id || archivingId === memory.id}
                  data-testid={MEMORIES_SMOKE_TEST_IDS.itemArchiveButton}
                >
                  {archivingId === memory.id ? '处理中...' : isMemoryArchived(memory) ? '取消归档' : '归档'}
                </button>
                <button
                  type="button"
                  className="memories-item-btn memories-item-btn--danger"
                  onClick={() => handleDeleteMemory(memory.id)}
                  disabled={deletingId === memory.id || archivingId === memory.id}
                  data-testid={MEMORIES_SMOKE_TEST_IDS.itemDeleteButton}
                >
                  {deletingId === memory.id ? '删除中...' : '删除'}
                </button>
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {routeMemoryId ? (
        <section
          className="memory-detail"
          aria-live="polite"
          data-testid={MEMORIES_SMOKE_TEST_IDS.detailPanel}
          data-memory-id={routeMemoryId}
        >
          <div className="memory-detail-header">
            <h2>记忆详情</h2>
            <div className="memory-detail-actions">
              {detailMemory ? (
                <button
                  type="button"
                  className="memories-item-btn"
                  onClick={() => handleToggleArchive(detailMemory.id, isMemoryArchived(detailMemory))}
                  disabled={deletingId === detailMemory.id || archivingId === detailMemory.id}
                  data-testid={MEMORIES_SMOKE_TEST_IDS.detailArchiveButton}
                >
                  {archivingId === detailMemory.id ? '处理中...' : isMemoryArchived(detailMemory) ? '取消归档' : '归档'}
                </button>
              ) : null}
              {detailMemory ? (
                <button
                  type="button"
                  className="memories-item-btn memories-item-btn--danger"
                  onClick={() => handleDeleteMemory(detailMemory.id)}
                  disabled={deletingId === detailMemory.id || archivingId === detailMemory.id}
                  data-testid={MEMORIES_SMOKE_TEST_IDS.detailDeleteButton}
                >
                  {deletingId === detailMemory.id ? '删除中...' : '删除'}
                </button>
              ) : null}
              <button
                type="button"
                className="memories-item-btn"
                onClick={handleCloseDetail}
                data-testid={MEMORIES_SMOKE_TEST_IDS.detailCloseButton}
              >
                关闭
              </button>
            </div>
          </div>

          {detailLoading ? (
            <p
              className="memory-detail-state"
              role="status"
              data-testid={MEMORIES_SMOKE_TEST_IDS.detailState}
            >
              加载详情中...
            </p>
          ) : null}

          {!detailLoading && detailError ? (
            <p
              className="memory-detail-state memory-detail-state--error"
              role="alert"
              data-testid={MEMORIES_SMOKE_TEST_IDS.detailState}
            >
              {detailError}
            </p>
          ) : null}

          {!detailLoading && !detailError && detailMemory ? (
            <div className="memory-detail-content">
              {(() => {
                const sourceSummary = normalizeMemoryProvenance(detailMemory)
                return (
                  <section className="memory-provenance" aria-label="来源摘要">
                    <h3>来源摘要</h3>
                    <dl className="memory-provenance-grid">
                      <div>
                        <dt>source_type</dt>
                        <dd>{sourceSummary.type}</dd>
                      </div>
                      <div>
                        <dt>source_time</dt>
                        <dd>{sourceSummary.time}</dd>
                      </div>
                      <div>
                        <dt>imported_from</dt>
                        <dd>{sourceSummary.importedFrom}</dd>
                      </div>
                      <div>
                        <dt>lifecycle</dt>
                        <dd data-testid={MEMORIES_SMOKE_TEST_IDS.detailLifecycleValue}>
                          {isMemoryArchived(detailMemory) ? 'archived' : 'active'}
                        </dd>
                      </div>
                    </dl>
                  </section>
                )
              })()}
              <p>
                <strong>ID:</strong> {detailMemory.id}
              </p>
              <p>
                <strong>创建时间:</strong> {formatCreatedAt(detailMemory.created_at)}
              </p>
              <p className="memory-detail-block">
                <strong>内容:</strong>
                <span>{detailMemory.content || '暂无内容'}</span>
              </p>
              <div className="memory-detail-block">
                <strong>Metadata:</strong>
                {detailMemory?.metadata ? (
                  <dl className="memory-detail-metadata">
                    {Object.entries(detailMemory.metadata).map(([key, value]) => (
                      <div key={key} className="memory-detail-metadata-item">
                        <dt>{key}</dt>
                        <dd>
                          {Array.isArray(value)
                            ? value.join(', ') || '-'
                            : value === null || value === undefined || value === ''
                              ? '-'
                              : String(value)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <span>无 metadata</span>
                )}
              </div>

              <section
                className="memory-context-section"
                aria-label="关联社区"
                data-testid={MEMORIES_SMOKE_TEST_IDS.communitiesSection}
              >
                <h3>关联社区</h3>
                {detailContextLoading ? (
                  <div className="memory-context-empty">加载关联社区中...</div>
                ) : detailContextError ? (
                  <div className="memory-context-empty">{detailContextError}</div>
                ) : detailContext.communities.length > 0 ? (
                  <ul className="memory-context-list">
                    {detailContext.communities.map((community) => {
                      const communityHref = buildCommunitiesHashHref(community?.id)
                      return (
                        <li key={community?.id || community?.title || 'community'}>
                          <div className="memory-context-row">
                            <strong>{community?.title || community?.id || '未命名社区'}</strong>
                            <span className="memory-context-meta">
                              level={community?.level ?? '-'} | entities={community?.entity_count ?? 0}
                            </span>
                          </div>
                          {community?.summary ? <p>{community.summary}</p> : null}
                          {communityHref ? (
                            <Link
                              to={communityHref}
                              className="memory-context-link"
                              data-testid={MEMORIES_SMOKE_TEST_IDS.communityLink}
                            >
                              跳转到社区详情
                            </Link>
                          ) : null}
                        </li>
                      )
                    })}
                  </ul>
                ) : (
                  <div className="memory-context-empty">暂无关联社区</div>
                )}
              </section>

              <section
                className="memory-context-section"
                aria-label="关联实体"
                data-testid={MEMORIES_SMOKE_TEST_IDS.entitiesSection}
              >
                <h3>关联实体</h3>
                {detailContextLoading ? (
                  <div className="memory-context-empty">加载关联实体中...</div>
                ) : detailContextError ? (
                  <div className="memory-context-empty">{detailContextError}</div>
                ) : detailContext.entities.length > 0 ? (
                  <ul className="memory-context-list">
                    {detailContext.entities.map((entity) => (
                      <li key={entity?.id || entity?.name || 'entity'}>
                        <div className="memory-context-row">
                          <strong>{entity?.name || entity?.id || '未命名实体'}</strong>
                          <span className="memory-context-meta">
                            type={entity?.type || '-'} | confidence={entity?.confidence ?? '-'}
                          </span>
                        </div>
                        {entity?.mention_text ? <p>{entity.mention_text}</p> : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="memory-context-empty">暂无关联实体</div>
                )}
              </section>

              {!detailContextLoading && !detailContextError && !hasMemoryContextContent(detailContext) ? (
                <div className="memory-context-empty">当前记忆还没有可展示的图谱上下文</div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  )
}
