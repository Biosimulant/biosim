import React, { useCallback, useEffect } from 'react'
import { useUi, useModuleNames, isNumberControl } from '../app/ui'

type Props = { onRun: () => void; onPause: () => void; onResume: () => void; onReset: () => void }

function StatusDisplay() {
  const { state } = useUi()
  const st = state.status
  if (!st) return <div className="status-display"><div className="status-badge status-unknown">Unknown</div></div>
  if (st.error) return (
    <div className="status-display">
      <div className="status-badge status-error">Error</div>
      <div className="status-message error">{st.error.message}</div>
    </div>
  )
  if (st.running) return (
    <div className="status-display">
      <div className={`status-badge ${st.paused ? 'status-paused' : 'status-running'}`}>{st.paused ? 'Paused' : 'Running'}</div>
      <div className="status-info">Step: {st.step_count?.toLocaleString() || 0}</div>
    </div>
  )
  return <div className="status-display"><div className="status-badge status-idle">Idle</div></div>
}

function Controls({ onRun, onPause, onResume, onReset }: Props) {
  const { state, actions } = useUi()
  const st = state.status
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const updateControl = useCallback((name: string, value: string) => actions.setControls({ [name]: value }), [actions])
  return (
    <div className="controls">
      {numberControls.length > 0 && (
        <div className="control-fields">
          {numberControls.map((c) => (
            <div key={c.name} className="control-field">
              <label htmlFor={`control-${c.name}`} className="control-label">{c.label || c.name}</label>
              <input id={`control-${c.name}`} type="number" className="control-input" value={String(state.controls[c.name] ?? c.default)} min={c.min} max={c.max} step={c.step ?? 'any'} onChange={(e) => updateControl(c.name, e.target.value)} disabled={!!st?.running} />
            </div>
          ))}
        </div>
      )}
      <div className="control-actions">
        <button className="btn btn-primary" onClick={onRun} disabled={!!st?.running}>Run Simulation</button>
        {st?.running && (
          <button className="btn btn-secondary" onClick={st.paused ? onResume : onPause}>{st.paused ? 'Resume' : 'Pause'}</button>
        )}
        <button className="btn btn-outline" onClick={onReset}>Reset</button>
      </div>
    </div>
  )
}

function ModuleManager() {
  const { state, actions } = useUi()
  const moduleNames = useModuleNames()
  useEffect(() => {
    if (moduleNames.length > 0 && state.visibleModules.size === 0) actions.setVisibleModules(new Set(moduleNames))
  }, [moduleNames, state.visibleModules.size, actions])
  const toggle = useCallback((name: string) => {
    const next = new Set(state.visibleModules)
    next.has(name) ? next.delete(name) : next.add(name)
    actions.setVisibleModules(next)
  }, [state.visibleModules, actions])
  const showAll = useCallback(() => actions.setVisibleModules(new Set(moduleNames)), [moduleNames, actions])
  const hideAll = useCallback(() => actions.setVisibleModules(new Set()), [actions])
  if (moduleNames.length === 0) return <div className="modules"><div className="empty-state"><p>No modules available</p></div></div>
  return (
    <div className="modules">
      <div className="module-list">
        {moduleNames.map((m) => (
          <label key={m} className="module-item">
            <input type="checkbox" className="module-checkbox" checked={state.visibleModules.has(m)} onChange={() => toggle(m)} />
            <span className="module-name">{m}</span>
          </label>
        ))}
      </div>
      <div className="module-actions">
        <button className="btn btn-small" onClick={showAll}>Show All</button>
        <button className="btn btn-small" onClick={hideAll}>Hide All</button>
      </div>
    </div>
  )
}

export default function Sidebar(props: Props) {
  return (
    <div className="sidebar">
      <div className="sidebar-content">
        <section className="sidebar-section">
          <h2 className="section-title">Status</h2>
          <StatusDisplay />
        </section>
        <section className="sidebar-section">
          <h2 className="section-title">Controls</h2>
          <Controls {...props} />
        </section>
        <section className="sidebar-section">
          <h2 className="section-title">Modules</h2>
          <ModuleManager />
        </section>
      </div>
    </div>
  )
}
