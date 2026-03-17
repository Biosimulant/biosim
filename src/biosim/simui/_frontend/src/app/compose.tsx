import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'
import {
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type OnConnect,
} from '@xyflow/react'
import dagre from 'dagre'
import type { Api, ConfigGraph, GraphNode, GraphEdge, ModuleRegistry, ModuleSpec } from '../lib/api'

// We use Record<string, unknown> as node data to satisfy React Flow's constraint
type NodeData = Record<string, unknown>

// ── Dagre layout helper ──

export const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'LR'
): { nodes: Node[]; edges: Edge[] } => {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))
  const nodeWidth = 200
  const nodeHeight = 120
  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 100 })
  nodes.forEach((node) => dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight }))
  edges.forEach((edge) => dagreGraph.setEdge(edge.source, edge.target))
  dagre.layout(dagreGraph)
  const layoutedNodes = nodes.map((node) => {
    const pos = dagreGraph.node(node.id)
    return { ...node, position: { x: pos.x - nodeWidth / 2, y: pos.y - nodeHeight / 2 } }
  })
  return { nodes: layoutedNodes, edges }
}

// ── Graph conversion helpers ──

export const apiGraphToFlow = (
  graph: ConfigGraph,
  registry: ModuleRegistry | null
): { nodes: Node[]; edges: Edge[] } => {
  const nodes: Node[] = graph.nodes.map((n) => {
    const spec = registry?.modules[n.type]
    return {
      id: n.id,
      type: 'moduleNode',
      position: n.position,
      data: {
        label: n.id,
        moduleType: n.type,
        args: n.data.args,
        inputs: n.data.inputs.length > 0 ? n.data.inputs : (spec?.inputs || []),
        outputs: n.data.outputs.length > 0 ? n.data.outputs : (spec?.outputs || []),
      } as NodeData,
    }
  })
  const edges: Edge[] = graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    sourceHandle: e.sourceHandle,
    target: e.target,
    targetHandle: e.targetHandle,
    type: 'smoothstep',
    animated: false,
    style: { stroke: 'var(--primary-muted)', strokeWidth: 2 },
  }))
  return { nodes, edges }
}

export const flowToApiGraph = (
  nodes: Node[],
  edges: Edge[],
  meta: ConfigGraph['meta']
): ConfigGraph => {
  const apiNodes: GraphNode[] = nodes.map((n) => {
    const data = n.data as NodeData
    return {
      id: n.id,
      type: data.moduleType as string,
      position: n.position,
      data: { args: data.args as Record<string, unknown>, inputs: data.inputs as string[], outputs: data.outputs as string[] },
    }
  })
  const apiEdges: GraphEdge[] = edges.map((e) => ({
    id: e.id,
    source: e.source,
    sourceHandle: e.sourceHandle || '',
    target: e.target,
    targetHandle: e.targetHandle || '',
  }))
  return { nodes: apiNodes, edges: apiEdges, meta }
}

// ── Compose context ──

type ComposeState = {
  nodes: Node[]
  edges: Edge[]
  registry: ModuleRegistry | null
  selectedNode: Node | null
  configPath: string
  meta: ConfigGraph['meta']
  isDirty: boolean
  error: string | null
  isApplying: boolean
  centerView: 'canvas' | 'yaml'
  yamlPreview: string
  showYaml: boolean
  showFileList: boolean
  files: { name: string; path: string; is_dir: boolean }[]
}

type ComposeActions = {
  setNodes: React.Dispatch<React.SetStateAction<Node[]>>
  setEdges: React.Dispatch<React.SetStateAction<Edge[]>>
  onNodesChange: ReturnType<typeof useNodesState>[2]
  onEdgesChange: ReturnType<typeof useEdgesState>[2]
  setRegistry: (r: ModuleRegistry | null) => void
  setSelectedNode: (n: Node | null) => void
  setConfigPath: (p: string) => void
  setMeta: (m: ConfigGraph['meta']) => void
  setIsDirty: (d: boolean) => void
  setError: (e: string | null) => void
  setIsApplying: (a: boolean) => void
  setCenterView: (v: 'canvas' | 'yaml') => void
  setYamlPreview: (y: string) => void
  setShowYaml: (s: boolean) => void
  setShowFileList: (s: boolean) => void
  setFiles: (f: { name: string; path: string; is_dir: boolean }[]) => void
  onConnect: OnConnect
  onSelectionChange: (params: { nodes: Node[] }) => void
  onNodeDragStop: () => void
  onLayout: () => void
  onUpdateNode: (nodeId: string, args: Record<string, unknown>) => void
  onDeleteNode: (nodeId: string) => void
  onRenameNode: (oldId: string, newId: string) => void
  onNewConfig: () => void
  loadConfig: (path: string) => Promise<void>
  saveConfig: () => Promise<void>
  applyConfig: () => Promise<void>
  previewYaml: () => Promise<void>
  onPaletteDragStart: (event: React.DragEvent, moduleType: string, spec: ModuleSpec) => void
  onDragOver: (event: React.DragEvent) => void
  onDrop: (event: React.DragEvent) => void
  reactFlowWrapper: React.RefObject<HTMLDivElement | null>
}

