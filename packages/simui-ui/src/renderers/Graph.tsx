import React, { useMemo } from 'react'

type Edge = { source: string; target: string }
type Node = { id: string }

// Lightweight SVG circular layout. For small graphs this is clearer and safer than pulling a heavy lib.
export default function Graph({ data, isFullscreen }: { data: { nodes?: Node[]; edges?: Edge[] }; isFullscreen?: boolean }) {
  const nodes = data.nodes || []
  const edges = data.edges || []
  const W = 520, H = 300, R = 110, CX = W / 2, CY = H / 2
  const positions = useMemo(() => {
    const n = Math.max(1, nodes.length)
    const map = new Map<string, { x: number; y: number }>()
    nodes.forEach((node, i) => {
      const a = (2 * Math.PI * i) / n
      map.set(node.id, { x: CX + R * Math.cos(a), y: CY + R * Math.sin(a) })
    })
    return map
  }, [JSON.stringify(nodes)])

  const containerStyle: React.CSSProperties = isFullscreen
    ? { width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }
    : {}

  return (
    <div style={containerStyle}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={isFullscreen ? '100%' : H} preserveAspectRatio={isFullscreen ? 'xMidYMid meet' : undefined}>
        {/* Edges */}
        {edges.map((e, i) => {
          const s = positions.get(e.source)
          const t = positions.get(e.target)
          if (!s || !t) return null
          return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="#64748b" strokeWidth={1} />
        })}
        {/* Nodes */}
        {nodes.map((n, i) => {
          const p = positions.get(n.id)
          if (!p) return null
          return (
            <g key={n.id}>
              <circle cx={p.x} cy={p.y} r={14} fill="#22d3ee" />
              <text x={p.x} y={p.y + 4} fontSize={10} textAnchor="middle" fill="#0f172a">{n.id}</text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}
