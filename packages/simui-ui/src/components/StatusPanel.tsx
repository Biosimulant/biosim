import React, { useCallback, useMemo, useState } from 'react'
import { useUi, isNumberControl } from '../app/ui'
import { formatDuration } from '../lib/time'
import { resolveRunProgress } from '../lib/progress'

function toFiniteNumber(value: unknown): number {
  if (value === '' || value === null || value === undefined) return Number.NaN
  const n = typeof value === 'number' ? value : Number(String(value))
  return Number.isFinite(n) ? n : Number.NaN
}

function StatusDisplay() {
  const { state } = useUi()
  const st = state.status
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const controlDefault = (name: string): number | undefined => numberControls.find((c) => c.name === name)?.default
  const duration = toFiniteNumber(state.controls.duration ?? controlDefault('duration'))
  const progress = resolveRunProgress({ status: st, duration })
  const progressDisplay = progress.progressPct !== null && (
    <div className="sim-progress-row" title="Simulation-time progress">
      <span className="sim-progress-label">{progress.progressLabel}</span>
      <div className="sim-progress-track" aria-hidden="true">
        <div className="sim-progress-fill" style={{ width: `${progress.progressPct}%` }} />
      </div>
    </div>
  )

  if (!st) return <div className="status-display"><div className="status-badge status-unknown">Unknown</div></div>
  if (st.error) return (
    <div className="status-display">
      <div className="status-badge status-error">Error</div>
      <div className="status-message error">{st.error.message}</div>
      {progressDisplay}
    </div>
  )
  if (st.running) return (
    <div className="status-display">
      <div className={`status-badge ${st.paused ? 'status-paused' : 'status-running'}`}>{st.paused ? 'Paused' : 'Running'}</div>
      <div className="status-info">Steps: {st.step_count?.toLocaleString() || 0}</div>
      {progressDisplay}
    </div>
  )
  if (progressDisplay) return (
    <div className="status-display">
      <div className="status-badge status-idle">Idle</div>
      <div className="status-info">Last run</div>
      {progressDisplay}
    </div>
  )
  return <div className="status-display"><div className="status-badge status-idle">Idle</div></div>
}

export function useStatusSummary(): string {
  const { state } = useUi()
  return useMemo(() => {
    const st = state.status
    if (!st) return 'Unknown'
    const numberControls = (state.spec?.controls || []).filter(isNumberControl)
    const controlDefault = (name: string): number | undefined => numberControls.find((c) => c.name === name)?.default
    const duration = toFiniteNumber(state.controls.duration ?? controlDefault('duration'))
    const progress = resolveRunProgress({ status: st, duration })
    if (st.error) return progress.progressPct !== null ? `Error · ${progress.progressLabel}` : 'Error'
    if (st.running) {
      return progress.progressPct !== null
        ? `${st.paused ? 'Paused' : 'Running'} · ${progress.progressLabel}`
        : `${st.paused ? 'Paused' : 'Running'} · Steps: ${st.step_count?.toLocaleString() || 0}`
    }
    if (progress.progressPct !== null) return `Idle · Last run: ${progress.progressLabel}`
    return 'Idle'
  }, [state.controls.duration, state.spec?.controls, state.status])
}

export default function StatusPanel() {
  const [open, setOpen] = useState(false)
  const summary = useStatusSummary()

  return (
    <section className={`sidebar-panel ${open ? 'is-open' : 'is-closed'}`} style={{ margin: '12px' }}>
      <button
        type="button"
        className="sidebar-panel-header"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className={`sidebar-panel-chevron ${open ? 'open' : ''}`} aria-hidden="true">
          ▸
        </span>
        <span className="sidebar-panel-title">Status</span>
        {summary && <span className="sidebar-panel-summary">{summary}</span>}
      </button>
      {open && <div className="sidebar-panel-body"><StatusDisplay /></div>}
    </section>
  )
}
