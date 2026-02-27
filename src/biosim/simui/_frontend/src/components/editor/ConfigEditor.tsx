import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  useNodesState,
  useEdgesState,
  addEdge,
  type Node,
  type Edge,
  type Connection,
  type OnConnect,
  type NodeTypes,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from 'dagre'

import ModuleNode, { type ModuleNodeData } from './ModuleNode'
import ModulePalette from './ModulePalette'
import PropertiesPanel from './PropertiesPanel'
import type { Api, ConfigGraph, GraphNode, GraphEdge, ModuleRegistry, ModuleSpec } from '../../lib/api'

interface ConfigEditorProps {
  api: Api
  initialConfigPath?: string
}

// Dagre layout helper
const getLayoutedElements = (
  nodes: Node[],
  edges: Edge[],
  direction: 'TB' | 'LR' = 'LR'
): { nodes: Node[]; edges: Edge[] } => {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const nodeWidth = 200
  const nodeHeight = 120

  dagreGraph.setGraph({ rankdir: direction, nodesep: 50, ranksep: 100 })

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  })

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target)
  })

  dagre.layout(dagreGraph)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = dagreGraph.node(node.id)
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - nodeWidth / 2,
        y: nodeWithPosition.y - nodeHeight / 2,
      },
    }
  })

  return { nodes: layoutedNodes, edges }
}

// Convert API graph to React Flow nodes/edges
const apiGraphToFlow = (
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
      } as ModuleNodeData,
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

