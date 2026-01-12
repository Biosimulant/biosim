import React, { useMemo } from 'react'

type Item = { label: string; value: number }

export default function Bar({ data }: { data: { items?: Item[] } }) {
  const W = 520, H = 240
  const ML = 40, MR = 10, MT = 10, MB = 24
  const items = data?.items || []
  const yMax = useMemo(() => Math.max(1, ...items.map((it) => Number(it?.value || 0))), [JSON.stringify(items)])
  const sx = (i: number, n: number) => ML + ((i + 0.5) * (W - ML - MR)) / Math.max(1, n)
  const bw = (n: number) => Math.max(8, (0.8 * (W - ML - MR)) / Math.max(1, n))
  const sy = (v: number) => MT + (1 - Math.min(1, Math.max(0, v / yMax))) * (H - MT - MB)
  const yTicks = (count = 4) => Array.from({ length: count + 1 }, (_, i) => (i * yMax) / count)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H}>
      <line x1={ML} y1={H - MB} x2={W - MR} y2={H - MB} className="axis" />
      <line x1={ML} y1={MT} x2={ML} y2={H - MB} className="axis" />
      {yTicks(4).map((ty) => (
        <g key={`ty-${ty}`}>
          <line x1={ML - 4} y1={sy(ty)} x2={ML} y2={sy(ty)} className="tick" />
          <text x={ML - 6} y={sy(ty) + 3} className="ticklbl" textAnchor="end">{ty.toFixed(0)}</text>
        </g>
      ))}
      {items.map((it, i) => (
        <g key={i}>
          <rect x={sx(i, items.length) - bw(items.length) / 2} y={sy(it.value)} width={bw(items.length)} height={H - MB - sy(it.value)} className="bar" />
          <text x={sx(i, items.length)} y={H - 6} className="xlbl" textAnchor="middle">{it.label}</text>
        </g>
      ))}
    </svg>
  )
}
