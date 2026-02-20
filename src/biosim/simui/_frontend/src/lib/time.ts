export function formatDuration(seconds: number): string {
  if (!Number.isFinite(seconds)) return '—'
  const sign = seconds < 0 ? '-' : ''
  const abs = Math.abs(seconds)

  if (abs < 1e-9) return '0 s'
  if (abs < 1) {
    const ms = abs * 1000
    const decimals = ms < 1 ? 2 : ms < 10 ? 1 : 0
    return `${sign}${ms.toFixed(decimals)} ms`
  }
  if (abs < 60) {
    const decimals = abs < 10 ? 2 : abs < 30 ? 1 : 0
    return `${sign}${abs.toFixed(decimals)} s`
  }
  if (abs < 3600) {
    const m = Math.floor(abs / 60)
    const s = Math.round(abs - m * 60)
    return `${sign}${m}m ${s}s`
  }
  const h = Math.floor(abs / 3600)
  const m = Math.floor((abs - h * 3600) / 60)
  const s = Math.round(abs - h * 3600 - m * 60)
  return `${sign}${h}h ${m}m ${s}s`
}

export function formatDurationTick(seconds: number, rangeSeconds: number): string {
  if (!Number.isFinite(seconds) || !Number.isFinite(rangeSeconds)) return '—'
  const absRange = Math.abs(rangeSeconds)
  const abs = Math.abs(seconds)
  const sign = seconds < 0 ? '-' : ''

  if (absRange < 1) {
    const ms = abs * 1000
    const rangeMs = absRange * 1000
    const decimals = rangeMs < 1 ? 2 : rangeMs < 10 ? 1 : 0
    return `${sign}${ms.toFixed(decimals)}ms`
  }
  if (absRange < 60) {
    const decimals = absRange < 10 ? 2 : absRange < 30 ? 1 : 0
    return `${sign}${abs.toFixed(decimals)}s`
  }
  if (absRange < 3600) {
    const m = Math.floor(abs / 60)
    const s = Math.round(abs - m * 60)
    return `${sign}${m}:${String(s).padStart(2, '0')}`
  }
  const h = Math.floor(abs / 3600)
  const m = Math.floor((abs - h * 3600) / 60)
  const s = Math.round(abs - h * 3600 - m * 60)
  return `${sign}${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

export function looksLikeDurationAxis(series: Array<{ points?: Array<[number, number]> }>): boolean {
  let checked = 0
  let increasing = 0
  for (const s of series || []) {
    const pts = s.points || []
    // Only sample a small number of segments for speed
    for (let i = 1; i < pts.length && checked < 200; i++) {
      const prev = Number(pts[i - 1]?.[0])
      const cur = Number(pts[i]?.[0])
      if (!Number.isFinite(prev) || !Number.isFinite(cur)) continue
      checked += 1
      if (cur >= prev) increasing += 1
    }
  }
  // If almost all sampled segments are non-decreasing, it's probably time.
  return checked >= 5 && increasing / checked >= 0.95
}
