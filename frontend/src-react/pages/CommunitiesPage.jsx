import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import communityApi from '../api/community'
import { COMMUNITIES_SMOKE_TEST_IDS } from './CommunitiesPage.smoke-helpers'
import {
  buildCommunityHash,
  buildInitialFacetData,
  buildInitialFacetErrors,
  buildInitialFacetLoading,
  hasAnyFacetContent,
  normalizeCommunityIdFromHash,
  normalizeFacetPayload,
} from './CommunitiesPage.detail-helpers'
import './CommunitiesPage.css'

const DEFAULT_ALGORITHM = 'leiden'
const DETAIL_SECTION_LABELS = {
  entities: '实体',
  relationships: '关系',
  ancestors: '上游社区',
  descendants: '下游社区',
}

function normalizeCommunitiesPayload(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.communities)) return payload.communities
  return []
}

function normalizeHierarchyPayload(payload) {
  if (payload && Array.isArray(payload.roots)) {
    return {
      roots: payload.roots,
      total_communities: payload.total_communities ?? payload.roots.length,
      max_level: payload.max_level ?? Math.max(0, ...payload.roots.map((node) => Number(node.level) || 0))
    }
  }

  return null
}

function normalizeErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

function buildLevelText(level) {
  const parsed = Number(level)
  if (Number.isNaN(parsed)) return 'Level -'
  return `Level ${parsed}`
}

function buildNodeList(nodes = [], depth = 0, onSelect, selectedId) {
  return nodes.map((node) => {
    const nodeId = String(node.id)
    const isSelected = selectedId === nodeId
    return (
      <div className="community-tree-node" key={`${nodeId}-${depth}`} style={{ '--community-node-depth': depth }}>
        <button
          type="button"
          className={`community-tree-node-content ${isSelected ? 'is-selected' : ''}`}
          onClick={() => onSelect(node)}
        >
          <span className="community-tree-title">{node.title || '未命名社区'}</span>
          <span className="community-tree-count">{node.entity_count ?? 0} 实体</span>
        </button>
        {Array.isArray(node.children) && node.children.length > 0 ? (
          <div className="community-tree-children">{buildNodeList(node.children, depth + 1, onSelect, selectedId)}</div>
        ) : null}
      </div>
    )
  })
}

