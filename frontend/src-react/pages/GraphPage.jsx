import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as d3 from 'd3'
import graphApi from '../api/graph'
import { GRAPH_SMOKE_TEST_IDS } from './GraphPage.smoke-helpers'
import './GraphPage.css'

const LAYOUT_OPTIONS = [
  { value: 'force', label: '力导向布局' },
  { value: 'circular', label: '圆形布局' },
  { value: 'hierarchical', label: '层级布局' },
  { value: 'clustered', label: '聚类布局' }
]

function normalizeEntitiesPayload(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.entities)) return payload.entities
  if (Array.isArray(payload?.data?.entities)) return payload.data.entities
  return []
}

function normalizeRelationshipsPayload(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.relationships)) return payload.relationships
  if (Array.isArray(payload?.data?.relationships)) return payload.data.relationships
  return []
}

function createNodeColor(type) {
  if (type === 'community') return 'var(--graph-node-community)'
  if (type === 'entity') return 'var(--graph-node-entity)'
  return 'var(--graph-node-default)'
}

function buildHierarchicalLevels(nodes, links) {
  const adjacency = new Map(nodes.map((node) => [node.id, []]))
  const inDegree = new Map(nodes.map((node) => [node.id, 0]))

  links.forEach((link) => {
    if (!adjacency.has(link.source) || !adjacency.has(link.target)) {
      return
    }
    adjacency.get(link.source).push(link.target)
    inDegree.set(link.target, (inDegree.get(link.target) || 0) + 1)
  })

  const roots = nodes.filter((node) => !node.parentId && (inDegree.get(node.id) || 0) === 0)
  const queue = roots.map((node) => ({ id: node.id, level: 0 }))
  const levels = new Map()
  const visited = new Set()

  while (queue.length > 0) {
    const current = queue.shift()
    if (!current || visited.has(current.id)) continue
    visited.add(current.id)
    levels.set(current.id, current.level)

    ;(adjacency.get(current.id) || []).forEach((nextId) => {
      if (!visited.has(nextId)) {
        queue.push({ id: nextId, level: current.level + 1 })
      }
    })
  }

  nodes.forEach((node) => {
    if (!levels.has(node.id)) {
      levels.set(node.id, 0)
    }
  })

  return levels
}

function applyStaticLayout(layoutType, nodes, links, width, height) {
  if (layoutType === 'circular') {
    const radius = Math.max(60, Math.min(width, height) / 3)
    nodes.forEach((node, index) => {
      const angle = (2 * Math.PI * index) / Math.max(1, nodes.length)
      node.x = width / 2 + radius * Math.cos(angle)
      node.y = height / 2 + radius * Math.sin(angle)
    })
    return
  }

  if (layoutType === 'hierarchical') {
    const levels = buildHierarchicalLevels(nodes, links)
    const maxLevel = Math.max(0, ...levels.values())
    const levelGroups = new Map()

    nodes.forEach((node) => {
      const level = levels.get(node.id) || 0
      if (!levelGroups.has(level)) {
        levelGroups.set(level, [])
      }
      levelGroups.get(level).push(node)
    })

    Array.from(levelGroups.entries()).forEach(([level, group]) => {
      const y = maxLevel === 0 ? height / 2 : 60 + (level * (height - 120)) / maxLevel
      group.forEach((node, index) => {
        const x = ((index + 1) * width) / (group.length + 1)
        node.x = x
        node.y = y
      })
    })
    return
  }

  if (layoutType === 'clustered') {
    const groups = new Map()
    nodes.forEach((node) => {
      const key = node.community || node.type || 'default'
      if (!groups.has(key)) {
        groups.set(key, [])
      }
      groups.get(key).push(node)
    })

    const entries = Array.from(groups.entries())
    const centerRadius = Math.max(80, Math.min(width, height) / 4)

    entries.forEach(([, group], groupIndex) => {
      const clusterAngle = (2 * Math.PI * groupIndex) / Math.max(1, entries.length)
      const clusterX = width / 2 + centerRadius * Math.cos(clusterAngle)
      const clusterY = height / 2 + centerRadius * Math.sin(clusterAngle)
      const innerRadius = Math.max(24, group.length * 10)

      group.forEach((node, nodeIndex) => {
        const innerAngle = (2 * Math.PI * nodeIndex) / Math.max(1, group.length)
        node.x = clusterX + innerRadius * Math.cos(innerAngle)
        node.y = clusterY + innerRadius * Math.sin(innerAngle)
      })
    })
  }
}

