import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useUi, useModuleNames, isJsonControl, isNumberControl } from '../app/ui'
import { formatDuration } from '../lib/time'

type Props = { onRun: () => void; onPause: () => void; onResume: () => void; onReset: () => void }

type PanelId = 'controls' | 'status' | 'modules'

function SidebarPanel({
  id,
  title,
  summary,
  open,
  onToggle,
  children,
}: {
  id: PanelId
  title: string
  summary?: string
  open: boolean
  onToggle: (id: PanelId) => void
  children: React.ReactNode
}) {
  return (
    <section className={`sidebar-panel ${open ? 'is-open' : 'is-closed'}`}>
      <button
        type="button"
        className="sidebar-panel-header"
        onClick={() => onToggle(id)}
        aria-expanded={open}
      >
        <span className={`sidebar-panel-chevron ${open ? 'open' : ''}`} aria-hidden="true">
          ▸
        </span>
        <span className="sidebar-panel-title">{title}</span>
        {summary && <span className="sidebar-panel-summary">{summary}</span>}
      </button>
      {open && <div className="sidebar-panel-body">{children}</div>}
    </section>
  )
}

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
      <div className="status-info">Ticks: {st.tick_count?.toLocaleString() || 0}</div>
    </div>
  )
  return <div className="status-display"><div className="status-badge status-idle">Idle</div></div>
}

