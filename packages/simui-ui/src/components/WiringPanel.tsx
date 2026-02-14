import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import dagre from 'dagre'
import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type Edge,
  type EdgeChange,
  type Node,
  type NodeChange,
  type NodeProps,
  type NodeTypes,
} from '@xyflow/react'
import { isJsonControl, useUi } from '../app/ui'
import { useApi } from '../app/providers'

type WiringEntry = { from: string; to?: unknown; targets?: unknown }

type WiringNodeData = Record<string, unknown> & {
  label: string
  inputs: string[]
  outputs: string[]
}

const NEW_HANDLE_ID = '__new__'

type WiringFlowNode = Node<WiringNodeData, 'wiringNode'>

type PositionMap = Record<string, { x: number; y: number }>

type PortsByAlias = Record<string, { inputs?: string[]; outputs?: string[] }>

type WiringLayout = {
  version: number
  nodes: PositionMap
  hidden_modules: string[]
}

type StoredWiring = {
  wiring: string
  updatedAt: number
}

type PendingConnect = {
  source: string
  target: string
  sourceHandle: string
  targetHandle: string
  sourcePort: string
  targetPort: string
  mode: 'from' | 'to' | 'both'
}

function parseRef(ref: string): { module: string; port: string } | null {
  const idx = ref.indexOf('.')
  if (idx <= 0 || idx >= ref.length - 1) return null
  return { module: ref.slice(0, idx), port: ref.slice(idx + 1) }
}

function normalizeWiring(raw: unknown): WiringEntry[] {
  if (!Array.isArray(raw)) throw new Error('Wiring must be a JSON array.')
  return raw.filter((entry) => entry && typeof entry === 'object') as WiringEntry[]
}

function wiringToFlow(
  wiring: WiringEntry[],
  baseModules: string[],
  portsByAlias: PortsByAlias,
  hiddenModules: Set<string>,
  prevNodes: WiringFlowNode[]
): { nodes: WiringFlowNode[]; edges: Edge[]; needsLayout: boolean } {
  const outputsByModule = new Map<string, Set<string>>()
  const inputsByModule = new Map<string, Set<string>>()
  const moduleIds = new Set<string>([...baseModules, ...Object.keys(portsByAlias || {})])

  for (const [alias, ports] of Object.entries(portsByAlias || {})) {
    if (!outputsByModule.has(alias)) outputsByModule.set(alias, new Set())
    if (!inputsByModule.has(alias)) inputsByModule.set(alias, new Set())
    for (const p of ports.outputs || []) outputsByModule.get(alias)!.add(String(p))
    for (const p of ports.inputs || []) inputsByModule.get(alias)!.add(String(p))
  }

  const edges: Edge[] = []
  let edgeSeq = 0
  for (const entry of wiring) {
    const srcRef = typeof entry.from === 'string' ? entry.from : ''
    const dstRefsRaw = (entry as any).to ?? (entry as any).targets
    const dstRefs: string[] = typeof dstRefsRaw === 'string' ? [dstRefsRaw] : Array.isArray(dstRefsRaw) ? dstRefsRaw : []
    const src = parseRef(srcRef)
    if (!src) continue
    moduleIds.add(src.module)
    if (!outputsByModule.has(src.module)) outputsByModule.set(src.module, new Set())
    outputsByModule.get(src.module)!.add(src.port)

    for (const dstRef of dstRefs) {
      if (typeof dstRef !== 'string') continue
      const dst = parseRef(dstRef)
      if (!dst) continue
      moduleIds.add(dst.module)
      if (!inputsByModule.has(dst.module)) inputsByModule.set(dst.module, new Set())
      inputsByModule.get(dst.module)!.add(dst.port)
      edgeSeq += 1
      edges.push({
        id: `w-${edgeSeq}-${srcRef}->${dstRef}`,
        source: src.module,
        sourceHandle: src.port,
        target: dst.module,
        targetHandle: dst.port,
        type: 'smoothstep',
        style: { stroke: '#6b7280', strokeWidth: 2 },
      })
    }
  }

  for (const hidden of hiddenModules) moduleIds.delete(hidden)

  const prevById = new Map(prevNodes.map((n) => [n.id, n]))
  const nodes: WiringFlowNode[] = Array.from(moduleIds).map((id) => {
    const prev = prevById.get(id)
    const inputs = Array.from(inputsByModule.get(id) ?? []).sort()
    const outputs = Array.from(outputsByModule.get(id) ?? []).sort()
    return {
      id,
      type: 'wiringNode',
      position: prev?.position ?? { x: 0, y: 0 },
      data: { label: id, inputs, outputs },
    }
  })

  const needsLayout = nodes.length > 0 && nodes.every((n) => n.position.x === 0 && n.position.y === 0)
  return { nodes, edges, needsLayout }
}