const ComposeCtx = createContext<{ state: ComposeState; actions: ComposeActions } | null>(null)

export function ComposeProvider({ api, children }: { api: Api; children: React.ReactNode }) {
  const [nodes, setNodes, onNodesChange] = useNodesState([] as Node[])
  const [edges, setEdges, onEdgesChange] = useEdgesState([] as Edge[])
  const [registry, setRegistry] = useState<ModuleRegistry | null>(null)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [configPath, setConfigPath] = useState('')
  const [meta, setMeta] = useState<ConfigGraph['meta']>({})
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isApplying, setIsApplying] = useState(false)
  const [centerView, setCenterView] = useState<'canvas' | 'yaml'>('canvas')
  const [yamlPreview, setYamlPreview] = useState('')
  const [showYaml, setShowYaml] = useState(false)
  const [showFileList, setShowFileList] = useState(false)
  const [files, setFiles] = useState<{ name: string; path: string; is_dir: boolean }[]>([])
  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  // Initialize: load registry and current config
  React.useEffect(() => {
    const init = async () => {
      try {
        const [registryData, currentConfig] = await Promise.all([
          api.editor.getModules(),
          api.editor.getCurrent(),
        ])
        setRegistry(registryData)
        if (currentConfig.available && currentConfig.graph) {
          const { nodes: flowNodes, edges: flowEdges } = apiGraphToFlow(currentConfig.graph, registryData)
          const needsLayout = flowNodes.every(n => n.position.x === 0 && n.position.y === 0)
          if (needsLayout && flowNodes.length > 0) {
            const layouted = getLayoutedElements(flowNodes, flowEdges)
            setNodes(layouted.nodes)
            setEdges(layouted.edges)
          } else {
            setNodes(flowNodes)
            setEdges(flowEdges)
          }
          setMeta(currentConfig.graph.meta)
          setConfigPath(currentConfig.path || '')
          setIsDirty(false)
        } else {
          // No current config — start with empty canvas (user can open a file via toolbar)
          setMeta({ title: 'New Configuration' })
          setIsDirty(false)
          // Pre-load file list in background for when user clicks "Open"
          api.editor.listFiles().then(setFiles).catch(console.error)
        }
      } catch (err) {
        console.error('Failed to initialize editor:', err)
        api.editor.listFiles().then(setFiles).catch(console.error)
      }
    }
    init()
  }, [api, setNodes, setEdges])

  const onConnect: OnConnect = useCallback(
    (params: Connection) => {
      const newEdge: Edge = {
        ...params,
        id: `e${Date.now()}`,
        type: 'smoothstep',
        style: { stroke: 'var(--primary-muted)', strokeWidth: 2 },
      } as Edge
      setEdges((eds) => addEdge(newEdge, eds))
      setIsDirty(true)
    },
    [setEdges]
  )

  const onSelectionChange = useCallback(({ nodes: selectedNodes }: { nodes: Node[] }) => {
    setSelectedNode(selectedNodes.length === 1 ? selectedNodes[0] : null)
  }, [])

  const onNodeDragStop = useCallback(() => { setIsDirty(true) }, [])

  const onLayout = useCallback(() => {
    const layouted = getLayoutedElements(nodes, edges)
    setNodes(layouted.nodes)
    setEdges(layouted.edges)
    setIsDirty(true)
  }, [nodes, edges, setNodes, setEdges])

  const onUpdateNode = useCallback(
    (nodeId: string, args: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => n.id === nodeId ? { ...n, data: { ...n.data, args } } : n)
      )
      setIsDirty(true)
    },
    [setNodes]
  )

  const onDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId))
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelectedNode(null)
      setIsDirty(true)
    },
    [setNodes, setEdges]
  )

  const onRenameNode = useCallback(
    (oldId: string, newId: string) => {
      if (nodes.some(n => n.id === newId && n.id !== oldId)) {
        setError(`Node ID "${newId}" already exists`)
        return
      }
      setNodes((nds) =>
        nds.map((n) => n.id === oldId ? { ...n, id: newId, data: { ...n.data, label: newId } } : n)
      )
      setEdges((eds) =>
        eds.map((e) => {
          const updated = { ...e }
          if (e.source === oldId) updated.source = newId
          if (e.target === oldId) updated.target = newId
          return updated
        })
      )
      setSelectedNode((prev) => (prev?.id === oldId ? { ...prev, id: newId } : prev))
      setIsDirty(true)
    },
    [nodes, setNodes, setEdges]
  )

  const onNewConfig = useCallback(() => {
    setNodes([])
    setEdges([])
    setMeta({ title: 'New Configuration' })
    setConfigPath('')
    setIsDirty(true)
    setShowFileList(false)
  }, [setNodes, setEdges])

  const loadConfig = useCallback(async (path: string) => {
    try {
      setError(null)
      const graph = await api.editor.getConfig(path)
      const { nodes: flowNodes, edges: flowEdges } = apiGraphToFlow(graph, registry)
      const needsLayout = flowNodes.every(n => n.position.x === 0 && n.position.y === 0)
      if (needsLayout && flowNodes.length > 0) {
        const layouted = getLayoutedElements(flowNodes, flowEdges)
        setNodes(layouted.nodes)
        setEdges(layouted.edges)
      } else {
        setNodes(flowNodes)
        setEdges(flowEdges)
      }
      setMeta(graph.meta)
      setConfigPath(path)
      setIsDirty(false)
      setShowFileList(false)
    } catch (err) {
      setError(`Failed to load config: ${err}`)
    }
  }, [api, registry, setNodes, setEdges])

  const saveConfig = useCallback(async () => {
    if (!configPath) { setError('No config path specified'); return }
    try {
      const graph = flowToApiGraph(nodes, edges, meta)
      await api.editor.saveConfig(configPath, graph)
      setIsDirty(false)
      setError(null)
    } catch (err) {
      setError(`Failed to save: ${err}`)
    }
  }, [api, configPath, nodes, edges, meta])

  const applyConfig = useCallback(async () => {
    if (!configPath) { setError('No config path specified'); return }
    setIsApplying(true)
    try {
      const graph = flowToApiGraph(nodes, edges, meta)
      const result = await api.editor.applyConfig(graph, configPath)
      if (result.ok) {
        setIsDirty(false)
        setError(null)
        setError('Configuration applied successfully!')
        setTimeout(() => setError(null), 3000)
      } else {
        setError(`Failed to apply: ${result.error || 'Unknown error'}`)
      }
    } catch (err) {
      setError(`Failed to apply config: ${err}`)
    } finally {
      setIsApplying(false)
    }
  }, [api, configPath, nodes, edges, meta])

  const previewYaml = useCallback(async () => {
    try {
      const graph = flowToApiGraph(nodes, edges, meta)
      const result = await api.editor.toYaml(graph)
      setYamlPreview(result.yaml)
      setShowYaml(true)
    } catch (err) {
      setError(`Failed to generate YAML: ${err}`)
    }
  }, [api, nodes, edges, meta])

  const onPaletteDragStart = useCallback(
    (event: React.DragEvent, moduleType: string, spec: ModuleSpec) => {
      event.dataTransfer.setData('application/moduleType', moduleType)
      event.dataTransfer.setData('application/moduleSpec', JSON.stringify(spec))
      event.dataTransfer.effectAllowed = 'move'
    },
    []
  )

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault()
      const moduleType = event.dataTransfer.getData('application/moduleType')
      const specJson = event.dataTransfer.getData('application/moduleSpec')
      if (!moduleType || !specJson) return
      const spec: ModuleSpec = JSON.parse(specJson)
      const wrapper = reactFlowWrapper.current
      if (!wrapper) return
      const bounds = wrapper.getBoundingClientRect()
      const position = { x: event.clientX - bounds.left - 100, y: event.clientY - bounds.top - 50 }
      let baseName = spec.name.toLowerCase().replace(/[^a-z0-9]/g, '_')
      let counter = 1
      let newId = baseName
      while (nodes.some(n => n.id === newId)) { newId = `${baseName}_${counter++}` }
      const newNode: Node = {
        id: newId,
        type: 'moduleNode',
        position,
        data: {
          label: newId,
          moduleType,
          args: {},
          inputs: spec.inputs,
          outputs: spec.outputs,
        } satisfies Record<string, unknown>,
      }
      setNodes((nds) => [...nds, newNode])
      setIsDirty(true)
    },
    [nodes, setNodes]
  )

  const state: ComposeState = {
    nodes, edges, registry, selectedNode, configPath, meta, isDirty, error,
    isApplying, centerView, yamlPreview, showYaml, showFileList, files,
  }

  const actions: ComposeActions = {
    setNodes, setEdges, onNodesChange, onEdgesChange,
    setRegistry, setSelectedNode, setConfigPath, setMeta,
    setIsDirty, setError, setIsApplying, setCenterView,
    setYamlPreview, setShowYaml, setShowFileList, setFiles,
    onConnect, onSelectionChange, onNodeDragStop, onLayout,
    onUpdateNode, onDeleteNode, onRenameNode, onNewConfig,
    loadConfig, saveConfig, applyConfig, previewYaml,
    onPaletteDragStart, onDragOver, onDrop, reactFlowWrapper,
  }

  const value = useMemo(() => ({ state, actions }), [
    nodes, edges, registry, selectedNode, configPath, meta, isDirty, error,
    isApplying, centerView, yamlPreview, showYaml, showFileList, files,
    // actions are stable due to useCallback
  ])

  return <ComposeCtx.Provider value={value}>{children}</ComposeCtx.Provider>
}

export function useCompose() {
  const ctx = useContext(ComposeCtx)
  if (!ctx) throw new Error('useCompose must be used within ComposeProvider')
  return ctx
}
