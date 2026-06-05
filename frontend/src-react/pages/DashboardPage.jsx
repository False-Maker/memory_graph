import { Link } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'
import { dashboardApi } from '../api/client'
import { buildDiagnosticsHref } from './DiagnosticsPage.helpers'
import { DASHBOARD_SMOKE_TEST_IDS } from './DashboardPage.smoke-helpers'
import './DashboardPage.css'

const STAT_CARDS = [
  {
    key: 'entities',
    label: '实体数量',
    to: '/graph',
    cta: '查看图谱',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
      </svg>
    )
  },
  {
    key: 'relationships',
    label: '关系数量',
    to: '/graph',
    cta: '查看图谱',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
      </svg>
    )
  },
  {
    key: 'memories',
    label: '记忆条目',
    to: '/memories',
    cta: '查看记忆',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 2a10 10 0 1 0 10 10 4 4 0 0 1-5-5 4 4 0 0 1-5-5" />
        <path d="M8.5 8.5v.01" />
        <path d="M16 15.5v.01" />
        <path d="M12 12v.01" />
        <path d="M11 17v.01" />
        <path d="M7 14v.01" />
      </svg>
    )
  },
  {
    key: 'communities',
    label: '知识社区',
    to: '/communities',
    cta: '查看社区',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>
    )
  }
]

const DEFAULT_STATS = {
  entities: 0,
  relationships: 0,
  memories: 0,
  communities: 0
}

const DEFAULT_OPERATOR_SUMMARY = {
  runtime: {},
  query_runs: {},
  sync_sources: {},
  mcp: {},
  collectors: {},
}