export default function GraphPage() {
  const containerRef = useRef(null)
  const svgRef = useRef(null)
  const graphGroupRef = useRef(null)
  const zoomRef = useRef(null)
  const simulationRef = useRef(null)
  const resizeObserverRef = useRef(null)

  const [layoutType, setLayoutType] = useState('force')
  const [nodes, setNodes] = useState([])
  const [links, setLinks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedNodeId, setSelectedNodeId] = useState(null)
  const [canvasVersion, setCanvasVersion] = useState(0)

  const selectedNode = useMemo(() => {
    return nodes.find((node) => node.id === selectedNodeId) || null
  }, [nodes, selectedNodeId])

  const loadGraphData = useCallback(async () => {
    setLoading(true)
    setError(null)

    try {
      const [entitiesResponse, relationshipsResponse] = await Promise.all([
        graphApi.getEntities({ limit: 200 }),
        graphApi.getRelationships({ limit: 400 })
      ])

      const entities = normalizeEntitiesPayload(entitiesResponse)
      const relationships = normalizeRelationshipsPayload(relationshipsResponse)

      const normalizedNodes = entities
        .filter((entity) => entity?.id !== undefined && entity?.id !== null)
        .map((entity) => ({
          id: String(entity.id),
          name: entity.name || '未命名节点',
          type: entity.type || 'entity',
          size: entity.size || 20,
          description: entity.properties?.description || entity.description || '',
          community: entity.community || entity.community_id || null,
          parentId: entity.parentId || entity.parent_id || null
        }))

      const nodeIdSet = new Set(normalizedNodes.map((node) => node.id))
      const normalizedLinks = relationships
        .map((relationship) => ({
          source: String(relationship.source_id ?? relationship.source ?? ''),
          target: String(relationship.target_id ?? relationship.target ?? ''),
          type: relationship.type || ''
        }))
        .filter((relationship) => {
          return nodeIdSet.has(relationship.source) && nodeIdSet.has(relationship.target)
        })

      setNodes(normalizedNodes)
      setLinks(normalizedLinks)
      setSelectedNodeId((current) => {
        if (!current) return current
        return normalizedNodes.some((node) => node.id === current) ? current : null
      })
    } catch (requestError) {
      setNodes([])
      setLinks([])
      setSelectedNodeId(null)
      setError(requestError?.response?.data?.detail || requestError?.message || '图谱数据加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadGraphData()
  }, [loadGraphData])

  useEffect(() => {
    const svgElement = svgRef.current
    const containerElement = containerRef.current
    if (!svgElement || !containerElement) return

    const svg = d3.select(svgElement)
    svg.selectAll('*').remove()

    const graphGroup = svg.append('g').attr('class', 'graph-canvas')
    graphGroupRef.current = graphGroup

    zoomRef.current = d3
      .zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        graphGroup.attr('transform', event.transform)
      })

    svg.call(zoomRef.current)

    const resize = () => {
      const width = containerElement.clientWidth || 900
      const height = containerElement.clientHeight || 520
      svg.attr('viewBox', `0 0 ${width} ${height}`)
      setCanvasVersion((version) => version + 1)
    }

    resize()

    const resizeObserver = new ResizeObserver(() => resize())
    resizeObserver.observe(containerElement)
    resizeObserverRef.current = resizeObserver

    return () => {
      resizeObserver.disconnect()
      resizeObserverRef.current = null
      simulationRef.current?.stop()
      simulationRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!graphGroupRef.current || !containerRef.current) return

    simulationRef.current?.stop()
    simulationRef.current = null

    const width = containerRef.current.clientWidth || 900
    const height = containerRef.current.clientHeight || 520
    const graphGroup = graphGroupRef.current

    graphGroup.selectAll('*').remove()

    if (nodes.length === 0) {
      return
    }

    const renderNodes = nodes.map((node) => ({ ...node }))
    const nodeById = new Map(renderNodes.map((node) => [node.id, node]))
    const renderLinks = links
      .map((link) => ({
        ...link,
        source: nodeById.get(link.source),
        target: nodeById.get(link.target)
      }))
      .filter((link) => link.source && link.target)

    const linkSelection = graphGroup
      .selectAll('line.graph-link')
      .data(renderLinks)
      .enter()
      .append('line')
      .attr('class', 'graph-link')
      .attr('stroke', 'var(--graph-link-color)')
      .attr('stroke-width', 1.5)
      .attr('opacity', 0.6)

    const nodeSelection = graphGroup
      .selectAll('g.graph-node')
      .data(renderNodes)
      .enter()
      .append('g')
      .attr('class', 'graph-node')
      .attr('data-testid', GRAPH_SMOKE_TEST_IDS.node)
      .attr('cursor', 'pointer')
      .on('click', (event, node) => {
        event.stopPropagation()
        setSelectedNodeId(node.id)
      })

    nodeSelection
      .append('circle')
      .attr('r', (node) => node.size || 20)
      .attr('fill', (node) => node.color || createNodeColor(node.type))
      .attr('stroke', (node) => (node.id === selectedNodeId ? 'var(--graph-node-selected-stroke)' : 'var(--graph-node-stroke)'))
      .attr('stroke-width', (node) => (node.id === selectedNodeId ? 3 : 2))

    nodeSelection
      .append('text')
      .attr('dy', (node) => (node.size || 20) + 14)
      .attr('text-anchor', 'middle')
      .attr('font-size', '11px')
      .attr('fill', 'var(--graph-label-color)')
      .text((node) => (node.name || '节点').slice(0, 12))

    const drag = d3
      .drag()
      .on('start', (event, node) => {
        if (!simulationRef.current || event.active) return
        simulationRef.current.alphaTarget(0.3).restart()
        node.fx = node.x
        node.fy = node.y
      })
      .on('drag', (event, node) => {
        node.fx = event.x
        node.fy = event.y
      })
      .on('end', (event, node) => {
        if (!simulationRef.current || event.active) return
        simulationRef.current.alphaTarget(0)
        node.fx = null
        node.fy = null
      })

    nodeSelection.call(drag)

    if (layoutType === 'force') {
      simulationRef.current = d3
        .forceSimulation(renderNodes)
        .force('link', d3.forceLink(renderLinks).id((node) => node.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-120))
        .force('collision', d3.forceCollide().radius((node) => Math.max(24, (node.size || 20) + 10)))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .on('tick', () => {
          linkSelection
            .attr('x1', (link) => link.source.x)
            .attr('y1', (link) => link.source.y)
            .attr('x2', (link) => link.target.x)
            .attr('y2', (link) => link.target.y)

          nodeSelection.attr('transform', (node) => `translate(${node.x},${node.y})`)
        })
    } else {
      applyStaticLayout(layoutType, renderNodes, renderLinks, width, height)

      linkSelection
        .attr('x1', (link) => link.source.x || 0)
        .attr('y1', (link) => link.source.y || 0)
        .attr('x2', (link) => link.target.x || 0)
        .attr('y2', (link) => link.target.y || 0)

      nodeSelection.attr('transform', (node) => `translate(${node.x || 0},${node.y || 0})`)
    }
  }, [nodes, links, layoutType, selectedNodeId, canvasVersion])

  return (
    <section
      className="graph-page"
      aria-label="Graph page"
      data-testid={GRAPH_SMOKE_TEST_IDS.page}
    >
      <header className="graph-header">
        <div>
          <h1>知识图谱</h1>
          <p className="graph-subtitle">可视化实体关系网络</p>
        </div>
      </header>

      <div className="graph-toolbar" data-testid={GRAPH_SMOKE_TEST_IDS.toolbar}>
        <div className="graph-toolbar-left">
          <button
            type="button"
            className="graph-action graph-action--primary"
            onClick={loadGraphData}
            disabled={loading}
            data-testid={GRAPH_SMOKE_TEST_IDS.refreshButton}
          >
            {loading ? '加载中...' : '刷新图谱'}
          </button>
        </div>

        <div className="graph-toolbar-center">
          <label className="graph-layout-label" htmlFor="graph-layout-select">
            布局
          </label>
          <select
            id="graph-layout-select"
            className="graph-layout-select"
            data-testid={GRAPH_SMOKE_TEST_IDS.layoutSelect}
            value={layoutType}
            onChange={(event) => setLayoutType(event.target.value)}
            disabled={loading || nodes.length === 0}
          >
            {LAYOUT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="graph-toolbar-right">
          <span className="graph-stat">实体: {nodes.length}</span>
          <span className="graph-stat">关系: {links.length}</span>
        </div>
      </div>

      <div className="graph-workspace">
        <div className="graph-canvas-shell" ref={containerRef}>
          <svg ref={svgRef} className="graph-svg" />

          {loading ? (
            <div
              className="graph-overlay"
              role="status"
              data-testid={GRAPH_SMOKE_TEST_IDS.loadingOverlay}
            >
              <div className="graph-spinner" />
              <p>加载图谱数据...</p>
            </div>
          ) : null}

          {!loading && error ? (
            <div
              className="graph-overlay graph-overlay--error"
              role="alert"
              data-testid={GRAPH_SMOKE_TEST_IDS.errorOverlay}
            >
              <p>{error}</p>
              <button type="button" className="graph-retry" onClick={loadGraphData}>
                重试
              </button>
            </div>
          ) : null}

          {!loading && !error && nodes.length === 0 ? (
            <div
              className="graph-overlay graph-overlay--empty"
              role="status"
              data-testid={GRAPH_SMOKE_TEST_IDS.emptyOverlay}
            >
              <p>暂无图谱数据，请先导入记忆或刷新后重试。</p>
            </div>
          ) : null}
        </div>

        {selectedNode ? (
          <aside
            className="graph-detail-panel"
            aria-label="节点详情"
            data-testid={GRAPH_SMOKE_TEST_IDS.detailPanel}
          >
            <div className="graph-detail-header">
              <h2>节点详情</h2>
              <button type="button" className="graph-close" onClick={() => setSelectedNodeId(null)}>
                关闭
              </button>
            </div>
            <div className="graph-detail-body">
              <div className="graph-detail-row">
                <span className="graph-detail-label">名称</span>
                <span className="graph-detail-value">{selectedNode.name}</span>
              </div>
              <div className="graph-detail-row">
                <span className="graph-detail-label">类型</span>
                <span className="graph-detail-badge">{selectedNode.type || '实体'}</span>
              </div>
              <div className="graph-detail-row">
                <span className="graph-detail-label">ID</span>
                <code className="graph-detail-code">{selectedNode.id}</code>
              </div>
              {selectedNode.description ? (
                <div className="graph-detail-row">
                  <span className="graph-detail-label">描述</span>
                  <p className="graph-detail-description">{selectedNode.description}</p>
                </div>
              ) : null}
            </div>
          </aside>
        ) : null}
      </div>
    </section>
  )
}