// Convert React Flow nodes/edges to API graph
const flowToApiGraph = (
  nodes: Node[],
  edges: Edge[],
  meta: ConfigGraph['meta']
): ConfigGraph => {
  const apiNodes: GraphNode[] = nodes.map((n) => {
    const data = n.data as ModuleNodeData
    return {
      id: n.id,
      type: data.moduleType,
      position: n.position,
      data: {
        args: data.args,
        inputs: data.inputs,
        outputs: data.outputs,
      },
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

const ConfigEditor: React.FC<ConfigEditorProps> = ({ api, initialConfigPath }) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([])
  const [edges, setEdges, onEdgesChange] = useEdgesState([])
  const [registry, setRegistry] = useState<ModuleRegistry | null>(null)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [configPath, setConfigPath] = useState(initialConfigPath || '')
  const [meta, setMeta] = useState<ConfigGraph['meta']>({})
  const [isDirty, setIsDirty] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [files, setFiles] = useState<{ name: string; path: string; is_dir: boolean }[]>([])
  const [showFileList, setShowFileList] = useState(!initialConfigPath)
  const [showYaml, setShowYaml] = useState(false)
  const [yamlPreview, setYamlPreview] = useState('')

  const reactFlowWrapper = useRef<HTMLDivElement>(null)

  // Dark theme colors
  const bg = '#0f0f0f'
  const surface = '#181818'
  const text = '#e0e0e0'
  const muted = '#888888'
  const border = '#2a2a2a'
  const accent = 'var(--primary)'

  const nodeTypes: NodeTypes = useMemo(() => ({ moduleNode: ModuleNode }), [])
  const [isApplying, setIsApplying] = useState(false)

  // Load registry and current config on mount
  useEffect(() => {
    const init = async () => {
      try {
        const [registryData, currentConfig] = await Promise.all([
          api.editor.getModules(),
          api.editor.getCurrent(),
        ])
        setRegistry(registryData)

        // If we have a current simulation config, load it automatically
        if (currentConfig.available && currentConfig.graph) {
          const { nodes: flowNodes, edges: flowEdges } = apiGraphToFlow(currentConfig.graph, registryData)

          // Apply layout if positions are all at origin
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
          setShowFileList(false)
        } else {
          // No current config, show file list
          const files = await api.editor.listFiles()
          setFiles(files)
          setShowFileList(true)
        }
      } catch (err) {
        console.error('Failed to initialize editor:', err)
        // Fallback: load file list
        api.editor.listFiles().then(setFiles).catch(console.error)
      }
    }
    init()
  }, [api, setNodes, setEdges])

  // Load config file
  const loadConfig = useCallback(async (path: string) => {
    try {
      setError(null)
      const graph = await api.editor.getConfig(path)
      const { nodes: flowNodes, edges: flowEdges } = apiGraphToFlow(graph, registry)

      // Apply layout if positions are all at origin
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

  // Save config
  const saveConfig = useCallback(async () => {
    if (!configPath) {
      setError('No config path specified')
      return
    }
    try {
      const graph = flowToApiGraph(nodes, edges, meta)
      await api.editor.saveConfig(configPath, graph)
      setIsDirty(false)
      setError(null)
    } catch (err) {
      setError(`Failed to save: ${err}`)
    }
  }, [api, configPath, nodes, edges, meta])

  // Apply config to running simulation
  const applyConfig = useCallback(async () => {
    if (!configPath) {
      setError('No config path specified')
      return
    }
    setIsApplying(true)
    try {
      const graph = flowToApiGraph(nodes, edges, meta)
      const result = await api.editor.applyConfig(graph, configPath)
      if (result.ok) {
        setIsDirty(false)
        setError(null)
        // Show success briefly
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

  // Auto-layout
  const onLayout = useCallback(() => {
    const layouted = getLayoutedElements(nodes, edges)
    setNodes(layouted.nodes)
    setEdges(layouted.edges)
    setIsDirty(true)
  }, [nodes, edges, setNodes, setEdges])

  // Handle new connection
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

  // Handle node selection
  const onSelectionChange = useCallback(({ nodes: selectedNodes }: { nodes: Node[] }) => {
    setSelectedNode(selectedNodes.length === 1 ? selectedNodes[0] : null)
  }, [])

  // Handle node drag to mark dirty
  const onNodeDragStop = useCallback(() => {
    setIsDirty(true)
  }, [])

  // Handle drop from palette
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
      const position = {
        x: event.clientX - bounds.left - 100,
        y: event.clientY - bounds.top - 50,
      }

      // Generate unique ID
      let baseName = spec.name.toLowerCase().replace(/[^a-z0-9]/g, '_')
      let counter = 1
      let newId = baseName
      while (nodes.some(n => n.id === newId)) {
        newId = `${baseName}_${counter++}`
      }

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
        } as ModuleNodeData,
      }

      setNodes((nds) => [...nds, newNode])
      setIsDirty(true)
    },
    [nodes, setNodes]
  )

  // Palette drag start handler
  const onPaletteDragStart = useCallback(
    (event: React.DragEvent, moduleType: string, spec: ModuleSpec) => {
      event.dataTransfer.setData('application/moduleType', moduleType)
      event.dataTransfer.setData('application/moduleSpec', JSON.stringify(spec))
      event.dataTransfer.effectAllowed = 'move'
    },
    []
  )

  // Update node args
  const onUpdateNode = useCallback(
    (nodeId: string, args: Record<string, unknown>) => {
      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === nodeId) {
            return { ...n, data: { ...n.data, args } as ModuleNodeData }
          }
          return n
        })
      )
      setIsDirty(true)
    },
    [setNodes]
  )

  // Delete node
  const onDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId))
      setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId))
      setSelectedNode(null)
      setIsDirty(true)
    },
    [setNodes, setEdges]
  )

  // Rename node
  const onRenameNode = useCallback(
    (oldId: string, newId: string) => {
      if (nodes.some(n => n.id === newId && n.id !== oldId)) {
        setError(`Node ID "${newId}" already exists`)
        return
      }

      setNodes((nds) =>
        nds.map((n) => {
          if (n.id === oldId) {
            return { ...n, id: newId, data: { ...n.data, label: newId } as ModuleNodeData }
          }
          return n
        })
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

  // New config
  const onNewConfig = useCallback(() => {
    setNodes([])
    setEdges([])
    setMeta({ title: 'New Configuration' })
    setConfigPath('')
    setIsDirty(true)
    setShowFileList(false)
  }, [setNodes, setEdges])

  // Preview YAML
  const onPreviewYaml = useCallback(async () => {
    try {
      const graph = flowToApiGraph(nodes, edges, meta)
      const result = await api.editor.toYaml(graph)
      setYamlPreview(result.yaml)
      setShowYaml(true)
    } catch (err) {
      setError(`Failed to generate YAML: ${err}`)
    }
  }, [api, nodes, edges, meta])

  // Button style helper
  const buttonStyle = {
    padding: '6px 12px',
    border: `1px solid ${border}`,
    borderRadius: '6px',
    background: surface,
    color: text,
    cursor: 'pointer',
    fontSize: '13px',
    fontWeight: 500,
  }

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100%', background: bg }}>
      {/* Left sidebar - Module Palette */}
      <div style={{ width: '240px', borderRight: `1px solid ${border}`, background: surface }}>
        <ModulePalette registry={registry} onDragStart={onPaletteDragStart} />
      </div>

      {/* Main canvas area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        {/* Toolbar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '8px 12px',
            borderBottom: `1px solid ${border}`,
            background: surface,
          }}
        >
          <button onClick={() => setShowFileList(true)} style={buttonStyle}>
            Open
          </button>
          <button onClick={onNewConfig} style={buttonStyle}>
            New
          </button>
          <button
            onClick={saveConfig}
            disabled={!isDirty || !configPath}
            style={{
              ...buttonStyle,
              background: isDirty && configPath ? accent : border,
              color: isDirty && configPath ? '#fff' : muted,
              cursor: isDirty && configPath ? 'pointer' : 'not-allowed',
            }}
          >
            Save
          </button>
          <button
            onClick={applyConfig}
            disabled={isApplying || !configPath}
            style={{
              ...buttonStyle,
              background: configPath && !isApplying ? '#22c55e' : border,
              color: configPath && !isApplying ? '#fff' : muted,
              cursor: configPath && !isApplying ? 'pointer' : 'not-allowed',
            }}
          >
            {isApplying ? 'Applying...' : 'Apply to Simulation'}
          </button>
          <div style={{ width: '1px', height: '20px', background: border }} />
          <button onClick={onLayout} style={buttonStyle}>
            Auto Layout
          </button>
          <button onClick={onPreviewYaml} style={buttonStyle}>
            View YAML
          </button>

          <div style={{ flex: 1 }} />

          {configPath && (
            <span style={{ fontSize: '12px', color: muted }}>
              {configPath}
              {isDirty && <span style={{ color: '#f59e0b' }}> (unsaved)</span>}
            </span>
          )}
        </div>

        {/* Message display (error or success) */}
        {error && (
          <div
            style={{
              padding: '8px 12px',
              background: error.includes('success') ? '#14352a' : '#3b1c1c',
              borderBottom: `1px solid ${error.includes('success') ? '#22c55e' : '#7f1d1d'}`,
              color: error.includes('success') ? '#86efac' : '#fca5a5',
              fontSize: '13px',
            }}
          >
            {error}
            <button
              onClick={() => setError(null)}
              style={{
                marginLeft: '8px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: error.includes('success') ? '#86efac' : '#fca5a5',
              }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Canvas */}
        <div ref={reactFlowWrapper} style={{ flex: 1, background: bg }} onDragOver={onDragOver} onDrop={onDrop}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onSelectionChange={onSelectionChange}
            onNodeDragStop={onNodeDragStop}
            nodeTypes={nodeTypes}
            fitView
            snapToGrid
            snapGrid={[15, 15]}
            deleteKeyCode={['Backspace', 'Delete']}
            onNodesDelete={() => setIsDirty(true)}
            onEdgesDelete={() => setIsDirty(true)}
            style={{ background: bg }}
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color={border} />
            <Controls style={{ background: surface, border: `1px solid ${border}`, borderRadius: '6px' }} />
            <MiniMap
              nodeColor={(node) => {
                const data = node.data as ModuleNodeData
                if (data.moduleType.includes('.neuro.')) return 'var(--primary)'
                if (data.moduleType.includes('.ecology.')) return '#22c55e'
                return '#a855f7'
              }}
              maskColor="rgba(11, 16, 32, 0.7)"
              style={{ background: surface, border: `1px solid ${border}`, borderRadius: '6px' }}
            />
            {meta.title && (
              <Panel position="top-center">
                <div style={{ padding: '6px 14px', background: surface, borderRadius: '6px', border: `1px solid ${border}`, fontSize: '14px', fontWeight: 600, color: text }}>
                  {meta.title}
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>
      </div>

      {/* Right sidebar - Properties */}
      <div style={{ width: '280px', borderLeft: `1px solid ${border}`, background: surface }}>
        <PropertiesPanel
          selectedNode={selectedNode}
          registry={registry}
          onUpdateNode={onUpdateNode}
          onDeleteNode={onDeleteNode}
          onRenameNode={onRenameNode}
        />
      </div>

      {/* File list modal */}
      {showFileList && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowFileList(false)}
        >
          <div
            style={{
              background: surface,
              borderRadius: '10px',
              border: `1px solid ${border}`,
              width: '400px',
              maxHeight: '500px',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: '16px', borderBottom: `1px solid ${border}` }}>
              <h3 style={{ margin: 0, fontSize: '16px', color: text, fontWeight: 600 }}>Open Configuration</h3>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
              {files.map((f) => (
                <div
                  key={f.path}
                  onClick={() => {
                    if (f.is_dir) {
                      api.editor.listFiles(f.path).then(setFiles)
                    } else {
                      loadConfig(f.path)
                    }
                  }}
                  style={{
                    padding: '10px 12px',
                    cursor: 'pointer',
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    color: text,
                    fontSize: '13px',
                  }}
                  onMouseOver={(e) => (e.currentTarget.style.background = bg)}
                  onMouseOut={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <span>{f.is_dir ? '📁' : '📄'}</span>
                  <span>{f.name}</span>
                </div>
              ))}
              {files.length === 0 && (
                <div style={{ padding: '16px', textAlign: 'center', color: muted, fontSize: '13px' }}>
                  No config files found
                </div>
              )}
            </div>
            <div style={{ padding: '12px', borderTop: `1px solid ${border}`, display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowFileList(false)} style={buttonStyle}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* YAML preview modal */}
      {showYaml && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => setShowYaml(false)}
        >
          <div
            style={{
              background: surface,
              borderRadius: '10px',
              border: `1px solid ${border}`,
              width: '600px',
              maxHeight: '80vh',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '0 8px 32px rgba(0,0,0,0.4)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ padding: '16px', borderBottom: `1px solid ${border}`, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0, fontSize: '16px', color: text, fontWeight: 600 }}>YAML Preview</h3>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(yamlPreview)
                }}
                style={{
                  ...buttonStyle,
                  padding: '4px 12px',
                  fontSize: '12px',
                }}
              >
                Copy
              </button>
            </div>
            <pre
              style={{
                flex: 1,
                overflow: 'auto',
                padding: '16px',
                margin: 0,
                background: bg,
                color: text,
                fontSize: '12px',
                fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                lineHeight: 1.5,
              }}
            >
              {yamlPreview}
            </pre>
            <div style={{ padding: '12px', borderTop: `1px solid ${border}`, display: 'flex', justifyContent: 'flex-end' }}>
              <button onClick={() => setShowYaml(false)} style={buttonStyle}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ConfigEditor
