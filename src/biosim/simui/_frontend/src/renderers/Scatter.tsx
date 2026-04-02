import React, { useMemo } from 'react'

type ScatterPoint = { x: number; y: number; label?: string; series?: string }

function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export default function Scatter({ data, isFullscreen }: { data: { points?: ScatterPoint[] }; isFullscreen?: boolean }) {
  const W = 560, H = 280
  const ML = 56, MR = 20, MT = 20, MB = 40
  const points = useMemo(
    () => (Array.isArray(data?.points) ? data.points : []).map((point) => ({
      x: toFiniteNumber(point?.x),
      y: toFiniteNumber(point?.y),
      label: typeof point?.label === 'string' ? point.label : undefined,
      series: typeof point?.series === 'string' ? point.series : undefined,
    })),
    [JSON.stringify(data?.points || [])]
  )

  if (points.length === 0) return <div className="empty">No scatter data</div>

  let xMin = points[0]!.x, xMax = points[0]!.x, yMin = points[0]!.y, yMax = points[0]!.y
  for (const point of points) {
    if (point.x < xMin) xMin = point.x
    if (point.x > xMax) xMax = point.x
    if (point.y < yMin) yMin = point.y
    if (point.y > yMax) yMax = point.y
  }
  if (xMax <= xMin) xMax = xMin + 1
  if (yMax <= yMin) yMax = yMin + 1

  const sx = (value: number) => ML + ((value - xMin) / (xMax - xMin)) * (W - ML - MR)
  const sy = (value: number) => MT + (1 - (value - yMin) / (yMax - yMin)) * (H - MT - MB)
  const ticks = (min: number, max: number, count = 4) => Array.from({ length: count + 1 }, (_, i) => min + ((max - min) * i) / count)

  const seriesNames = Array.from(new Set(points.map((point) => point.series).filter(Boolean))) as string[]
  const colorBySeries = new Map<string, string>()
  const palette = ['#4f46e5', '#059669', '#ea580c', '#dc2626', '#0ea5e9', '#a855f7']
  seriesNames.forEach((name, index) => colorBySeries.set(name, palette[index % palette.length]!))

  const colorForPoint = (point: ScatterPoint) => point.series ? colorBySeries.get(point.series) || palette[0]! : palette[0]!

  const containerStyle: React.CSSProperties = isFullscreen
    ? { width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center' }
    : {}

  return (
    <div style={containerStyle}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={isFullscreen ? '100%' : H} preserveAspectRatio={isFullscreen ? 'xMidYMid meet' : undefined}>
        <line x1={ML} y1={H - MB} x2={W - MR} y2={H - MB} className="axis" />
        <line x1={ML} y1={MT} x2={ML} y2={H - MB} className="axis" />
        {ticks(xMin, xMax).map((tick) => (
          <g key={`x-${tick}`}>
            <line x1={sx(tick)} y1={H - MB} x2={sx(tick)} y2={H - MB + 4} className="tick" />
            <text x={sx(tick)} y={H - 8} className="ticklbl" textAnchor="middle">{tick.toFixed(2)}</text>
          </g>
        ))}
        {ticks(yMin, yMax).map((tick) => (
          <g key={`y-${tick}`}>
            <line x1={ML - 4} y1={sy(tick)} x2={ML} y2={sy(tick)} className="tick" />
            <text x={ML - 8} y={sy(tick) + 3} className="ticklbl" textAnchor="end">{tick.toFixed(2)}</text>
          </g>
        ))}
        {points.map((point, index) => (
          <g key={`${point.label || 'point'}-${index}`}>
            <circle cx={sx(point.x)} cy={sy(point.y)} r={4} fill={colorForPoint(point)} opacity={0.85}>
              {point.label ? <title>{`${point.label}: (${point.x.toFixed(3)}, ${point.y.toFixed(3)})`}</title> : null}
            </circle>
          </g>
        ))}
      </svg>
      {seriesNames.length > 0 ? (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          {seriesNames.map((series) => (
            <div key={series} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
              <span style={{ width: 10, height: 10, borderRadius: 999, background: colorBySeries.get(series) }} />
              <span>{series}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}
