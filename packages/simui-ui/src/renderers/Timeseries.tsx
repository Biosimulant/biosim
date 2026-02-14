import React, { useMemo } from 'react'

type Series = { name?: string; points: Array<[number, number]> }

export default function Timeseries({ data, isFullscreen }: { data: { series?: Series[] }; isFullscreen?: boolean }) {
  const W = 520, H = 240
  const ML = 50, MR = 20, MT = 20, MB = 40
  const series = data?.series || []

  const { xMin, xMax, yMin, yMax } = useMemo(() => {
    let xMin = 0
    let xMax = 1
    let yMin = 0
    let yMax = 1

    for (const s of series) {
      const points = Array.isArray(s?.points) ? s.points : []
      for (const p of points) {
        const x = Number(p?.[0]) || 0
        const y = Number(p?.[1]) || 0
        if (x < xMin) xMin = x
        if (x > xMax) xMax = x
        if (y < yMin) yMin = y
        if (y > yMax) yMax = y
      }
    }

    return {
      xMin,
      xMax: xMax <= xMin ? xMin + 1 : xMax,
      yMin,
      yMax: yMax <= yMin ? yMin + 1 : yMax,
    }
  }, [series])

  const sx = (x: number) => ML + ((x - xMin) / (xMax - xMin)) * (W - ML - MR)
  const sy = (y: number) => MT + (1 - (y - yMin) / (yMax - yMin)) * (H - MT - MB)
  const poly = (s: Series) => (s.points || []).map((p) => `${sx(p[0])},${sy(p[1])}`).join(' ')
  const ticks = (lo: number, hi: number, count = 5) => Array.from({ length: count + 1 }, (_, i) => lo + (i * (hi - lo)) / count)

  const containerStyle: React.CSSProperties = isFullscreen
    ? { width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }
    : {}

  return (
    <div style={containerStyle} className={isFullscreen ? 'fullscreen-renderer' : ''}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={isFullscreen ? '100%' : H} preserveAspectRatio={isFullscreen ? 'xMidYMid meet' : undefined}>
        <line x1={ML} y1={H - MB} x2={W - MR} y2={H - MB} className="axis" />
        <line x1={ML} y1={MT} x2={ML} y2={H - MB} className="axis" />
        {ticks(xMin, xMax, 5).map((tx) => (
          <g key={`tx-${tx}`}>
            <line x1={sx(tx)} y1={H - MB} x2={sx(tx)} y2={H - MB + 4} className="tick" />
            <text x={sx(tx)} y={H - 6} className="ticklbl" textAnchor="middle">{tx.toFixed(2)}</text>
          </g>
        ))}
        {ticks(yMin, yMax, 4).map((ty) => (
          <g key={`ty-${ty}`}>
            <line x1={ML - 4} y1={sy(ty)} x2={ML} y2={sy(ty)} className="tick" />
            <text x={ML - 6} y={sy(ty) + 3} className="ticklbl" textAnchor="end">{ty.toFixed(2)}</text>
          </g>
        ))}
        {series.map((s, si) => (
          <polyline key={si} points={poly(s)} fill="none" stroke={si === 0 ? '#2563eb' : si === 1 ? '#dc2626' : '#10b981'} strokeWidth={2} />
        ))}
      </svg>
    </div>
  )
}
