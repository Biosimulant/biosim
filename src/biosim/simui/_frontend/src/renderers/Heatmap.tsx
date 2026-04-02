import React, { useMemo } from 'react'

type HeatmapData = {
  values?: number[][]
  x_labels?: string[]
  y_labels?: string[]
}

function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

function colorForValue(value: number, min: number, max: number): string {
  const ratio = max <= min ? 0.5 : (value - min) / (max - min)
  const clamped = Math.max(0, Math.min(1, ratio))
  const hue = 220 - (220 * clamped)
  const lightness = 92 - (48 * clamped)
  return `hsl(${hue} 80% ${lightness}%)`
}

export default function Heatmap({ data, isFullscreen }: { data: HeatmapData; isFullscreen?: boolean }) {
  const values = useMemo(
    () => (Array.isArray(data?.values) ? data.values : []).map((row) => Array.isArray(row) ? row.map((value) => toFiniteNumber(value)) : []),
    [JSON.stringify(data?.values || [])]
  )
  const rows = values.length
  const cols = rows > 0 ? Math.max(...values.map((row) => row.length), 0) : 0

  if (rows === 0 || cols === 0) return <div className="empty">No heatmap data</div>

  let min = values[0]?.[0] ?? 0
  let max = min
  for (const row of values) {
    for (const value of row) {
      if (value < min) min = value
      if (value > max) max = value
    }
  }

  const W = Math.max(360, cols * 36 + 96)
  const H = Math.max(240, rows * 28 + 72)
  const ML = 72, MT = 24, MB = 36
  const cellW = (W - ML - 12) / cols
  const cellH = (H - MT - MB) / rows
  const xLabels = Array.isArray(data?.x_labels) ? data.x_labels : []
  const yLabels = Array.isArray(data?.y_labels) ? data.y_labels : []

  const containerStyle: React.CSSProperties = isFullscreen
    ? { width: '100%', height: '100%', overflow: 'auto' }
    : { overflow: 'auto' }

  return (
    <div style={containerStyle}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={isFullscreen ? '100%' : H} preserveAspectRatio={isFullscreen ? 'xMidYMid meet' : undefined}>
        {values.map((row, rowIndex) => (
          row.map((value, colIndex) => (
            <g key={`${rowIndex}-${colIndex}`}>
              <rect
                x={ML + colIndex * cellW}
                y={MT + rowIndex * cellH}
                width={cellW}
                height={cellH}
                rx={2}
                fill={colorForValue(value, min, max)}
              >
                <title>{`${yLabels[rowIndex] || `Row ${rowIndex + 1}`}, ${xLabels[colIndex] || `Col ${colIndex + 1}`}: ${value}`}</title>
              </rect>
              {cellW >= 24 && cellH >= 18 ? (
                <text
                  x={ML + colIndex * cellW + cellW / 2}
                  y={MT + rowIndex * cellH + cellH / 2 + 4}
                  textAnchor="middle"
                  style={{ fontSize: 10, fill: value > (min + max) / 2 ? '#fff' : '#111827' }}
                >
                  {value.toFixed(2)}
                </text>
              ) : null}
            </g>
          ))
        ))}
        {Array.from({ length: cols }, (_, colIndex) => (
          <text
            key={`x-label-${colIndex}`}
            x={ML + colIndex * cellW + cellW / 2}
            y={H - 12}
            textAnchor="middle"
            style={{ fontSize: 10, fill: 'var(--text-muted, #6b7280)' }}
          >
            {xLabels[colIndex] || String(colIndex + 1)}
          </text>
        ))}
        {Array.from({ length: rows }, (_, rowIndex) => (
          <text
            key={`y-label-${rowIndex}`}
            x={ML - 8}
            y={MT + rowIndex * cellH + cellH / 2 + 4}
            textAnchor="end"
            style={{ fontSize: 10, fill: 'var(--text-muted, #6b7280)' }}
          >
            {yLabels[rowIndex] || String(rowIndex + 1)}
          </text>
        ))}
      </svg>
    </div>
  )
}
