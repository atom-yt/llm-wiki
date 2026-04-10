import { useEffect, useState, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Spin, Empty, Typography, Tag, Statistic, Row, Col, theme, message, Select, Button, Space, Slider } from 'antd'
import {
  FileTextOutlined,
  ApartmentOutlined,
  BulbOutlined,
  ToolOutlined,
  WarningOutlined,
  SearchOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
  FullscreenOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { fetchGraph, type GraphNode, type GraphEdge, type GraphStats } from '../services/api'

const { Text } = Typography

// Page type configuration
const TYPE_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  source: { label: 'Source', color: '#8c8c8c', icon: <FileTextOutlined /> },
  entity: { label: 'Entity', color: '#1677ff', icon: <ApartmentOutlined /> },
  concept: { label: 'Concept', color: '#52c41a', icon: <BulbOutlined /> },
  procedure: { label: 'Procedure', color: '#fa8c16', icon: <ToolOutlined /> },
  incident: { label: 'Incident', color: '#f5222d', icon: <WarningOutlined /> },
  query: { label: 'Query', color: '#722ed1', icon: <SearchOutlined /> },
  unknown: { label: 'Unknown', color: '#d9d9d9', icon: <FileTextOutlined /> },
}

interface Position {
  x: number
  y: number
}

interface SimulationNode extends Position {
  id: string
  node: GraphNode
  fixed?: boolean
}

interface SimulationEdge {
  source: SimulationNode
  target: SimulationNode
}

interface ViewState {
  zoom: number
  panX: number
  panY: number
}