export default function CommunitiesPage() {
  const [communities, setCommunities] = useState([])
  const [levels, setLevels] = useState([])
  const [currentLevel, setCurrentLevel] = useState(null)
  const [selectedAlgorithm, setSelectedAlgorithm] = useState(DEFAULT_ALGORITHM)
  const [showHierarchy, setShowHierarchy] = useState(false)
  const [hierarchy, setHierarchy] = useState(null)

  const [selectedCommunity, setSelectedCommunity] = useState(null)
  const [communityDetails, setCommunityDetails] = useState(null)
  const [communityFacetData, setCommunityFacetData] = useState(buildInitialFacetData)
  const [communityFacetLoading, setCommunityFacetLoading] = useState(buildInitialFacetLoading)
  const [communityFacetErrors, setCommunityFacetErrors] = useState(buildInitialFacetErrors)
  const [hashCommunityId, setHashCommunityId] = useState(() => normalizeCommunityIdFromHash(window.location.hash))
  const autoOpenRef = useRef(null)

  const [loading, setLoading] = useState(false)
  const [detecting, setDetecting] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [regeneratingSummary, setRegeneratingSummary] = useState(false)

  const [listError, setListError] = useState(null)
  const [hierarchyError, setHierarchyError] = useState(null)
  const [detailError, setDetailError] = useState(null)
  const [actionFeedback, setActionFeedback] = useState(null)

  const hasCommunities = communities.length > 0

  const filteredCommunities = useMemo(() => {
    if (currentLevel === null) return communities
    return communities.filter((community) => Number(community.level) === Number(currentLevel))
  }, [communities, currentLevel])

  const loadCommunities = useCallback(
    async (overrideLevel = currentLevel) => {
      setLoading(true)
      setListError(null)
      try {
        const params = {}
        if (overrideLevel !== null && overrideLevel !== undefined) {
          params.level = overrideLevel
        }
        const response = await communityApi.getCommunities(params)
        const nextCommunities = normalizeCommunitiesPayload(response)
        setCommunities(nextCommunities)

        const levelSet = new Set(
          nextCommunities
            .map((community) => Number(community.level))
            .filter((level) => !Number.isNaN(level))
        )
        setLevels(Array.from(levelSet).sort((left, right) => left - right))
      } catch (error) {
        setCommunities([])
        setLevels([])
        setListError(normalizeErrorMessage(error, '加载社区失败'))
      } finally {
        setLoading(false)
      }
    },
    [currentLevel]
  )

  const loadHierarchy = useCallback(async () => {
    setHierarchyError(null)
    try {
      const response = await communityApi.getFullHierarchy()
      setHierarchy(normalizeHierarchyPayload(response))
    } catch (error) {
      setHierarchy(null)
      setHierarchyError(normalizeErrorMessage(error, '加载层次结构失败'))
    }
  }, [])

  const loadCommunityDetail = useCallback(async (community) => {
    if (!community?.id) {
      setSelectedCommunity(null)
      setCommunityDetails(null)
      setCommunityFacetData(buildInitialFacetData())
      setCommunityFacetLoading(buildInitialFacetLoading())
      setCommunityFacetErrors(buildInitialFacetErrors())
      return
    }

    setSelectedCommunity(community)
    setCommunityDetails(null)
    setLoadingDetail(true)
    setDetailError(null)
    setActionFeedback(null)

    try {
      const response = await communityApi.getCommunity(community.id)
      setCommunityDetails(response)
    } catch (error) {
      setDetailError(normalizeErrorMessage(error, '社区详情加载失败'))
      setCommunityDetails(null)
    } finally {
      setLoadingDetail(false)
    }
  }, [])

  const loadCommunityFacets = useCallback(async (communityId) => {
    if (!communityId) {
      setCommunityFacetData(buildInitialFacetData())
      setCommunityFacetLoading(buildInitialFacetLoading())
      setCommunityFacetErrors(buildInitialFacetErrors())
      return
    }

    const nextLoading = {
      entities: true,
      relationships: true,
      ancestors: true,
      descendants: true,
    }
    setCommunityFacetLoading(nextLoading)
    setCommunityFacetErrors(buildInitialFacetErrors())

    const requests = {
      entities: communityApi.getCommunityEntities(communityId, { limit: 20 }),
      relationships: communityApi.getCommunityRelationships(communityId, { limit: 20 }),
      ancestors: communityApi.getCommunityAncestors(communityId, { limit: 20 }),
      descendants: communityApi.getCommunityDescendants(communityId, { limit: 20 }),
    }

    const keys = Object.keys(requests)
    const settled = await Promise.allSettled(keys.map((key) => requests[key]))

    const nextData = buildInitialFacetData()
    const nextErrors = buildInitialFacetErrors()
    const nextLoadingState = buildInitialFacetLoading()

    keys.forEach((key, index) => {
      const result = settled[index]
      nextLoadingState[key] = false
      if (result.status === 'fulfilled') {
        nextData[key] = normalizeFacetPayload(key, result.value)
      } else {
        nextErrors[key] = normalizeErrorMessage(result.reason, `加载${DETAIL_SECTION_LABELS[key]}失败`)
      }
    })

    setCommunityFacetData(nextData)
    setCommunityFacetErrors(nextErrors)
    setCommunityFacetLoading(nextLoadingState)
  }, [])

  const updateHashForCommunity = useCallback((communityId) => {
    const nextHash = buildCommunityHash(communityId)
    if (window.location.hash !== nextHash) {
      window.location.hash = nextHash
    }
  }, [])

  const loadCommunityDetailWithFacets = useCallback(async (community, { syncHash = true } = {}) => {
    await Promise.all([
      loadCommunityDetail(community),
      loadCommunityFacets(community?.id),
    ])
    if (syncHash && community?.id) {
      updateHashForCommunity(community.id)
    }
  }, [loadCommunityDetail, loadCommunityFacets, updateHashForCommunity])

  const resetSelectedCommunityView = useCallback(({ clearHash = false, clearFeedback = true } = {}) => {
    setSelectedCommunity(null)
    setCommunityDetails(null)
    setCommunityFacetData(buildInitialFacetData())
    setCommunityFacetLoading(buildInitialFacetLoading())
    setCommunityFacetErrors(buildInitialFacetErrors())
    setDetailError(null)
    autoOpenRef.current = null
    if (clearFeedback) {
      setActionFeedback(null)
    }
    if (clearHash && window.location.hash) {
      window.history.replaceState(null, '', window.location.pathname + window.location.search)
      setHashCommunityId(null)
    }
  }, [])

  const handleRefresh = useCallback(async () => {
    await loadCommunities(currentLevel)
    if (showHierarchy) {
      await loadHierarchy()
    }
    setActionFeedback({ type: 'success', message: '社区数据已刷新' })
  }, [currentLevel, loadCommunities, loadHierarchy, showHierarchy])

  const handleDetectCommunities = useCallback(async () => {
    setDetecting(true)
    setActionFeedback(null)
    try {
      await communityApi.detectCommunities({
        algorithm: selectedAlgorithm,
        resolution: 1.0
      })
      setActionFeedback({ type: 'success', message: '社区检测已触发，正在刷新数据...' })
      await new Promise((resolve) => window.setTimeout(resolve, 2000))
      await loadCommunities(currentLevel)
      if (showHierarchy) {
        await loadHierarchy()
      }
    } catch (error) {
      setActionFeedback({
        type: 'error',
        message: normalizeErrorMessage(error, '触发社区检测失败')
      })
    } finally {
      setDetecting(false)
    }
  }, [currentLevel, loadCommunities, loadHierarchy, selectedAlgorithm, showHierarchy])

  const handleToggleHierarchy = useCallback(async () => {
    const nextVisible = !showHierarchy
    setShowHierarchy(nextVisible)
    if (nextVisible && !hierarchy) {
      await loadHierarchy()
    }
  }, [hierarchy, loadHierarchy, showHierarchy])

  const handleRegenerateSummary = useCallback(async () => {
    if (!selectedCommunity?.id) return
    setRegeneratingSummary(true)
    setActionFeedback(null)
    setDetailError(null)
    try {
      const response = await communityApi.summarizeCommunity(selectedCommunity.id, { regenerate: true })
      const summary = response?.summary
      if (summary) {
        setCommunityDetails((current) => ({
          ...(current || selectedCommunity),
          summary
        }))
        setCommunities((current) =>
          current.map((item) => {
            if (String(item.id) !== String(selectedCommunity.id)) return item
            return { ...item, summary }
          })
        )
      }
      setActionFeedback({ type: 'success', message: '摘要已重新生成' })
    } catch (error) {
      setDetailError(normalizeErrorMessage(error, '生成摘要失败'))
      setActionFeedback({ type: 'error', message: normalizeErrorMessage(error, '生成摘要失败') })
    } finally {
      setRegeneratingSummary(false)
    }
  }, [selectedCommunity])

  useEffect(() => {
    loadCommunities(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    function handleHashChange() {
      setHashCommunityId(normalizeCommunityIdFromHash(window.location.hash))
    }

    window.addEventListener('hashchange', handleHashChange)
    return () => {
      window.removeEventListener('hashchange', handleHashChange)
    }
  }, [])

  useEffect(() => {
    if (!hashCommunityId) return
    if (autoOpenRef.current === hashCommunityId) return
    if (selectedCommunity && String(selectedCommunity.id) === hashCommunityId) return

    const directMatch = communities.find((item) => String(item.id) === hashCommunityId)
    if (directMatch) {
      autoOpenRef.current = hashCommunityId
      loadCommunityDetailWithFacets(directMatch, { syncHash: false })
      return
    }

    autoOpenRef.current = hashCommunityId
    communityApi
      .getCommunity(hashCommunityId)
      .then((community) => loadCommunityDetailWithFacets(community, { syncHash: false }))
      .catch((error) => {
        resetSelectedCommunityView({ clearHash: false, clearFeedback: false })
        setActionFeedback({
          type: 'error',
          message: normalizeErrorMessage(error, `未找到社区 ${hashCommunityId}`),
        })
      })
  }, [communities, hashCommunityId, loadCommunityDetailWithFacets, resetSelectedCommunityView, selectedCommunity])

  return (
    <section
      className="communities-page"
      aria-label="Communities page"
      data-testid={COMMUNITIES_SMOKE_TEST_IDS.page}
    >
      <header className="communities-header">
        <h1>知识社区</h1>
        <p className="communities-subtitle">发现和管理知识图谱中的主题社区</p>
      </header>

      <div className="communities-toolbar" data-testid={COMMUNITIES_SMOKE_TEST_IDS.toolbar}>
        <div className="communities-toolbar-left">
          <button
            type="button"
            className="community-btn community-btn--primary community-detect-btn"
            onClick={handleDetectCommunities}
            disabled={detecting}
            data-testid={COMMUNITIES_SMOKE_TEST_IDS.detectButton}
          >
            {detecting ? '检测中...' : '触发社区检测'}
          </button>

          <label className="community-select-label" htmlFor="community-algorithm">
            算法
          </label>
          <select
            id="community-algorithm"
            className="community-select"
            value={selectedAlgorithm}
            onChange={(event) => setSelectedAlgorithm(event.target.value)}
            disabled={detecting}
          >
            <option value="leiden">Leiden</option>
            <option value="louvain">Louvain</option>
            <option value="label_propagation">Label Propagation</option>
          </select>

          <button
            type="button"
            className="community-btn"
            onClick={handleRefresh}
            disabled={loading || detecting}
            data-testid={COMMUNITIES_SMOKE_TEST_IDS.refreshButton}
          >
            刷新
          </button>

          <button
            type="button"
            className={`community-btn community-hierarchy-toggle ${showHierarchy ? 'is-active' : ''}`}
            onClick={handleToggleHierarchy}
            data-testid={COMMUNITIES_SMOKE_TEST_IDS.hierarchyToggle}
          >
            层次结构
          </button>
        </div>

        <div className="communities-level-filter" role="group" aria-label="按层级筛选">
          <button
            type="button"
            className={`community-level-btn ${currentLevel === null ? 'is-active' : ''}`}
            onClick={() => {
              setCurrentLevel(null)
              loadCommunities(null)
            }}
          >
            全部
          </button>
          {levels.map((level) => (
            <button
              type="button"
              key={level}
              className={`community-level-btn ${Number(currentLevel) === Number(level) ? 'is-active' : ''}`}
              onClick={() => {
                setCurrentLevel(level)
                loadCommunities(level)
              }}
            >
              {buildLevelText(level)}
            </button>
          ))}
        </div>
      </div>

      {actionFeedback ? (
        <div
          className={`community-action-feedback ${actionFeedback.type === 'error' ? 'community-action-error' : 'community-action-success'}`}
          role={actionFeedback.type === 'error' ? 'alert' : 'status'}
          data-testid={COMMUNITIES_SMOKE_TEST_IDS.actionFeedback}
        >
          {actionFeedback.message}
        </div>
      ) : null}

      {showHierarchy ? (
        <section
          className="community-hierarchy-panel"
          aria-label="社区层次结构"
          data-testid={COMMUNITIES_SMOKE_TEST_IDS.hierarchyPanel}
        >
          <div className="community-hierarchy-header">
            <h2>社区层次结构</h2>
            {hierarchy ? (
              <span>
                共 {hierarchy.total_communities ?? 0} 个社区，最大层级 {hierarchy.max_level ?? 0}
              </span>
            ) : null}
          </div>

          {hierarchyError ? <div className="community-hierarchy-error">{hierarchyError}</div> : null}

          {!hierarchyError && hierarchy?.roots?.length ? (
            <div className="community-hierarchy-tree">
              {buildNodeList(hierarchy.roots, 0, loadCommunityDetailWithFacets, selectedCommunity ? String(selectedCommunity.id) : null)}
            </div>
          ) : null}

          {!hierarchyError && !hierarchy?.roots?.length ? <div className="community-hierarchy-empty">暂无层次结构数据</div> : null}
        </section>
      ) : null}

      <div className={`communities-workspace ${selectedCommunity ? 'has-detail' : ''}`}>
        <section
          className="communities-list-panel"
          aria-live="polite"
          data-testid={COMMUNITIES_SMOKE_TEST_IDS.listPanel}
        >
          {loading ? (
            <div
              className="community-state-panel"
              role="status"
              data-testid={COMMUNITIES_SMOKE_TEST_IDS.listStatePanel}
            >
              <div className="community-spinner" />
              <p>加载社区数据...</p>
            </div>
          ) : null}

          {!loading && listError ? (
            <div
              className="community-state-panel community-state-panel--error"
              role="alert"
              data-testid={COMMUNITIES_SMOKE_TEST_IDS.listStatePanel}
            >
              <p>{listError}</p>
              <button type="button" className="community-btn" onClick={() => loadCommunities(currentLevel)}>
                重试
              </button>
            </div>
          ) : null}

          {!loading && !listError && !hasCommunities ? (
            <div
              className="community-state-panel community-state-panel--empty"
              data-testid={COMMUNITIES_SMOKE_TEST_IDS.listStatePanel}
            >
              <h2>暂无社区</h2>
              <p>点击“触发社区检测”开始发现知识社区</p>
              <button type="button" className="community-btn community-btn--primary" onClick={handleDetectCommunities} disabled={detecting}>
                {detecting ? '检测中...' : '触发社区检测'}
              </button>
            </div>
          ) : null}

          {!loading && !listError && hasCommunities && filteredCommunities.length > 0 ? (
            <div className="communities-grid">
              {filteredCommunities.map((community) => {
                const isSelected = String(selectedCommunity?.id) === String(community.id)
                return (
                  <button
                    type="button"
                    className={`community-card ${isSelected ? 'is-selected' : ''}`}
                    key={community.id}
                    onClick={() => loadCommunityDetailWithFacets(community)}
                    data-testid={COMMUNITIES_SMOKE_TEST_IDS.card}
                  >
                    <div className="community-card-header">
                      <h3>{community.title || '未命名社区'}</h3>
                      <span className="community-level-badge">{buildLevelText(community.level)}</span>
                    </div>
                    <p className="community-card-summary">{community.summary || '暂无摘要'}</p>
                    <div className="community-card-meta">{community.entity_count ?? 0} 个实体</div>
                  </button>
                )
              })}
            </div>
          ) : null}

          {!loading && !listError && hasCommunities && filteredCommunities.length === 0 ? (
            <div
              className="community-state-panel community-state-panel--empty"
              data-testid={COMMUNITIES_SMOKE_TEST_IDS.listStatePanel}
            >
              <h2>当前层级暂无社区</h2>
              <p>请切换层级筛选或触发新的社区检测</p>
            </div>
          ) : null}
        </section>

        {selectedCommunity ? (
          <aside
            className="community-detail-panel"
            aria-label="社区详情"
            data-testid={COMMUNITIES_SMOKE_TEST_IDS.detailPanel}
          >
            <div className="community-detail-header">
              <h2>社区详情</h2>
              <button
                type="button"
                className="community-btn"
                onClick={() => resetSelectedCommunityView({ clearHash: true, clearFeedback: true })}
              >
                关闭
              </button>
            </div>

            <div className="community-detail-body">
              {loadingDetail ? (
                <div className="community-state-panel" role="status">
                  <div className="community-spinner" />
                  <p>加载社区详情...</p>
                </div>
              ) : null}

              {!loadingDetail ? (
                <>
                  <div className="community-detail-row">
                    <span className="community-detail-label">名称</span>
                    <strong>{selectedCommunity.title || '未命名社区'}</strong>
                  </div>
                  <div className="community-detail-row">
                    <span className="community-detail-label">层级</span>
                    <span className="community-level-badge">{buildLevelText(selectedCommunity.level)}</span>
                  </div>
                  <div className="community-detail-row">
                    <span className="community-detail-label">实体数量</span>
                    <span>{selectedCommunity.entity_count ?? 0} 个实体</span>
                  </div>
                  <div className="community-detail-row">
                    <span className="community-detail-label">摘要</span>
                    <p>{communityDetails?.summary || selectedCommunity.summary || '暂无摘要'}</p>
                  </div>

                  {detailError ? <div className="community-action-error">{detailError}</div> : null}

                  <section
                    className="community-detail-section"
                    aria-label="社区脉络"
                    data-testid={COMMUNITIES_SMOKE_TEST_IDS.lineageSection}
                  >
                    <h3>社区脉络</h3>
                    {communityFacetLoading.ancestors || communityFacetLoading.descendants ? (
                      <div className="community-detail-empty">加载脉络中...</div>
                    ) : null}
                    {!communityFacetLoading.ancestors && !communityFacetLoading.descendants ? (
                      <>
                        {communityFacetErrors.ancestors ? (
                          <div
                            className="community-action-error"
                            data-testid={COMMUNITIES_SMOKE_TEST_IDS.lineageAncestorsError}
                          >
                            {communityFacetErrors.ancestors}
                          </div>
                        ) : null}
                        {communityFacetErrors.descendants ? (
                          <div
                            className="community-action-error"
                            data-testid={COMMUNITIES_SMOKE_TEST_IDS.lineageDescendantsError}
                          >
                            {communityFacetErrors.descendants}
                          </div>
                        ) : null}
                        {!communityFacetErrors.ancestors && !communityFacetErrors.descendants ? (
                          <div className="community-detail-lineage">
                            <div>
                              <strong>上游</strong>
                              {communityFacetData.ancestors.length > 0 ? (
                                <ul className="community-detail-list">
                                  {communityFacetData.ancestors.map((item) => (
                                    <li key={`ancestor-${item.id}`}>
                                      <span>{item.title || item.id}</span>
                                      <span>{buildLevelText(item.level)}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <div className="community-detail-empty">暂无上游社区</div>
                              )}
                            </div>
                            <div>
                              <strong>下游</strong>
                              {communityFacetData.descendants.length > 0 ? (
                                <ul className="community-detail-list">
                                  {communityFacetData.descendants.map((item) => (
                                    <li key={`descendant-${item.id}`}>
                                      <span>{item.title || item.id}</span>
                                      <span>{buildLevelText(item.level)}</span>
                                    </li>
                                  ))}
                                </ul>
                              ) : (
                                <div className="community-detail-empty">暂无下游社区</div>
                              )}
                            </div>
                          </div>
                        ) : null}
                      </>
                    ) : null}
                  </section>

                  <section
                    className="community-detail-section"
                    aria-label="社区实体"
                    data-testid={COMMUNITIES_SMOKE_TEST_IDS.entitiesSection}
                  >
                    <h3>实体</h3>
                    {communityFacetLoading.entities ? (
                      <div className="community-detail-empty">加载实体中...</div>
                    ) : communityFacetErrors.entities ? (
                      <div
                        className="community-action-error"
                        data-testid={COMMUNITIES_SMOKE_TEST_IDS.entitiesError}
                      >
                        {communityFacetErrors.entities}
                      </div>
                    ) : communityFacetData.entities.length > 0 ? (
                      <div className="community-detail-chip-list">
                        {communityFacetData.entities.map((entity) => (
                          <span key={`entity-${entity.id || entity.name}`}>{entity.name || entity.id}</span>
                        ))}
                      </div>
                    ) : (
                      <div className="community-detail-empty">暂无实体</div>
                    )}
                  </section>

                  <section
                    className="community-detail-section"
                    aria-label="社区关系"
                    data-testid={COMMUNITIES_SMOKE_TEST_IDS.relationshipsSection}
                  >
                    <h3>关系</h3>
                    {communityFacetLoading.relationships ? (
                      <div className="community-detail-empty">加载关系中...</div>
                    ) : communityFacetErrors.relationships ? (
                      <div
                        className="community-action-error"
                        data-testid={COMMUNITIES_SMOKE_TEST_IDS.relationshipsError}
                      >
                        {communityFacetErrors.relationships}
                      </div>
                    ) : communityFacetData.relationships.length > 0 ? (
                      <ul className="community-detail-list">
                        {communityFacetData.relationships.map((relationship) => (
                          <li key={`relationship-${relationship.id}`}>
                            <span>{relationship.source || relationship.source_id}</span>
                            <span>{relationship.type || '-'}</span>
                            <span>{relationship.target || relationship.target_id}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <div className="community-detail-empty">暂无关系</div>
                    )}
                  </section>

                  {!hasAnyFacetContent(communityFacetData)
                  && !communityFacetLoading.entities
                  && !communityFacetLoading.relationships
                  && !communityFacetLoading.ancestors
                  && !communityFacetLoading.descendants ? (
                    <div className="community-detail-empty">当前社区暂无可展示的细节数据</div>
                  ) : null}

                  <div className="community-detail-actions">
                    <button
                    type="button"
                    className="community-btn community-btn--primary community-summarize-btn"
                    onClick={handleRegenerateSummary}
                    disabled={regeneratingSummary}
                    data-testid={COMMUNITIES_SMOKE_TEST_IDS.summarizeButton}
                  >
                      {regeneratingSummary ? '生成中...' : '重新生成摘要'}
                    </button>
                  </div>
                </>
              ) : null}
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  )
}