function layoutFlow(nodes: WiringFlowNode[], edges: Edge[]): WiringFlowNode[] {
  const dagreGraph = new dagre.graphlib.Graph()
  dagreGraph.setDefaultEdgeLabel(() => ({}))

  const nodeWidth = 220
  const nodeHeight = 140
  dagreGraph.setGraph({ rankdir: 'LR', nodesep: 40, ranksep: 80 })

  for (const node of nodes) {
    dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight })
  }
  for (const edge of edges) {
    dagreGraph.setEdge(edge.source, edge.target)
  }

  dagre.layout(dagreGraph)

  return nodes.map((node) => {
    const pos = dagreGraph.node(node.id)
    return {
      ...node,
      position: {
        x: pos.x - nodeWidth / 2,
        y: pos.y - nodeHeight / 2,
      },
    }
  })
}

function wiringToEdges(rawWiring: unknown): Edge[] {
  const wiring = normalizeWiring(rawWiring)
  const edges: Edge[] = []
  let edgeSeq = 0
  for (const entry of wiring) {
    const srcRef = typeof entry.from === 'string' ? entry.from : ''
    const dstRefsRaw = (entry as any).to ?? (entry as any).targets
    const dstRefs: string[] = typeof dstRefsRaw === 'string' ? [dstRefsRaw] : Array.isArray(dstRefsRaw) ? dstRefsRaw : []
    const src = parseRef(srcRef)
    if (!src) continue
    for (const dstRef of dstRefs) {
      if (typeof dstRef !== 'string') continue
      const dst = parseRef(dstRef)
      if (!dst) continue
      edgeSeq += 1
      edges.push({
        id: `w-${edgeSeq}-${srcRef}->${dstRef}`,
        source: src.module,
        sourceHandle: src.port,
        target: dst.module,
        targetHandle: dst.port,
        type: 'smoothstep',
        style: { stroke: '#6b7280', strokeWidth: 2 },
      })
    }
  }
  return edges
}

function edgesToWiring(edges: Edge[]): Array<{ from: string; to: string[] }> {
  const grouped = new Map<string, Set<string>>()
  for (const edge of edges) {
    if (!edge.sourceHandle || !edge.targetHandle) continue
    const from = `${edge.source}.${edge.sourceHandle}`
    const to = `${edge.target}.${edge.targetHandle}`
    if (!grouped.has(from)) grouped.set(from, new Set())
    grouped.get(from)!.add(to)
  }
  return Array.from(grouped.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([from, targets]) => ({ from, to: Array.from(targets).sort() }))
}