function Controls() {
  const { state, actions } = useUi()
  const st = state.status
  const capabilities = state.spec?.capabilities
  const controlsEnabled = capabilities?.controls ?? true
  const runEnabled = controlsEnabled && (capabilities?.run ?? true)
  const pauseResumeEnabled = controlsEnabled && (capabilities?.pauseResume ?? true)
  const resetEnabled = controlsEnabled && (capabilities?.reset ?? true)
  const moduleNames = useModuleNames()
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const hiddenJson = new Set(['wiring', 'wiring_layout', 'module_ports', 'models'])
  const jsonControls = (state.spec?.controls || []).filter(isJsonControl).filter((c) => !hiddenJson.has(c.name))
  const updateControl = useCallback((name: string, value: string) => actions.setControls({ [name]: value }), [actions])

  const toFiniteNumber = (value: unknown): number => {
    if (value === '' || value === null || value === undefined) return Number.NaN
    const n = typeof value === 'number' ? value : Number(String(value))
    return Number.isFinite(n) ? n : Number.NaN
  }
  const controlDefault = (name: string): number | undefined => numberControls.find((c) => c.name === name)?.default
  const duration = toFiniteNumber(state.controls.duration ?? controlDefault('duration'))
  const tickDt = toFiniteNumber(state.controls.tick_dt ?? controlDefault('tick_dt'))
  const simTime = toFiniteNumber(st?.tick_count) * tickDt

  const runtimeNames = new Set(['duration', 'tick_dt'])
  const runtimeControls = numberControls.filter((c) => runtimeNames.has(c.name))
  const otherNumberControls = numberControls.filter((c) => !runtimeNames.has(c.name))
  const moduleNameSet = new Set(moduleNames)
  const moduleControls = new Map<string, typeof otherNumberControls>()
  const miscControls: typeof otherNumberControls = []
  for (const c of otherNumberControls) {
    const dot = c.name.indexOf('.')
    if (dot > 0) {
      const alias = c.name.slice(0, dot)
      if (moduleNameSet.has(alias)) {
        const existing = moduleControls.get(alias) || []
        existing.push(c)
        moduleControls.set(alias, existing)
        continue
      }
    }
    miscControls.push(c)
  }

  const moduleAliases = Array.from(moduleControls.keys())
  const [openModules, setOpenModules] = useState<Record<string, boolean>>({})
  useEffect(() => {
    if (moduleAliases.length === 0) return
    setOpenModules((prev) => {
      const next = { ...prev }
      for (const alias of moduleAliases) {
        if (!(alias in next)) next[alias] = false
      }
      return next
    })
  }, [moduleAliases.join('|')])
  const [jsonOpen, setJsonOpen] = useState(false)

  return (
    <div className="controls">
      {runtimeControls.length > 0 && (
        <div className="control-fields">
          {runtimeControls.map((c) => (
            <div key={c.name} className="control-field">
              <label htmlFor={`control-${c.name}`} className="control-label">{c.label || c.name}</label>
              <input id={`control-${c.name}`} type="number" className="control-input" value={String(state.controls[c.name] ?? c.default)} min={c.min} max={c.max} step={c.step ?? 'any'} onChange={(e) => updateControl(c.name, e.target.value)} disabled={!!st?.running || !controlsEnabled} />
            </div>
          ))}
        </div>
      )}
      {moduleControls.size > 0 && (
        <div className="control-fields">
          {Array.from(moduleControls.entries()).map(([alias, controls]) => (
            <div key={alias} className="control-group">
              <button
                type="button"
                className="control-group-header"
                onClick={() => setOpenModules((prev) => ({ ...prev, [alias]: !prev[alias] }))}
                aria-expanded={openModules[alias] ?? false}
              >
                <span className={`control-group-chevron ${openModules[alias] ? 'open' : ''}`} aria-hidden="true">
                  ▸
                </span>
                <span className="control-group-title">{alias}</span>
                <span className="control-group-summary">{controls.length} params</span>
              </button>
              {openModules[alias] && (
                <div className="control-group-body">
                  <div className="control-fields" style={{ marginTop: 0 }}>
                    {controls.map((c) => {
                      const dot = c.name.indexOf('.')
                      const short = dot > 0 ? c.name.slice(dot + 1) : c.name
                      return (
                        <div key={c.name} className="control-field">
                          <label htmlFor={`control-${c.name}`} className="control-label">{c.label || short}</label>
                          <input id={`control-${c.name}`} type="number" className="control-input" value={String(state.controls[c.name] ?? c.default)} min={c.min} max={c.max} step={c.step ?? 'any'} onChange={(e) => updateControl(c.name, e.target.value)} disabled={!!st?.running || !controlsEnabled} />
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {miscControls.length > 0 && (
        <div className="control-fields">
          {miscControls.map((c) => (
            <div key={c.name} className="control-field">
              <label htmlFor={`control-${c.name}`} className="control-label">{c.label || c.name}</label>
              <input id={`control-${c.name}`} type="number" className="control-input" value={String(state.controls[c.name] ?? c.default)} min={c.min} max={c.max} step={c.step ?? 'any'} onChange={(e) => updateControl(c.name, e.target.value)} disabled={!!st?.running || !controlsEnabled} />
            </div>
          ))}
        </div>
      )}
      {jsonControls.length > 0 && (
        <div className="control-group">
          <button
            type="button"
            className="control-group-header"
            onClick={() => setJsonOpen((prev) => !prev)}
            aria-expanded={jsonOpen}
          >
            <span className={`control-group-chevron ${jsonOpen ? 'open' : ''}`} aria-hidden="true">
              ▸
            </span>
            <span className="control-group-title">Advanced (JSON)</span>
            <span className="control-group-summary">{jsonControls.length} fields</span>
          </button>
          {jsonOpen && (
            <div className="control-group-body">
              <div className="control-fields">
                {jsonControls.map((c) => (
                  <div key={c.name} className="control-field">
                    <label htmlFor={`control-${c.name}`} className="control-label">{c.label || c.name}</label>
                    <textarea
                      id={`control-${c.name}`}
                      className="control-input"
                      value={String(state.controls[c.name] ?? c.default)}
                      placeholder={c.placeholder}
                      rows={c.rows ?? 6}
                      onChange={(e) => updateControl(c.name, e.target.value)}
                      disabled={!!st?.running || !controlsEnabled}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      <div className="control-derived">
        {st?.running && Number.isFinite(simTime) && (
          <div className="control-derived-row">
            <span className="control-derived-label">Sim time</span>
            <span className="control-derived-value">{formatDuration(simTime)}</span>
          </div>
        )}
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
        <button type="button" className="btn btn-small" onClick={showAll}>Show All</button>
        <button type="button" className="btn btn-small" onClick={hideAll}>Hide All</button>
      </div>
    </div>
  )
}

export default function Sidebar(props: Props) {
  const { state } = useUi()
  const moduleNames = useModuleNames()
  const totalModules = moduleNames.length
  const selectedModules = state.visibleModules.size || totalModules

  // Reduce scroll by opening only one panel by default.
  // Users can expand/collapse any panel independently.
  const [open, setOpen] = useState<Record<PanelId, boolean>>({
    controls: false,
    status: false,
    modules: false,
  })

  const toggle = useCallback((id: PanelId) => {
    setOpen((prev) => ({ ...prev, [id]: !prev[id] }))
  }, [])

  const statusSummary = useMemo(() => {
    const st = state.status
    if (!st) return 'Unknown'
    if (st.error) return 'Error'
    if (st.running) return `${st.paused ? 'Paused' : 'Running'} · Ticks: ${st.tick_count?.toLocaleString() || 0}`
    return 'Idle'
  }, [state.status])

  const controlsSummary = useMemo(() => {
    const controls = Array.isArray(state.spec?.controls) ? state.spec!.controls! : []
    const count = controls.filter((c) => isNumberControl(c) || isJsonControl(c)).length
    return count ? `${count} controls` : 'No controls'
  }, [state.spec])

  const modulesSummary = useMemo(() => {
    if (totalModules === 0) return 'No modules'
    return `${selectedModules}/${totalModules} shown`
  }, [selectedModules, totalModules])

  return (
    <div className="sidebar">
      <div className="sidebar-content">
        <SidebarPanel id="status" title="Status" summary={statusSummary} open={open.status} onToggle={toggle}>
          <StatusDisplay />
        </SidebarPanel>
        <SidebarPanel id="controls" title="Controls" summary={controlsSummary} open={open.controls} onToggle={toggle}>
          <Controls />
        </SidebarPanel>
        <SidebarPanel id="modules" title="Modules" summary={modulesSummary} open={open.modules} onToggle={toggle}>
          <ModuleManager />
        </SidebarPanel>
        <ActionsBar {...props} />
      </div>
    </div>
  )
}

function ActionsBar({ onRun, onPause, onResume, onReset }: Props) {
  const { state } = useUi()
  const st = state.status
  const controls = Array.isArray(state.spec?.controls) ? state.spec!.controls! : []
  const durationControl = controls.find((c) => isNumberControl(c) && c.name === 'duration')
  const durationDefault = durationControl && isNumberControl(durationControl) ? durationControl.default : undefined
  const duration = (() => {
    const raw = state.controls.duration ?? durationDefault
    const n = typeof raw === 'number' ? raw : Number(String(raw))
    return Number.isFinite(n) ? n : NaN
  })()
  const capabilities = state.spec?.capabilities
  const controlsEnabled = capabilities?.controls ?? true
  const runEnabled = controlsEnabled && (capabilities?.run ?? true)
  const pauseResumeEnabled = controlsEnabled && (capabilities?.pauseResume ?? true)
  const resetEnabled = controlsEnabled && (capabilities?.reset ?? true)

  return (
    <div className="sidebar-actions">
      <div className="sidebar-actions-row">
        <div className="sidebar-actions-label">Duration</div>
        <div className="sidebar-actions-value">{Number.isFinite(duration) ? formatDuration(duration) : '—'}</div>
      </div>
      {runEnabled && (
        <button type="button" className="btn btn-primary" onClick={onRun} disabled={!!st?.running}>
          Run Simulation
        </button>
      )}
      {pauseResumeEnabled && st?.running && (
        <button type="button" className="btn btn-secondary" onClick={st.paused ? onResume : onPause}>
          {st.paused ? 'Resume' : 'Pause'}
        </button>
      )}
      {resetEnabled && (
        <button type="button" className="btn btn-outline" onClick={onReset}>
          Reset
        </button>
      )}
    </div>
  )
}