export default function GraphPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { token } = theme.useToken()
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  const [loading, setLoading] = useState(true)
  const [nodes, setNodes] = useState<GraphNode[]>([])
  const [stats, setStats] = useState<GraphStats | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [hoveredNode, setHoveredNode] = useState<string | null>(null)
  const [filterType, setFilterType] = useState<string>('all')

  // Simulation state
  const [simNodes, setSimNodes] = useState<Map<string, SimulationNode>>(new Map())
  const [simEdges, setSimEdges] = useState<SimulationEdge[]>([])

  // View state (zoom and pan)
  const [viewState, setViewState] = useState<ViewState>({ zoom: 1, panX: 0, panY: 0 })

  // Dragging state
  const draggingRef = useRef<{ nodeId: string; startX: number; startY: number; nodeStartX: number; nodeStartY: number } | null>(null)
  const panningRef = useRef<{ startX: number; startY: number; viewStart: ViewState } | null>(null)

  // Mouse position tracking
  const mousePosRef = useRef<{ x: number; y: number } | null>(null)

  // Minimap state
  const [showMinimap] = useState(true)

  // Load graph data
  useEffect(() => {
    fetchGraph()
      .then(data => {
        setNodes(data.nodes)
        setStats(data.stats)
        initializeSimulation(data.nodes, data.edges)
      })
      .catch(err => {
        message.error(t('graph.loadError'))
        console.error(err)
      })
      .finally(() => setLoading(false))
  }, [])

  // Initialize simulation with better layout
  const initializeSimulation = useCallback((nodeData: GraphNode[], edgeData: GraphEdge[]) => {
    const width = canvasRef.current?.clientWidth || 800
    const height = canvasRef.current?.clientHeight || 600

    // Use a circular layout with better distribution
    const simNodeMap = new Map<string, SimulationNode>()
    const count = nodeData.length
    const centerX = 0
    const centerY = 0
    const baseRadius = Math.min(width, height) * 0.35

    nodeData.forEach((node, i) => {
      const angle = (i / count) * Math.PI * 2
      // Add some randomness to avoid perfect circles
      const randomOffset = Math.random() * 50 - 25
      const radius = baseRadius + randomOffset

      simNodeMap.set(node.id, {
        id: node.id,
        node,
        x: centerX + Math.cos(angle) * radius,
        y: centerY + Math.sin(angle) * radius,
      })
    })

    // Create edges
    const simEdgeList: SimulationEdge[] = []
    edgeData.forEach(edge => {
      const source = simNodeMap.get(edge.source)
      const target = simNodeMap.get(edge.target)
      if (source && target) {
        simEdgeList.push({ source, target })
      }
    })

    setSimNodes(simNodeMap)
    setSimEdges(simEdgeList)
  }, [])

  // Fit to screen after simulation initializes
  useEffect(() => {
    if (simNodes.size > 0) {
      // Small delay to ensure simulation has completed
      const timer = setTimeout(() => {
        fitToScreen()
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [simNodes.size])

  // Physics simulation
  useEffect(() => {
    if (simNodes.size === 0) return

    let frameCount = 0
    const maxFrames = 300
    const width = canvasRef.current?.clientWidth || 800
    const height = canvasRef.current?.clientHeight || 600

    const simulate = () => {
      const nodeArray = Array.from(simNodes.values())
      const nodeCount = nodeArray.length
      const k = Math.sqrt((width * height) / (nodeCount || 1)) * 0.6
      const alpha = Math.max(0.005, 0.5 - frameCount / maxFrames)

      if (alpha <= 0.005 || frameCount >= maxFrames) {
        return
      }

      // Apply forces to non-fixed nodes
      nodeArray.forEach(node => {
        // Skip fixed nodes (being dragged)
        if (node.fixed) return
        if (filterType !== 'all' && node.node.type !== filterType) return

        // Repulsion
        nodeArray.forEach(other => {
          if (node.id === other.id) return
          if (filterType !== 'all' && other.node.type !== filterType) return

          const dx = node.x - other.x
          const dy = node.y - other.y
          const dist = Math.sqrt(dx * dx + dy * dy) || 1
          const minDist = 60

          if (dist < minDist) {
            const force = (minDist * minDist) / (dist * dist)
            node.x = node.x + (dx / dist) * force * alpha * 3
            node.y = node.y + (dy / dist) * force * alpha * 3
          } else {
            const force = (k * k) / dist
            node.x = node.x + (dx / dist) * force * alpha
            node.y = node.y + (dy / dist) * force * alpha
          }
        })

        // Attraction to center
        const distToCenter = Math.sqrt(node.x * node.x + node.y * node.y) || 1
        node.x = node.x - (node.x / distToCenter) * 0.01 * alpha * distToCenter
        node.y = node.y - (node.y / distToCenter) * 0.01 * alpha * distToCenter
      })

      // Spring forces along edges
      simEdges.forEach(edge => {
        const sourceFilterOk = filterType === 'all' || edge.source.node.type === filterType
        const targetFilterOk = filterType === 'all' || edge.target.node.type === filterType

        if (!sourceFilterOk || !targetFilterOk) return

        const dx = edge.target.x - edge.source.x
        const dy = edge.target.y - edge.source.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const force = (dist - k * 0.5) * 0.008

        const fx = (dx / dist) * force * alpha
        const fy = (dy / dist) * force * alpha

        if (!edge.source.fixed) {
          edge.source.x = edge.source.x + fx
          edge.source.y = edge.source.y + fy
        }
        if (!edge.target.fixed) {
          edge.target.x = edge.target.x - fx
          edge.target.y = edge.target.y - fy
        }
      })

      setSimNodes(new Map(simNodes))
      frameCount++
      requestAnimationFrame(simulate)
    }

    simulate()
  }, [simEdges, filterType])

  // Transform screen to world coordinates
  const screenToWorld = useCallback((screenX: number, screenY: number) => {
    const canvas = canvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    const width = canvas.clientWidth
    const height = canvas.clientHeight

    const centerX = width / 2
    const centerY = height / 2

    return {
      x: (screenX - rect.left - centerX - viewState.panX) / viewState.zoom,
      y: (screenY - rect.top - centerY - viewState.panY) / viewState.zoom,
    }
  }, [viewState])

  // Handle wheel for zoom
  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault()

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const delta = -e.deltaY * 0.001
    const newZoom = Math.max(0.1, Math.min(5, viewState.zoom * (1 + delta)))

    // Zoom towards mouse position
    const width = canvas.clientWidth
    const height = canvas.clientHeight
    const centerX = width / 2
    const centerY = height / 2

    const worldX = (mouseX - centerX - viewState.panX) / viewState.zoom
    const worldY = (mouseY - centerY - viewState.panY) / viewState.zoom

    setViewState({
      zoom: newZoom,
      panX: mouseX - centerX - worldX * newZoom,
      panY: mouseY - centerY - worldY * newZoom,
    })
  }, [viewState])

  // Handle mouse down for drag/pan
  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const world = screenToWorld(mouseX, mouseY)

    // Check if clicking on a node
    let clickedNodeId: string | null = null
    let minDist = Infinity

    simNodes.forEach(simNode => {
      const visible = filterType === 'all' || simNode.node.type === filterType
      if (!visible) return

      const dx = world.x - simNode.x
      const dy = world.y - simNode.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      const size = Math.max(20, Math.min(50, 15 + (simNode.node.inbound + simNode.node.outbound) * 0.8))

      if (dist < size + 5 && dist < minDist) {
        minDist = dist
        clickedNodeId = simNode.id
      }
    })

    if (clickedNodeId) {
      const clickedNode = simNodes.get(clickedNodeId)
      if (clickedNode) {
        // Start dragging node
        draggingRef.current = {
          nodeId: clickedNodeId,
          startX: mouseX,
          startY: mouseY,
          nodeStartX: clickedNode.x,
          nodeStartY: clickedNode.y,
        }

        // Fix node position
        clickedNode.fixed = true
        setSimNodes(new Map(simNodes))
        setSelectedNode(clickedNode.node)
        canvas.style.cursor = 'grabbing'
      }
    } else {
      // Start panning
      panningRef.current = {
        startX: mouseX,
        startY: mouseY,
        viewStart: { ...viewState },
      }
      canvas.style.cursor = 'grabbing'
    }
  }, [screenToWorld, simNodes, filterType, viewState])

  // Handle mouse move for drag/pan
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    // Track mouse position
    mousePosRef.current = { x: mouseX, y: mouseY }

    // Handle node dragging
    if (draggingRef.current) {
      const { nodeId, startX, startY, nodeStartX, nodeStartY } = draggingRef.current

      const dx = (mouseX - startX) / viewState.zoom
      const dy = (mouseY - startY) / viewState.zoom

      const node = simNodes.get(nodeId)
      if (node) {
        node.x = nodeStartX + dx
        node.y = nodeStartY + dy
        simNodes.set(nodeId, node)
        setSimNodes(new Map(simNodes))
      }
      return
    }

    // Handle panning
    if (panningRef.current) {
      const { startX, startY, viewStart } = panningRef.current

      setViewState({
        zoom: viewState.zoom,
        panX: viewStart.panX + (mouseX - startX),
        panY: viewStart.panY + (mouseY - startY),
      })
      return
    }

    // Handle hover
    if (!draggingRef.current && !panningRef.current) {
      const world = screenToWorld(mouseX, mouseY)
      let hovered: string | null = null

      simNodes.forEach(simNode => {
        const visible = filterType === 'all' || simNode.node.type === filterType
        if (!visible) return

        const dx = world.x - simNode.x
        const dy = world.y - simNode.y
        const dist = Math.sqrt(dx * dx + dy * dy)
        const size = Math.max(20, Math.min(50, 15 + (simNode.node.inbound + simNode.node.outbound) * 0.8))

        if (dist < size + 5) {
          hovered = simNode.id
        }
      })

      setHoveredNode(hovered)
      canvas.style.cursor = hovered ? 'pointer' : 'grab'
    }
  }, [screenToWorld, simNodes, filterType, viewState])

  // Handle mouse up
  const handleMouseUp = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()

    // End dragging
    if (draggingRef.current) {
      const { nodeId } = draggingRef.current

      const node = simNodes.get(nodeId)
      if (node) {
        node.fixed = false
        simNodes.set(nodeId, node)
        setSimNodes(new Map(simNodes))
      }

      draggingRef.current = null
      const canvas = canvasRef.current
      if (canvas) {
        canvas.style.cursor = 'grab'
      }
    }

    // End panning
    panningRef.current = null

    const canvas = canvasRef.current
    if (canvas) {
      canvas.style.cursor = 'grab'
    }
  }, [simNodes])

  // Handle click for selection
  const handleClick = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    e.preventDefault()

    // If dragging occurred, don't treat as click
    if (draggingRef.current) {
      return
    }

    const canvas = canvasRef.current
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    const mouseX = e.clientX - rect.left
    const mouseY = e.clientY - rect.top

    const world = screenToWorld(mouseX, mouseY)

    let clickedNodeId: string | null = null
    let minDist = Infinity

    simNodes.forEach(simNode => {
      const visible = filterType === 'all' || simNode.node.type === filterType
      if (!visible) return

      const dx = world.x - simNode.x
      const dy = world.y - simNode.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      const size = Math.max(20, Math.min(50, 15 + (simNode.node.inbound + simNode.node.outbound) * 0.8))

      if (dist < size + 5 && dist < minDist) {
        minDist = dist
        clickedNodeId = simNode.id
      }
    })

    if (clickedNodeId) {
      const clickedNode = simNodes.get(clickedNodeId)
      if (clickedNode) {
        setSelectedNode(clickedNode.node)
      }
    } else {
      setSelectedNode(null)
    }
  }, [screenToWorld, simNodes, filterType])

  // Canvas rendering
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || simNodes.size === 0) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const width = canvas.clientWidth
    const height = canvas.clientHeight

    const dpr = window.devicePixelRatio || 1
    canvas.width = width * dpr
    canvas.height = height * dpr
    ctx.scale(dpr, dpr)
    ctx.clearRect(0, 0, width, height)

    const { zoom, panX, panY } = viewState

    ctx.save()
    ctx.translate(width / 2 + panX, height / 2 + panY)
    ctx.scale(zoom, zoom)

    // Draw edges
    ctx.strokeStyle = token.colorBorderSecondary
    ctx.lineWidth = 1.5 / zoom

    simEdges.forEach(edge => {
      const sourceVisible = filterType === 'all' || edge.source.node.type === filterType
      const targetVisible = filterType === 'all' || edge.target.node.type === filterType

      if (!sourceVisible || !targetVisible) return

      // Highlight edges connected to selected/hovered node
      const isHighlighted = selectedNode?.id === edge.source.id || selectedNode?.id === edge.target.id ||
                          hoveredNode === edge.source.id || hoveredNode === edge.target.id

      if (isHighlighted) {
        ctx.strokeStyle = token.colorPrimary
        ctx.lineWidth = 2 / zoom
      } else {
        ctx.strokeStyle = token.colorBorderSecondary
        ctx.lineWidth = 1.5 / zoom
      }

      ctx.beginPath()
      ctx.moveTo(edge.source.x, edge.source.y)
      ctx.lineTo(edge.target.x, edge.target.y)
      ctx.stroke()
    })

    // Draw nodes
    simNodes.forEach(simNode => {
      const node = simNode.node
      const visible = filterType === 'all' || node.type === filterType

      if (!visible) return

      const config = TYPE_CONFIG[node.type] || TYPE_CONFIG.unknown
      const x = simNode.x
      const y = simNode.y

      const size = Math.max(20, Math.min(50, 15 + (node.inbound + node.outbound) * 0.8))
      const isSelected = selectedNode?.id === node.id
      const isHovered = hoveredNode === node.id

      // Highlight halo
      if (isSelected || isHovered) {
        ctx.beginPath()
        ctx.arc(x, y, size + 10, 0, Math.PI * 2)
        ctx.fillStyle = isSelected ? token.colorPrimaryBg : 'rgba(24, 144, 255, 0.15)'
        ctx.fill()
      }

      // Node circle
      ctx.beginPath()
      ctx.arc(x, y, size, 0, Math.PI * 2)
      ctx.fillStyle = config.color
      ctx.fill()

      // Border
      ctx.strokeStyle = isSelected ? token.colorPrimary : 'rgba(0,0,0,0.15)'
      ctx.lineWidth = isSelected ? 3 / zoom : 2 / zoom
      ctx.stroke()

      // Label
      ctx.fillStyle = token.colorText
      const fontSize = Math.max(10, 12 / zoom)
      ctx.font = `${isSelected ? 'bold ' : ''}${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'top'

      const title = node.title || node.id
      const maxWidth = 150 / zoom
      let displayTitle = title
      if (ctx.measureText(title).width > maxWidth) {
        for (let i = title.length - 1; i > 0; i--) {
          const truncated = title.substring(0, i) + '...'
          if (ctx.measureText(truncated).width <= maxWidth) {
            displayTitle = truncated
            break
          }
        }
      }
      ctx.fillText(displayTitle, x, y + size + 6)
    })

    ctx.restore()

    // Draw minimap if enabled
    if (showMinimap) {
      drawMinimap(ctx, width, height, simNodes, simEdges, filterType, token)
    }
  }, [simNodes, simEdges, selectedNode, hoveredNode, filterType, viewState, showMinimap, token])

  // Minimap drawing
  const drawMinimap = useCallback((
    ctx: CanvasRenderingContext2D,
    width: number,
    height: number,
    nodes: Map<string, SimulationNode>,
    edges: SimulationEdge[],
    filterType: string,
    token: any
  ) => {
    if (nodes.size === 0) return

    const minimapSize = 150
    const minimapX = width - minimapSize - 10
    const minimapY = 10

    // Find bounds
    const positions = Array.from(nodes.values())
    const xs = positions.map(n => n.x)
    const ys = positions.map(n => n.y)
    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)

    const boundsWidth = maxX - minX || 1
    const boundsHeight = maxY - minY || 1
    const scaleX = (minimapSize - 10) / boundsWidth
    const scaleY = (minimapSize - 10) / boundsHeight
    const scale = Math.min(scaleX, scaleY)

    // Draw minimap background
    ctx.fillStyle = 'rgba(255,255,255,0.95)'
    ctx.strokeStyle = token.colorBorder
    ctx.lineWidth = 1
    ctx.fillRect(minimapX, minimapY, minimapSize, minimapSize)
    ctx.strokeRect(minimapX, minimapY, minimapSize, minimapSize)

    // Draw viewport indicator
    const viewportWidth = width / viewState.zoom
    const viewportHeight = height / viewState.zoom
    const vpX = minimapX + 5 + (-viewState.panX - viewportWidth / 2 - minX) * scale
    const vpY = minimapY + 5 + (-viewState.panY - viewportHeight / 2 - minY) * scale
    const vpW = viewportWidth * scale
    const vpH = viewportHeight * scale

    ctx.fillStyle = 'rgba(24, 144, 255, 0.1)'
    ctx.strokeStyle = token.colorPrimary
    ctx.lineWidth = 1
    ctx.fillRect(vpX, vpY, vpW, vpH)
    ctx.strokeRect(vpX, vpY, vpW, vpH)

    // Draw nodes in minimap
    nodes.forEach(simNode => {
      const visible = filterType === 'all' || simNode.node.type === filterType
      if (!visible) return

      const config = TYPE_CONFIG[simNode.node.type] || TYPE_CONFIG.unknown
      const mx = minimapX + 5 + (simNode.x - minX) * scale
      const my = minimapY + 5 + (simNode.y - minY) * scale

      ctx.fillStyle = config.color
      ctx.beginPath()
      ctx.arc(mx, my, 3, 0, Math.PI * 2)
      ctx.fill()
    })

    // Draw edges in minimap
    ctx.strokeStyle = token.colorBorderSecondary
    ctx.lineWidth = 0.5
    edges.forEach(edge => {
      const sourceVisible = filterType === 'all' || edge.source.node.type === filterType
      const targetVisible = filterType === 'all' || edge.target.node.type === filterType

      if (!sourceVisible || !targetVisible) return

      const sx = minimapX + 5 + (edge.source.x - minX) * scale
      const sy = minimapY + 5 + (edge.source.y - minY) * scale
      const tx = minimapX + 5 + (edge.target.x - minX) * scale
      const ty = minimapY + 5 + (edge.target.y - minY) * scale

      ctx.beginPath()
      ctx.moveTo(sx, sy)
      ctx.lineTo(tx, ty)
      ctx.stroke()
    })
  }, [viewState, filterType])

  // View controls
  const zoomIn = useCallback(() => {
    setViewState(prev => ({ ...prev, zoom: Math.min(5, prev.zoom * 1.2) }))
  }, [])

  const zoomOut = useCallback(() => {
    setViewState(prev => ({ ...prev, zoom: Math.max(0.1, prev.zoom / 1.2) }))
  }, [])

  const resetView = useCallback(() => {
    setViewState({ zoom: 1, panX: 0, panY: 0 })
  }, [])

  const fitToScreen = useCallback(() => {
    if (simNodes.size === 0) return

    const positions = Array.from(simNodes.values())
    const xs = positions.map(n => n.x)
    const ys = positions.map(n => n.y)

    const minX = Math.min(...xs)
    const maxX = Math.max(...xs)
    const minY = Math.min(...ys)
    const maxY = Math.max(...ys)

    const canvas = canvasRef.current
    if (!canvas) return

    const padding = 50
    const graphWidth = maxX - minX + padding * 2
    const graphHeight = maxY - minY + padding * 2

    const scaleX = canvas.clientWidth / graphWidth
    const scaleY = canvas.clientHeight / graphHeight
    const zoom = Math.min(scaleX, scaleY, 2)

    const centerX = (minX + maxX) / 2
    const centerY = (minY + maxY) / 2

    setViewState({
      zoom,
      panX: -centerX * zoom,
      panY: -centerY * zoom,
    })
  }, [simNodes])

  const handleNodeClick = useCallback(() => {
    if (selectedNode) {
      navigate(`/wiki/${selectedNode.id}`)
    }
  }, [selectedNode, navigate])

  const getTypeColor = (type: string) => {
    return TYPE_CONFIG[type]?.color || TYPE_CONFIG.unknown.color
  }

  if (loading) {
    return <Spin size="large" style={{ display: 'block', marginTop: 80, textAlign: 'center' }} />
  }

  if (nodes.length === 0) {
    return <Empty description={t('graph.noPages')} style={{ marginTop: 80 }} />
  }

  return (
    <div style={{ display: 'flex', gap: 20, height: 'calc(100vh - 200px)' }}>
      {/* Graph canvas */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }} ref={containerRef}>
        <div style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center', justifyContent: 'space-between' }}>
          <Space>
            <Text strong>{t('graph.title')}</Text>
            <Select
              value={filterType}
              onChange={setFilterType}
              style={{ width: 150 }}
              options={[
                { label: t('graph.filterAll'), value: 'all' },
                { label: TYPE_CONFIG.source.label, value: 'source' },
                { label: TYPE_CONFIG.entity.label, value: 'entity' },
                { label: TYPE_CONFIG.concept.label, value: 'concept' },
                { label: TYPE_CONFIG.procedure.label, value: 'procedure' },
                { label: TYPE_CONFIG.incident.label, value: 'incident' },
                { label: TYPE_CONFIG.query.label, value: 'query' },
              ]}
            />
          </Space>

          {/* View controls */}
          <Space>
            <Button
              icon={<ZoomOutOutlined />}
              onClick={zoomOut}
              size="small"
              title="Zoom out"
            />
            <Button
              icon={<ZoomInOutlined />}
              onClick={zoomIn}
              size="small"
              title="Zoom in"
            />
            <Button
              icon={<FullscreenOutlined />}
              onClick={fitToScreen}
              size="small"
              title="Fit to screen"
            />
            <Button
              icon={<ReloadOutlined />}
              onClick={resetView}
              size="small"
              title="Reset view"
            />
          </Space>
        </div>

        <Card
          style={{ flex: 1, padding: 0 }}
          bodyStyle={{ padding: 0, height: '100%' }}
        >
          <canvas
            ref={canvasRef}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onClick={handleClick}
            style={{ width: '100%', height: '100%', display: 'block', cursor: 'grab' }}
          />
        </Card>

        {/* Zoom slider */}
        <div style={{ padding: '8px 0', display: 'flex', alignItems: 'center', gap: 12 }}>
          <Text type="secondary" style={{ fontSize: 12 }}>缩放: {(viewState.zoom * 100).toFixed(0)}%</Text>
          <Slider
            min={0.1}
            max={5}
            step={0.1}
            value={viewState.zoom}
            onChange={(zoom) => setViewState(prev => ({ ...prev, zoom }))}
            style={{ flex: 1 }}
          />
        </div>
      </div>

      {/* Sidebar */}
      <div style={{ width: 320 }}>
        {stats && (
          <Card title={t('graph.statistics')} style={{ marginBottom: 16 }}>
            <Row gutter={[8, 16]}>
              <Col span={12}>
                <Statistic
                  title={t('graph.totalNodes')}
                  value={stats.total_nodes}
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={t('graph.totalEdges')}
                  value={stats.total_edges}
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={t('graph.orphanPages')}
                  value={stats.orphan_pages}
                  valueStyle={{ fontSize: 18, color: stats.orphan_pages > 0 ? token.colorError : token.colorSuccess }}
                />
              </Col>
              <Col span={12}>
                <Statistic
                  title={t('graph.density')}
                  value={(stats.total_edges / (stats.total_nodes * (stats.total_nodes - 1) / 2) * 100).toFixed(1)}
                  suffix="%"
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
            </Row>
          </Card>
        )}

        <Card title={t('graph.topHubs')} style={{ marginBottom: 16 }}>
          {stats?.hubs.map(hub => (
            <div key={hub.page} style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between' }}>
              <Text ellipsis style={{ maxWidth: 180 }}>{hub.page}</Text>
              <Tag color="blue">{hub.links}</Tag>
            </div>
          ))}
        </Card>

        {/* Type legend */}
        <Card title={t('graph.types')}>
          {Object.entries(TYPE_CONFIG).map(([type, config]) => (
            <div key={type} style={{ marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
              <div
                style={{
                  width: 12,
                  height: 12,
                  borderRadius: '50%',
                  backgroundColor: config.color,
                }}
              />
              <Text>{config.label}</Text>
              <Tag style={{ marginLeft: 'auto' }}>{nodes.filter(n => n.type === type).length}</Tag>
            </div>
          ))}
        </Card>

        {/* Selected node details */}
        {selectedNode && (
          <Card
            title={t('graph.nodeDetails')}
            style={{ marginTop: 16 }}
            extra={
              <Text type="secondary" style={{ cursor: 'pointer' }} onClick={handleNodeClick}>
                {t('graph.viewPage')} &rarr;
              </Text>
            }
          >
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">{t('graph.nodeId')}</Text>
              <div style={{ wordBreak: 'break-all', marginTop: 4 }}>{selectedNode.id}</div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">{t('graph.title')}</Text>
              <div style={{ marginTop: 4 }}>{selectedNode.title || '-'}</div>
            </div>
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">{t('graph.type')}</Text>
              <Tag color={getTypeColor(selectedNode.type)} style={{ marginLeft: 8, marginTop: 4 }}>
                {TYPE_CONFIG[selectedNode.type]?.label || selectedNode.type}
              </Tag>
            </div>
            <Row gutter={16}>
              <Col span={12}>
                <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>{t('graph.inbound')}</Text>
                <Text strong style={{ fontSize: 18 }}>{selectedNode.inbound}</Text>
              </Col>
              <Col span={12}>
                <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>{t('graph.outbound')}</Text>
                <Text strong style={{ fontSize: 18 }}>{selectedNode.outbound}</Text>
              </Col>
            </Row>
          </Card>
        )}
      </div>
    </div>
  )
}
