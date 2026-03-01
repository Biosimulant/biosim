import React from 'react'
import { useUi, isNumberControl } from '../app/ui'
import { formatDuration } from '../lib/time'

type Props = {
  connected: boolean
  runPending: boolean
  onRun: () => void
  onPause: () => void
  onResume: () => void
  onReset: () => void
  onToggleControls: () => void
  onToggleEditor?: () => void
  headerLeft?: React.ReactNode
  headerRight?: React.ReactNode
}

export default function Toolbar({
  connected,
  runPending,
  onRun,
  onPause,
  onResume,
  onReset,
  onToggleControls,
  onToggleEditor,
  headerLeft,
  headerRight,
}: Props) {
  const { state, actions } = useUi()
  const st = state.status
  const capabilities = state.spec?.capabilities
  const controlsEnabled = capabilities?.controls ?? true
  const runEnabled = controlsEnabled && (capabilities?.run ?? true)
  const showRunWhenDisabled = capabilities?.showRunWhenDisabled ?? false
  const showRunButton = runEnabled || showRunWhenDisabled
  const runDisabledReason = capabilities?.runDisabledReason || 'Run is disabled for this space.'
  const runButtonDisabled = !runEnabled || !!st?.running || !!runPending
  const runButtonTitle = !runEnabled ? runDisabledReason : undefined
  const pauseResumeEnabled = controlsEnabled && (capabilities?.pauseResume ?? true)
  const resetEnabled = controlsEnabled && (capabilities?.reset ?? true)

  const controls = Array.isArray(state.spec?.controls) ? state.spec!.controls! : []
  const durationControl = controls.find((c) => isNumberControl(c) && c.name === 'duration')
  const durationDefault = durationControl && isNumberControl(durationControl) ? durationControl.default : undefined
  const durationRaw = state.controls.duration ?? durationDefault
  const duration = typeof durationRaw === 'number' ? durationRaw : Number(String(durationRaw))
  const durationValid = Number.isFinite(duration)

  const tickDtRaw = state.controls.tick_dt
  const tickDt = typeof tickDtRaw === 'number' ? tickDtRaw : Number(String(tickDtRaw))
  const simTime = (st?.tick_count ?? 0) * tickDt

  const statusLabel = (() => {
    if (!st) return 'Idle'
    if (st.error) return 'Error'
    if (st.running && st.paused) return 'Paused'
    if (st.running) return 'Running'
    return 'Idle'
  })()

  const statusClass = (() => {
    if (!st) return 'toolbar-status--idle'
    if (st.error) return 'toolbar-status--error'
    if (st.running && st.paused) return 'toolbar-status--paused'
    if (st.running) return 'toolbar-status--running'
    return 'toolbar-status--idle'
  })()

  return (
    <div className="toolbar">
      {/* Left zone */}
      <div className="toolbar-left">
        {headerLeft}
        <div className="toolbar-sse">
          {connected && <div className="sse-indicator" title="Stream Connected" />}
        </div>
        <h1 className="toolbar-title">{state.spec?.title || 'BioSim UI'}</h1>
        <span className={`toolbar-status ${statusClass}`}>{statusLabel}</span>
        {st?.running && Number.isFinite(simTime) && (
          <span className="toolbar-sim-time" title="Simulation time">
            {st.tick_count?.toLocaleString()} ticks &middot; {formatDuration(simTime)}
          </span>
        )}
      </div>

      {/* Center zone — run controls */}
      <div className="toolbar-center">
        <label className="toolbar-duration">
          <span className="toolbar-duration-label">Duration</span>
          <input
            type="number"
            className="toolbar-duration-input"
            value={String(state.controls.duration ?? durationDefault ?? 10)}
            min={durationControl && isNumberControl(durationControl) ? durationControl.min : undefined}
            max={durationControl && isNumberControl(durationControl) ? durationControl.max : undefined}
            step={durationControl && isNumberControl(durationControl) ? durationControl.step ?? 'any' : 'any'}
            onChange={(e) => actions.setControls({ duration: e.target.value })}
            disabled={!!st?.running || !controlsEnabled}
          />
          {durationValid && <span className="toolbar-duration-fmt">{formatDuration(duration)}</span>}
        </label>

        {showRunButton && (
          <button
            className="toolbar-btn toolbar-btn--run"
            onClick={runEnabled ? onRun : undefined}
            disabled={runButtonDisabled}
            title={runButtonTitle}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
              <polygon points="5 3 19 12 5 21 5 3" />
            </svg>
            <span className="toolbar-btn-label">{runPending ? 'Starting…' : 'Run'}</span>
          </button>
        )}

        {pauseResumeEnabled && st?.running && (
          <button className="toolbar-btn toolbar-btn--secondary" onClick={st.paused ? onResume : onPause}>
            {st.paused ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                <span className="toolbar-btn-label">Resume</span>
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                  <rect x="6" y="4" width="4" height="16" />
                  <rect x="14" y="4" width="4" height="16" />
                </svg>
                <span className="toolbar-btn-label">Pause</span>
              </>
            )}
          </button>
        )}

        {resetEnabled && (
          <button className="toolbar-btn toolbar-btn--outline" onClick={onReset} title="Reset simulation">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="1 4 1 10 7 10" />
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
            </svg>
          </button>
        )}
      </div>

      {/* Right zone */}
      <div className="toolbar-right">
        {headerRight}
        <button
          className="toolbar-icon-btn"
          onClick={onToggleControls}
          title="Parameters"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="21" x2="4" y2="14" /><line x1="4" y1="10" x2="4" y2="3" />
            <line x1="12" y1="21" x2="12" y2="12" /><line x1="12" y1="8" x2="12" y2="3" />
            <line x1="20" y1="21" x2="20" y2="16" /><line x1="20" y1="12" x2="20" y2="3" />
            <line x1="1" y1="14" x2="7" y2="14" /><line x1="9" y1="8" x2="15" y2="8" />
            <line x1="17" y1="16" x2="23" y2="16" />
          </svg>
        </button>
        {onToggleEditor && (
          <button
            className="toolbar-icon-btn"
            onClick={onToggleEditor}
            title="Config Editor"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        )}
      </div>
    </div>
  )
}