const WiringNode: React.FC<NodeProps<WiringFlowNode>> = ({ data, selected }) => {
  const border = selected ? 'var(--warning)' : 'var(--border)'
  return (
    <div
      style={{
        background: 'var(--surface-2)',
        border: `1px solid ${border}`,
        borderRadius: 10,
        minWidth: 200,
        boxShadow: selected ? '0 0 0 2px rgba(234, 179, 8, 0.3)' : 'var(--shadow)',
        overflow: 'hidden',
        fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
      }}
    >
      <div
        style={{
          padding: '10px 12px',
          background: 'var(--surface)',
          borderBottom: '1px solid var(--border)',
          fontWeight: 700,
          fontSize: 13,
          color: 'var(--text)',
        }}
      >
        {data.label}
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, padding: '10px 8px 12px 8px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ paddingLeft: 6, fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>Inputs</div>
          {data.inputs.length === 0 ? (
            <div style={{ paddingLeft: 6, fontSize: 11, color: 'var(--muted)', fontStyle: 'italic' }}>none</div>
          ) : (
            data.inputs.map((port) => (
              <div key={port} style={{ position: 'relative', paddingLeft: 18 }}>
                <Handle
                  type="target"
                  position={Position.Left}
                  id={port}
                  style={{
                    width: 10,
                    height: 10,
                    left: -5,
                    background: '#6b7280',
                    border: '2px solid var(--surface-2)',
                  }}
                />
                <span style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'nowrap' }}>{port}</span>
              </div>
            ))
          )}
          <div style={{ position: 'relative', paddingLeft: 18, opacity: 0.85 }}>
            <Handle
              type="target"
              position={Position.Left}
              id={NEW_HANDLE_ID}
              style={{
                width: 10,
                height: 10,
                left: -5,
                background: 'var(--warning)',
                border: '2px solid var(--surface-2)',
              }}
            />
            <span style={{ fontSize: 12, color: 'var(--muted)', whiteSpace: 'nowrap' }}>+ add</span>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, alignItems: 'flex-end' }}>
          <div style={{ paddingRight: 6, fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>Outputs</div>
          {data.outputs.length === 0 ? (
            <div style={{ paddingRight: 6, fontSize: 11, color: 'var(--muted)', fontStyle: 'italic' }}>none</div>
          ) : (
            data.outputs.map((port) => (
              <div key={port} style={{ position: 'relative', paddingRight: 18 }}>
                <span style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'nowrap' }}>{port}</span>
                <Handle
                  type="source"
                  position={Position.Right}
                  id={port}
                  style={{
                    width: 10,
                    height: 10,
                    right: -5,
                    background: 'var(--primary)',
                    border: '2px solid var(--surface-2)',
                  }}
                />
              </div>
            ))
          )}
          <div style={{ position: 'relative', paddingRight: 18, opacity: 0.85 }}>
            <span style={{ fontSize: 12, color: 'var(--muted)', whiteSpace: 'nowrap' }}>+ add</span>
            <Handle
              type="source"
              position={Position.Right}
              id={NEW_HANDLE_ID}
              style={{
                width: 10,
                height: 10,
                right: -5,
                background: 'var(--warning)',
                border: '2px solid var(--surface-2)',
              }}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default function WiringPanel() {
  const api = useApi()
  const { state, actions } = useUi()
  const wiringControl = useMemo(() => {
    const controls = state.spec?.controls ?? []
    return controls.find((c) => isJsonControl(c) && c.name === 'wiring')
  }, [state.spec])
  const wiringLayoutControl = useMemo(() => {
    const controls = state.spec?.controls ?? []
    return controls.find((c) => isJsonControl(c) && c.name === 'wiring_layout')
  }, [state.spec])
  const modulePortsControl = useMemo(() => {
    const controls = state.spec?.controls ?? []
    return controls.find((c) => isJsonControl(c) && c.name === 'module_ports')
  }, [state.spec])
  const modelsControl = useMemo(() => {
    const controls = state.spec?.controls ?? []
    return controls.find((c) => isJsonControl(c) && c.name === 'models')
  }, [state.spec])

  const [isExpanded, setIsExpanded] = useState(false)
  const [parseError, setParseError] = useState<string | null>(null)
  const [showRaw, setShowRaw] = useState(false)
  const [rawDraft, setRawDraft] = useState<string>('')
  const [pendingConnect, setPendingConnect] = useState<PendingConnect | null>(null)
  const lastAppliedRef = useRef<string>('')
  const lastHydrateSigRef = useRef<string>('')

  const editingDisabled = !!state.status?.running

  const [storageKey, setStorageKey] = useState<string>('simui:wiring:default')

  useEffect(() => {
    let mounted = true
    const computeKey = async () => {
      try {
        const st = await api.state()
        if (!mounted) return
        const runId = (st as any)?.run?.id
        if (typeof runId === 'string' && runId) {
          setStorageKey(`simui:wiring:run:${runId}`)
          return
        }
        const target = (st as any)?.target
        const spaceId = target?.spaceId
        const spaceCommit = target?.spaceCommit
        if (typeof spaceId === 'string' && spaceId) {
          setStorageKey(`simui:wiring:draft:space:${spaceId}:${spaceCommit || 'head'}`)
          return
        }
        const modelId = target?.modelId
        const modelCommit = target?.modelCommit
        if (typeof modelId === 'string' && modelId) {
          setStorageKey(`simui:wiring:draft:model:${modelId}:${modelCommit || 'head'}`)
          return
        }
        const title = state.spec?.title || 'default'
        setStorageKey(`simui:wiring:title:${title}`)
      } catch {
        const title = state.spec?.title || 'default'
        setStorageKey(`simui:wiring:title:${title}`)
      }
    }
    void computeKey()
    return () => {
      mounted = false
    }
  }, [api, state.spec?.title])

  const wiringText = useMemo(() => {
    if (!wiringControl) return null
    const raw = state.controls.wiring
    if (raw === undefined) return String((wiringControl as any).default ?? '[]')
    return typeof raw === 'string' ? raw : String(raw)
  }, [state.controls.wiring, wiringControl])

  const wiringLayoutText = useMemo(() => {
    if (!wiringLayoutControl) return null
    const raw = (state.controls as any).wiring_layout
    if (raw === undefined) return String((wiringLayoutControl as any).default ?? '{"version":1,"nodes":{},"hidden_modules":[]}')
    return typeof raw === 'string' ? raw : String(raw)
  }, [(state.controls as any).wiring_layout, wiringLayoutControl])

  const modulePortsText = useMemo(() => {
    if (!modulePortsControl) return null
    const raw = (state.controls as any).module_ports
    if (raw === undefined) return String((modulePortsControl as any).default ?? '{}')
    return typeof raw === 'string' ? raw : String(raw)
  }, [(state.controls as any).module_ports, modulePortsControl])

  const modelsText = useMemo(() => {
    if (!modelsControl) return null
    const raw = (state.controls as any).models
    if (raw === undefined) return String((modelsControl as any).default ?? '[]')
    return typeof raw === 'string' ? raw : String(raw)
  }, [(state.controls as any).models, modelsControl])

  const portsByAlias: PortsByAlias = useMemo(() => {
    if (!modulePortsText) return {}
    try {
      const parsed = JSON.parse(modulePortsText)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
      return parsed as PortsByAlias
    } catch {
      return {}
    }
  }, [modulePortsText])

  const baselineModelsByAliasRef = useRef<Map<string, any> | null>(null)
  useEffect(() => {
    if (!modelsControl) return
    if (baselineModelsByAliasRef.current) return
    const raw = String((modelsControl as any).default ?? '[]')
    try {
      const parsed = JSON.parse(raw)
      if (!Array.isArray(parsed)) return
      const map = new Map<string, any>()
      parsed.forEach((entry, index) => {
        if (!entry || typeof entry !== 'object') return
        const alias = String((entry as any).alias ?? (entry as any).repo_full_name ?? (entry as any).repo ?? `module-${index + 1}`)
        if (!alias) return
        map.set(alias, entry)
      })
      baselineModelsByAliasRef.current = map
    } catch {
      // ignore
    }
  }, [modelsControl])

  const currentModelsByAlias: Map<string, any> = useMemo(() => {
    const map = new Map<string, any>()
    if (!modelsText) return map
    try {
      const parsed = JSON.parse(modelsText)
      if (!Array.isArray(parsed)) return map
      parsed.forEach((entry, index) => {
        if (!entry || typeof entry !== 'object') return
        const alias = String((entry as any).alias ?? (entry as any).repo_full_name ?? (entry as any).repo ?? `module-${index + 1}`)
        if (!alias) return
        map.set(alias, entry)
      })
    } catch {
      // ignore
    }
    return map
  }, [modelsText])

  const compositionAliases = useMemo(() => {
    if (!modelsControl) return null
    const baseline = baselineModelsByAliasRef.current
    if (!baseline) return null
    return Array.from(baseline.keys()).sort((a, b) => a.localeCompare(b))
  }, [modelsControl])

  const layout: WiringLayout = useMemo(() => {
    const fallback: WiringLayout = { version: 1, nodes: {}, hidden_modules: [] }
    if (!wiringLayoutText) return fallback
    try {
      const parsed = JSON.parse(wiringLayoutText)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return fallback
      const nodes = (parsed as any).nodes
      const hidden = (parsed as any).hidden_modules
      return {
        version: typeof (parsed as any).version === 'number' ? (parsed as any).version : 1,
        nodes: nodes && typeof nodes === 'object' && !Array.isArray(nodes) ? (nodes as PositionMap) : {},
        hidden_modules: Array.isArray(hidden) ? hidden.map(String) : [],
      }
    } catch {
      return fallback
    }
  }, [wiringLayoutText])

  useEffect(() => {
    if (!wiringControl) return
    const next: Record<string, string> = {}

    if (state.controls.wiring === undefined) {
      const stored = (() => {
        try {
          const raw = localStorage.getItem(storageKey)
          if (!raw) return null
          const parsed = JSON.parse(raw) as StoredWiring
          if (!parsed || typeof parsed.wiring !== 'string') return null
          return parsed.wiring
        } catch {
          return null
        }
      })()
      next.wiring = stored ?? String((wiringControl as any).default ?? '[]')
    }

    if (wiringLayoutControl && (state.controls as any).wiring_layout === undefined) {
      next.wiring_layout = String((wiringLayoutControl as any).default ?? '{"version":1,"nodes":{},"hidden_modules":[]}')
    }

    if (modulePortsControl && (state.controls as any).module_ports === undefined) {
      next.module_ports = String((modulePortsControl as any).default ?? '{}')
    }

    if (modelsControl && (state.controls as any).models === undefined) {
      next.models = String((modelsControl as any).default ?? '[]')
    }

    if (Object.keys(next).length > 0) actions.setControls(next)
  }, [actions, modelsControl, modulePortsControl, state.controls, storageKey, wiringControl, wiringLayoutControl])

  const [nodes, setNodes] = useState<WiringFlowNode[]>([])
  const [edges, setEdges] = useState<Edge[]>([])

  const nodeTypes: NodeTypes = useMemo(() => ({ wiringNode: WiringNode }), [])

  const updateLayout = useCallback((nextLayout: WiringLayout) => {
    if (wiringLayoutControl) {
      actions.setControls({ wiring_layout: JSON.stringify(nextLayout, null, 2) })
    } else {
      try {
        localStorage.setItem(`${storageKey}:layout`, JSON.stringify(nextLayout))
      } catch {
        // ignore
      }
    }
  }, [actions, storageKey, wiringLayoutControl])

  const readFallbackLayout = useCallback((): WiringLayout => {
    const base: WiringLayout = { version: 1, nodes: {}, hidden_modules: [] }
    if (wiringLayoutControl) return layout
    try {
      const raw = localStorage.getItem(`${storageKey}:layout`)
      if (!raw) return base
      const parsed = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return base
      return {
        version: typeof (parsed as any).version === 'number' ? (parsed as any).version : 1,
        nodes: (parsed as any).nodes && typeof (parsed as any).nodes === 'object' ? (parsed as any).nodes : {},
        hidden_modules: Array.isArray((parsed as any).hidden_modules) ? (parsed as any).hidden_modules.map(String) : [],
      }
    } catch {
      return base
    }
  }, [layout, storageKey, wiringLayoutControl])

  const effectiveLayout = useMemo(
    () => (wiringLayoutControl ? layout : readFallbackLayout()),
    [layout, readFallbackLayout, wiringLayoutControl]
  )
  const hiddenModules = useMemo(() => new Set<string>(effectiveLayout.hidden_modules || []), [effectiveLayout.hidden_modules])

  const setModelsText = useCallback((nextModels: unknown[]) => {
    if (!modelsControl) return
    actions.setControls({ models: JSON.stringify(nextModels, null, 2) })
  }, [actions, modelsControl])

  useEffect(() => {
    if (!wiringText) return
    const sig = `${wiringText}@@${wiringLayoutText ?? ''}@@${modulePortsText ?? ''}`
    if (sig === lastHydrateSigRef.current) return
    lastHydrateSigRef.current = sig

    try {
      const parsed = JSON.parse(wiringText)
      const wiring = normalizeWiring(parsed)
      setParseError(null)

      setNodes((prevNodes) => {
        const layoutValue = readFallbackLayout()
        const { nodes: nextNodes, edges: nextEdges, needsLayout } = wiringToFlow(
          wiring,
          Array.isArray(state.spec?.modules) ? state.spec!.modules.map(String) : [],
          portsByAlias,
          new Set<string>(layoutValue.hidden_modules || []),
          prevNodes
        )
        const withSaved = nextNodes.map((n) => {
          const p = (layoutValue.nodes || {})[n.id]
          if (!p) return n
          return { ...n, position: { x: p.x, y: p.y } }
        })
        setEdges(nextEdges)
        const shouldLayout = needsLayout && Object.keys(layoutValue.nodes || {}).length === 0
        const finalNodes = shouldLayout ? layoutFlow(withSaved, nextEdges) : withSaved
        if (shouldLayout) {
          const positions: PositionMap = {}
          for (const n of finalNodes) positions[n.id] = { x: n.position.x, y: n.position.y }
          updateLayout({ ...layoutValue, nodes: positions, hidden_modules: layoutValue.hidden_modules || [], version: 1 })
        }
        return finalNodes
      })
      if (!showRaw) setRawDraft(wiringText)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setParseError(message)
      setRawDraft(wiringText)
    }
  }, [modulePortsText, portsByAlias, readFallbackLayout, showRaw, state.spec, updateLayout, wiringLayoutText, wiringText])

  const updateControlsFromEdges = useCallback((nextEdges: Edge[]) => {
    const wiring = edgesToWiring(nextEdges)
    const nextText = JSON.stringify(wiring, null, 2)
    lastAppliedRef.current = nextText
    actions.setControls({ wiring: nextText })
    setRawDraft(nextText)
    setParseError(null)
    try {
      localStorage.setItem(storageKey, JSON.stringify({ wiring: nextText, updatedAt: Date.now() } satisfies StoredWiring))
    } catch {
      // ignore
    }
  }, [actions, storageKey])

  const ensurePort = useCallback((nodeId: string, dir: 'input' | 'output', port: string) => {
    setNodes((prev) => prev.map((n) => {
      if (n.id !== nodeId) return n
      const data = n.data as WiringNodeData
      const key = dir === 'input' ? 'inputs' : 'outputs'
      const list = data[key]
      if (list.includes(port)) return n
      const next = { ...data, [key]: [...list, port].sort() } as WiringNodeData
      return { ...n, data: next }
    }))

    if (!modulePortsControl) return
    try {
      const parsed = modulePortsText ? JSON.parse(modulePortsText) : {}
      const base = parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
      const existing = (base as any)[nodeId]
      const nextEntry =
        existing && typeof existing === 'object' && !Array.isArray(existing) ? { ...existing } : {}
      const field = dir === 'input' ? 'inputs' : 'outputs'
      const nextList = Array.isArray((nextEntry as any)[field]) ? (nextEntry as any)[field].map(String) : []
      if (!nextList.includes(port)) nextList.push(port)
      nextList.sort((a: string, b: string) => a.localeCompare(b))
      ;(nextEntry as any)[field] = nextList
      ;(base as any)[nodeId] = nextEntry
      actions.setControls({ module_ports: JSON.stringify(base, null, 2) })
    } catch {
      // ignore
    }
  }, [actions, modulePortsControl, modulePortsText])

  const onNodesChange = useCallback((changes: NodeChange<WiringFlowNode>[]) => {
    setNodes((prev) => {
      const next = applyNodeChanges<WiringFlowNode>(changes, prev)
      const moved = changes.some((c) => c.type === 'position' || c.type === 'dimensions')
      if (moved) {
        const pos: PositionMap = {}
        for (const n of next) pos[n.id] = { x: n.position.x, y: n.position.y }
        const layoutValue = readFallbackLayout()
        updateLayout({ ...layoutValue, nodes: { ...(layoutValue.nodes || {}), ...pos }, hidden_modules: layoutValue.hidden_modules || [], version: 1 })
      }
      return next
    })
  }, [readFallbackLayout, updateLayout])

  const onEdgesChange = useCallback((changes: EdgeChange[]) => {
    const shouldUpdate = changes.some((c) => c.type === 'remove' || c.type === 'add')
    setEdges((prev) => {
      const next = applyEdgeChanges(changes, prev)
      if (shouldUpdate) updateControlsFromEdges(next)
      return next
    })
  }, [updateControlsFromEdges])

  const applyPendingConnect = useCallback(() => {
    if (!pendingConnect) return
    const sourcePort = pendingConnect.sourcePort.trim()
    const targetPort = pendingConnect.targetPort.trim()
    if (sourcePort.includes('.') || targetPort.includes('.')) {
      setParseError('Port names must not include "."')
      return
    }
    if (!sourcePort || !targetPort) return
    ensurePort(pendingConnect.source, 'output', sourcePort)
    ensurePort(pendingConnect.target, 'input', targetPort)
    setEdges((prev) => {
      const next = addEdge(
        {
          id: `e-${Date.now()}`,
          source: pendingConnect.source,
          sourceHandle: sourcePort,
          target: pendingConnect.target,
          targetHandle: targetPort,
          type: 'smoothstep',
          style: { stroke: '#6b7280', strokeWidth: 2 },
        } as Edge,
        prev
      )
      updateControlsFromEdges(next)
      return next
    })
    setPendingConnect(null)
  }, [ensurePort, pendingConnect, updateControlsFromEdges])

  const onConnect = useCallback((conn: Connection) => {
    if (editingDisabled) return
    if (!conn.source || !conn.target) return
    let sourceHandle = conn.sourceHandle
    let targetHandle = conn.targetHandle

    if (!sourceHandle || !targetHandle) return

    if (sourceHandle === NEW_HANDLE_ID) {
      setPendingConnect({
        source: conn.source,
        target: conn.target,
        sourceHandle,
        targetHandle,
        sourcePort: '',
        targetPort: targetHandle === NEW_HANDLE_ID ? '' : String(targetHandle),
        mode: targetHandle === NEW_HANDLE_ID ? 'both' : 'from',
      })
      return
    }

    if (targetHandle === NEW_HANDLE_ID) {
      setPendingConnect({
        source: conn.source,
        target: conn.target,
        sourceHandle,
        targetHandle,
        sourcePort: String(sourceHandle),
        targetPort: '',
        mode: 'to',
      })
      return
    }

    setEdges((prev) => {
      const next = addEdge(
        {
          ...conn,
          sourceHandle,
          targetHandle,
          id: `e-${Date.now()}`,
          type: 'smoothstep',
          style: { stroke: '#6b7280', strokeWidth: 2 },
        } as Edge,
        prev
      )
      updateControlsFromEdges(next)
      return next
    })
  }, [editingDisabled, ensurePort, updateControlsFromEdges])

  const applyRawJson = useCallback(() => {
    try {
      const parsed = JSON.parse(rawDraft)
      const nextText = JSON.stringify(edgesToWiring(wiringToEdges(parsed)), null, 2)
      lastAppliedRef.current = nextText
      actions.setControls({ wiring: nextText })
      setParseError(null)
      setShowRaw(false)
      try {
        localStorage.setItem(storageKey, JSON.stringify({ wiring: nextText, updatedAt: Date.now() } satisfies StoredWiring))
      } catch {
        // ignore
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setParseError(message)
      setIsExpanded(true)
      setShowRaw(true)
    }
  }, [actions, rawDraft, storageKey])

  const autoLayout = useCallback(() => {
    setNodes((prev) => {
      const layouted = layoutFlow(prev, edges)
      const pos: PositionMap = {}
      for (const n of layouted) pos[n.id] = { x: n.position.x, y: n.position.y }
      const layoutValue = readFallbackLayout()
      updateLayout({ ...layoutValue, nodes: { ...(layoutValue.nodes || {}), ...pos }, hidden_modules: layoutValue.hidden_modules || [], version: 1 })
      return layouted
    })
  }, [edges, readFallbackLayout, updateLayout])

  const resetLayout = useCallback(() => {
    const layoutValue = readFallbackLayout()
    updateLayout({ ...layoutValue, nodes: {}, hidden_modules: layoutValue.hidden_modules || [], version: 1 })
    setNodes((prev) => prev.map((n) => ({ ...n, position: { x: 0, y: 0 } })))
  }, [readFallbackLayout, updateLayout])

  const visibleEdges = useMemo(
    () => edges.filter((e) => !hiddenModules.has(e.source) && !hiddenModules.has(e.target)),
    [edges, hiddenModules]
  )

  const moduleCount = nodes.length
  const connectionCount = visibleEdges.length
  const allModuleIds = useMemo(() => {
    const ids = new Set<string>()
    for (const m of Array.isArray(state.spec?.modules) ? state.spec!.modules : []) ids.add(String(m))
    for (const m of Object.keys(portsByAlias || {})) ids.add(String(m))
    for (const n of nodes) ids.add(String(n.id))
    return Array.from(ids).sort((a, b) => a.localeCompare(b))
  }, [nodes, portsByAlias, state.spec])

  const toggleHidden = useCallback((moduleId: string) => {
    const layoutValue = readFallbackLayout()
    const hidden = new Set<string>(layoutValue.hidden_modules || [])
    if (hidden.has(moduleId)) hidden.delete(moduleId)
    else hidden.add(moduleId)
    updateLayout({ ...layoutValue, hidden_modules: Array.from(hidden).sort(), version: 1, nodes: layoutValue.nodes || {} })
  }, [readFallbackLayout, updateLayout])

  const toggleCompositionModule = useCallback((alias: string) => {
    if (!modelsControl) return
    const baseline = baselineModelsByAliasRef.current
    if (!baseline) return
    const layoutValue = readFallbackLayout()
    const hidden = new Set<string>(layoutValue.hidden_modules || [])

    const existing = currentModelsByAlias.get(alias)
    if (existing) {
      const remaining = Array.from(currentModelsByAlias.entries())
        .filter(([k]) => k !== alias)
        .map(([, v]) => v)
      setModelsText(remaining)
      hidden.add(alias)
      updateLayout({ ...layoutValue, hidden_modules: Array.from(hidden).sort(), nodes: layoutValue.nodes || {}, version: 1 })
      setEdges((prev) => {
        const nextEdges = prev.filter((e) => e.source !== alias && e.target !== alias)
        updateControlsFromEdges(nextEdges)
        return nextEdges
      })
      return
    }

    const template = baseline.get(alias)
    if (!template) return
    const nextModels = [...Array.from(currentModelsByAlias.values()), template]
    setModelsText(nextModels)
    hidden.delete(alias)
    updateLayout({ ...layoutValue, hidden_modules: Array.from(hidden).sort(), nodes: layoutValue.nodes || {}, version: 1 })
  }, [currentModelsByAlias, modelsControl, readFallbackLayout, setModelsText, updateControlsFromEdges, updateLayout])

  if (!wiringControl) return null

  return (
    <div className={`wiring-panel ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="wiring-header" onClick={() => setIsExpanded((v) => !v)}>
        <div className="wiring-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M9 18h6" />
            <path d="M10 22h4" />
            <path d="M12 2v10" />
            <path d="M5 12h14" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          <span>Wiring</span>
          <span className="wiring-meta">{moduleCount} modules · {connectionCount} connections</span>
          {hiddenModules.size > 0 && <span className="wiring-meta">{hiddenModules.size} hidden</span>}
          {editingDisabled && <span className="wiring-locked">locked while running</span>}
        </div>
        <div className="wiring-actions">
          <button
            className="expand-btn"
            onClick={(e) => { e.stopPropagation(); setIsExpanded((v) => !v) }}
          >
            {isExpanded ? 'Collapse' : 'Expand'}
          </button>
        </div>
      </div>

      {parseError && (
        <div className="wiring-error">
          <span>Invalid wiring JSON: {parseError}</span>
          <button className="btn btn-small btn-outline" onClick={() => { setIsExpanded(true); setShowRaw(true) }}>
            Edit JSON
          </button>
        </div>
      )}

      {isExpanded && (
        <div className="wiring-body">
          <div className="wiring-canvas">
            <ReactFlow
              nodes={nodes}
              edges={visibleEdges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              nodeTypes={nodeTypes}
              fitView
              snapToGrid
              snapGrid={[15, 15]}
              nodesDraggable={!editingDisabled}
              nodesConnectable={!editingDisabled}
              elementsSelectable={!editingDisabled}
              deleteKeyCode={editingDisabled ? null : ['Backspace', 'Delete']}
              style={{ background: 'var(--bg)' }}
            >
              <Background gap={20} size={1} color="var(--border)" />
              <Controls style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 6 }} />
            </ReactFlow>
          </div>

          <div className="wiring-advanced">
            <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <button className="btn btn-small btn-outline" onClick={autoLayout}>Auto layout</button>
                <button className="btn btn-small btn-outline" onClick={resetLayout}>Reset layout</button>
              </div>
              <button className="btn btn-small btn-outline" onClick={() => setShowRaw((v) => !v)}>
                {showRaw ? 'Hide JSON' : 'Show JSON'}
              </button>
            </div>

            {allModuleIds.length > 0 && (
              <div className="wiring-palette">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>Modules</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>diagram only</div>
                </div>
                <div className="wiring-palette-list">
                  {allModuleIds.map((id) => {
                    const hidden = hiddenModules.has(id)
                    return (
                      <label key={id} className="wiring-palette-item">
                        <input
                          type="checkbox"
                          checked={!hidden}
                          onChange={() => toggleHidden(id)}
                          disabled={editingDisabled}
                        />
                        <span style={{ color: hidden ? 'var(--muted)' : 'var(--text)' }}>{id}</span>
                      </label>
                    )
                  })}
                </div>
              </div>
            )}

            {compositionAliases && compositionAliases.length > 0 && (
              <div className="wiring-palette">
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                  <div style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>Run Composition</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>affects run</div>
                </div>
                <div className="wiring-palette-list">
                  {compositionAliases.map((alias) => {
                    const included = currentModelsByAlias.has(alias)
                    return (
                      <label key={alias} className="wiring-palette-item">
                        <input
                          type="checkbox"
                          checked={included}
                          onChange={() => toggleCompositionModule(alias)}
                          disabled={editingDisabled}
                        />
                        <span style={{ color: included ? 'var(--text)' : 'var(--muted)' }}>{alias}</span>
                      </label>
                    )
                  })}
                </div>
              </div>
            )}

            {showRaw && (
              <div className="wiring-json">
                <textarea
                  className="control-input"
                  value={rawDraft}
                  onChange={(e) => setRawDraft(e.target.value)}
                  rows={10}
                  disabled={editingDisabled}
                />
                <div className="wiring-json-actions">
                  <button className="btn btn-small btn-primary" onClick={applyRawJson} disabled={editingDisabled}>
                    Apply
                  </button>
                  <button className="btn btn-small btn-outline" onClick={() => { setRawDraft(wiringText ?? '[]'); setParseError(null) }}>
                    Reset
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {pendingConnect && (
        <div
          className="wiring-modal-backdrop"
          onClick={() => setPendingConnect(null)}
          role="presentation"
        >
          <div className="wiring-modal" onClick={(e) => e.stopPropagation()}>
            <div className="wiring-modal-title">Add connection</div>
            <div className="wiring-modal-subtitle">
              {pendingConnect.source} → {pendingConnect.target}
            </div>
            <div className="wiring-modal-grid">
              <label className="wiring-modal-field">
                <span>From (output port)</span>
                <input
                  className="control-input"
                  value={pendingConnect.sourcePort}
                  onChange={(e) => setPendingConnect((prev) => prev ? { ...prev, sourcePort: e.target.value } : prev)}
                  placeholder="e.g. population_state"
                  disabled={editingDisabled || pendingConnect.mode === 'to'}
                  list={`wiring-ports-out-${pendingConnect.source}`}
                />
              </label>
              <label className="wiring-modal-field">
                <span>To (input port)</span>
                <input
                  className="control-input"
                  value={pendingConnect.targetPort}
                  onChange={(e) => setPendingConnect((prev) => prev ? { ...prev, targetPort: e.target.value } : prev)}
                  placeholder="e.g. prey_state"
                  disabled={editingDisabled || pendingConnect.mode === 'from'}
                  list={`wiring-ports-in-${pendingConnect.target}`}
                />
              </label>
            </div>
            {/* Suggestions */}
            <datalist id={`wiring-ports-out-${pendingConnect.source}`}>
              {(nodes.find((n) => n.id === pendingConnect.source)?.data.outputs ?? []).map((port) => (
                <option key={String(port)} value={String(port)} />
              ))}
            </datalist>
            <datalist id={`wiring-ports-in-${pendingConnect.target}`}>
              {(nodes.find((n) => n.id === pendingConnect.target)?.data.inputs ?? []).map((port) => (
                <option key={String(port)} value={String(port)} />
              ))}
            </datalist>
            <div className="wiring-modal-actions">
              <button className="btn btn-outline" onClick={() => setPendingConnect(null)}>Cancel</button>
              <button className="btn btn-primary" onClick={applyPendingConnect} disabled={editingDisabled}>
                Add
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