function formatRelativeDate(dateString) {
  if (!dateString) return ''
  const date = new Date(dateString)
  if (Number.isNaN(date.getTime())) {
    return ''
  }

  const now = new Date()
  const diffMs = now - date
  const days = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`

  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function normalizeMemoriesResponse(response) {
  const memories = Array.isArray(response)
    ? response
    : Array.isArray(response?.memories)
      ? response.memories
      : []

  return memories.map((memory) => ({
    id: memory.id,
    title: memory.title || memory.metadata?.title || '未命名记忆',
    preview: memory.preview || memory.content || '暂无内容',
    created_at: memory.created_at,
  }))
}

function normalizeStatsResponse(statsResponse, communitiesResponse) {
  const communityCount = Array.isArray(communitiesResponse?.roots)
    ? Number(communitiesResponse.total_communities ?? communitiesResponse.roots.length)
    : Number(communitiesResponse?.total ?? communitiesResponse?.communities?.length ?? 0)

  return {
    entities: Number(statsResponse?.total_entities ?? statsResponse?.entities ?? 0),
    relationships: Number(statsResponse?.total_relationships ?? statsResponse?.relationships ?? 0),
    memories: Number(statsResponse?.total_memories ?? statsResponse?.memories ?? 0),
    communities: Number.isFinite(communityCount) ? communityCount : 0,
  }
}

export default function DashboardPage() {
  const [stats, setStats] = useState(DEFAULT_STATS)
  const [statsLoading, setStatsLoading] = useState(true)
  const [statsError, setStatsError] = useState(null)

  const [memories, setMemories] = useState([])
  const [memoriesLoading, setMemoriesLoading] = useState(true)
  const [memoriesError, setMemoriesError] = useState(null)
  const [operatorSummary, setOperatorSummary] = useState(DEFAULT_OPERATOR_SUMMARY)
  const [operatorSummaryError, setOperatorSummaryError] = useState(null)

  useEffect(() => {
    async function loadStats() {
      setStatsLoading(true)
      setStatsError(null)
      try {
        const [statsResponse, communitiesResponse] = await Promise.all([
          dashboardApi.getStats(),
          dashboardApi.getCommunities(500),
        ])
        setStats(normalizeStatsResponse(statsResponse, communitiesResponse))
      } catch (error) {
        setStats(DEFAULT_STATS)
        setStatsError(error?.message || '统计数据加载失败')
      } finally {
        setStatsLoading(false)
      }
    }

    async function loadRecentMemories() {
      setMemoriesLoading(true)
      setMemoriesError(null)
      try {
        const data = await dashboardApi.getRecentMemories(10)
        setMemories(normalizeMemoriesResponse(data))
      } catch (error) {
        setMemories([])
        setMemoriesError(error?.message || '加载失败')
      } finally {
        setMemoriesLoading(false)
      }
    }

    async function loadOperatorSummary() {
      setOperatorSummaryError(null)
      try {
        const payload = await dashboardApi.getOperatorSummary()
        setOperatorSummary(payload && typeof payload === 'object' ? payload : DEFAULT_OPERATOR_SUMMARY)
      } catch (error) {
        setOperatorSummary(DEFAULT_OPERATOR_SUMMARY)
        setOperatorSummaryError(error?.message || '运营摘要加载失败')
      }
    }

    loadStats()
    loadRecentMemories()
    loadOperatorSummary()
  }, [])

  const renderedStats = useMemo(() => {
    return STAT_CARDS.map((card) => ({
      ...card,
      value: statsLoading ? '-' : stats[card.key]
    }))
  }, [stats, statsLoading])

  const operatorCards = useMemo(() => ([
    {
      key: 'queryRuns',
      label: '最近 Query Runs',
      value: operatorSummary.query_runs?.total_recent ?? '-',
      to: buildDiagnosticsHref({ tab: 'query-runs' }),
      testId: DASHBOARD_SMOKE_TEST_IDS.operatorCardQueryRuns,
    },
    {
      key: 'runtime',
      label: 'Runtime 状态',
      value: operatorSummary.runtime?.status ?? '-',
      to: buildDiagnosticsHref({ tab: 'runtime' }),
      testId: DASHBOARD_SMOKE_TEST_IDS.operatorCardRuntime,
    },
    {
      key: 'failures',
      label: 'Recent Failures',
      value: operatorSummary.runtime?.recent_failures_count ?? '-',
      to: buildDiagnosticsHref({ tab: 'failures' }),
      testId: DASHBOARD_SMOKE_TEST_IDS.operatorCardFailures,
    },
    {
      key: 'mcp',
      label: 'MCP Tools',
      value: operatorSummary.mcp?.tools_count ?? '-',
      to: buildDiagnosticsHref({ tab: 'mcp' }),
      testId: DASHBOARD_SMOKE_TEST_IDS.operatorCardMcp,
    },
  ]), [operatorSummary])

  return (
    <section
      className="dashboard-page"
      aria-label="Dashboard page"
      data-testid={DASHBOARD_SMOKE_TEST_IDS.page}
    >
      <header className="dashboard-header">
        <div>
          <h1>我的记忆库</h1>
          <p className="dashboard-subtitle">让AI记住您的重要信息</p>
        </div>
      </header>

      {statsError ? (
        <div
          className="dashboard-inline-error"
          data-testid={DASHBOARD_SMOKE_TEST_IDS.statsError}
        >
          统计加载失败，请检查后端与社区接口状态。
        </div>
      ) : null}

      <div
        className="dashboard-stats-grid"
        aria-busy={statsLoading}
        data-testid={DASHBOARD_SMOKE_TEST_IDS.statsGrid}
      >
        {renderedStats.map((card) => (
          <Link
            key={card.key}
            to={card.to}
            className="dashboard-stat-card dashboard-stat-card--link"
            data-testid={DASHBOARD_SMOKE_TEST_IDS[`stat${card.key.charAt(0).toUpperCase()}${card.key.slice(1)}`]}
          >
            <div className={`dashboard-stat-icon dashboard-stat-icon--${card.key}`}>{card.icon}</div>
            <div className="dashboard-stat-text">
              <div className={`dashboard-stat-value ${statsLoading ? 'is-loading' : ''}`}>{card.value}</div>
              <div className="dashboard-stat-label">{card.label}</div>
              <div className="dashboard-stat-cta">{card.cta}</div>
            </div>
          </Link>
        ))}
      </div>

      <article
        className="dashboard-recent-section"
        aria-label="Operator summary"
        data-testid={DASHBOARD_SMOKE_TEST_IDS.operatorSection}
      >
        <div className="dashboard-section-header">
          <h2>运营摘要</h2>
          <Link to="/diagnostics" className="dashboard-link-button">
            打开 Diagnostics →
          </Link>
        </div>
        {operatorSummaryError ? (
          <div className="dashboard-state-panel dashboard-state-panel--error">{operatorSummaryError}</div>
        ) : null}
        <div className="dashboard-stats-grid">
          {operatorCards.map((card) => (
            <Link
              key={card.key}
              to={card.to}
              className="dashboard-stat-card dashboard-stat-card--link"
              data-testid={card.testId}
            >
              <div className="dashboard-stat-text">
                <div className="dashboard-stat-value">{card.value}</div>
                <div className="dashboard-stat-label">{card.label}</div>
                <div className="dashboard-stat-cta">查看详情</div>
              </div>
            </Link>
          ))}
        </div>
      </article>

      <article
        className="dashboard-recent-section"
        aria-label="Recent memories"
        data-testid={DASHBOARD_SMOKE_TEST_IDS.recentSection}
      >
        <div className="dashboard-section-header">
          <h2>最近记忆</h2>
          <Link to="/memories" className="dashboard-link-button" data-testid={DASHBOARD_SMOKE_TEST_IDS.viewAllLink}>
            查看全部 →
          </Link>
        </div>

        {memoriesLoading ? (
          <div
            className="dashboard-state-panel"
            role="status"
            data-testid={DASHBOARD_SMOKE_TEST_IDS.recentState}
          >
            <div className="dashboard-spinner" />
            加载中...
          </div>
        ) : null}

        {!memoriesLoading && memoriesError ? (
          <div
            className="dashboard-state-panel dashboard-state-panel--error"
            role="alert"
            data-testid={DASHBOARD_SMOKE_TEST_IDS.recentState}
          >
            {memoriesError}
          </div>
        ) : null}

        {!memoriesLoading && !memoriesError && memories.length === 0 ? (
          <div
            className="dashboard-state-panel"
            data-testid={DASHBOARD_SMOKE_TEST_IDS.recentState}
          >
            暂无记忆，开始添加您的第一条记忆吧！
          </div>
        ) : null}

        {!memoriesLoading && !memoriesError && memories.length > 0 ? (
          <div className="dashboard-recent-list">
            {memories.map((memory, index) => (
              <article
                className="dashboard-recent-item"
                key={memory.id ?? `${memory.created_at ?? 'memory'}-${index}`}
                data-testid={DASHBOARD_SMOKE_TEST_IDS.recentItem}
              >
                {memory.id ? (
                  <Link
                    to={`/memories/${encodeURIComponent(memory.id)}`}
                    className="dashboard-recent-link"
                    data-testid={DASHBOARD_SMOKE_TEST_IDS.recentItemLink}
                  >
                    <div className="dashboard-recent-main">
                      <div className="dashboard-recent-title">{memory.title || '未命名记忆'}</div>
                      <div className="dashboard-recent-preview">{memory.preview || memory.content || '暂无内容'}</div>
                    </div>
                    <time className="dashboard-recent-time">{formatRelativeDate(memory.created_at)}</time>
                  </Link>
                ) : (
                  <>
                    <div className="dashboard-recent-main">
                      <div className="dashboard-recent-title">{memory.title || '未命名记忆'}</div>
                      <div className="dashboard-recent-preview">{memory.preview || memory.content || '暂无内容'}</div>
                    </div>
                    <time className="dashboard-recent-time">{formatRelativeDate(memory.created_at)}</time>
                  </>
                )}
              </article>
            ))}
          </div>
        ) : null}
      </article>
    </section>
  )
}
