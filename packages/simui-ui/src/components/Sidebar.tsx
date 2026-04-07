import React, { useCallback, useEffect, useState } from 'react'
import { useUi, useModuleNames, isJsonControl, isNumberControl } from '../app/ui'
import { resolveRunProgress } from '../lib/progress'
import { formatDuration } from '../lib/time'

type Props = {
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onReset: () => void;
  runPending?: boolean;
  sidebarAction?: React.ReactNode;
}

function toFiniteNumber(value: unknown): number {
  if (value === '' || value === null || value === undefined) return Number.NaN
  const n = typeof value === 'number' ? value : Number(String(value))
  return Number.isFinite(n) ? n : Number.NaN
}

function SidebarActions({
  onRun,
  onPause,
  onResume,
  onReset,
  runPending,
  sidebarAction,
}: Props) {
  const { state } = useUi()
  const st = state.status
  const capabilities = state.spec?.capabilities
  const controlsEnabled = capabilities?.controls ?? true
  const runEnabled = controlsEnabled && (capabilities?.run ?? true)
  const showRunWhenDisabled = capabilities?.showRunWhenDisabled ?? false
  const showRunButton = runEnabled || showRunWhenDisabled
  const runDisabledReason = capabilities?.runDisabledReason || 'Run is disabled for this space.'
  const runButtonDisabled = !runEnabled || !!st?.running || !!runPending
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const controlDefault = (name: string): number | undefined => numberControls.find((c) => c.name === name)?.default
  const duration = toFiniteNumber(state.controls.duration ?? controlDefault('duration'))
  const tickDt = toFiniteNumber(state.controls.tick_dt ?? controlDefault('tick_dt'))
  const progress = resolveRunProgress({ status: st, duration, tickDt })

  let statusSummary = 'Idle'
  if (st?.error) statusSummary = progress.progressPct !== null ? `Error · ${progress.progressLabel}` : 'Error'
  else if (st?.running) {
    statusSummary = progress.progressPct !== null
      ? `${st.paused ? 'Paused' : 'Running'} · ${progress.progressLabel}`
      : st.paused ? 'Paused' : 'Running'
  } else if (progress.progressPct !== null) {
    statusSummary = `Idle · Last run: ${progress.progressLabel}`
  }

  return (
    <div className="sidebar-actions">
      <div className="sidebar-actions-summary">{statusSummary}</div>
      <div className="sidebar-actions-buttons">
        {showRunButton && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={runEnabled ? onRun : undefined}
            disabled={runButtonDisabled}
            title={!runEnabled ? runDisabledReason : undefined}
          >
            {runPending ? 'Starting…' : 'Run Simulation'}
          </button>
        )}
        {controlsEnabled && (capabilities?.pauseResume ?? true) && st?.running && (
          <button type="button" className="btn btn-secondary" onClick={st.paused ? onResume : onPause}>
            {st.paused ? 'Resume' : 'Pause'}
          </button>
        )}
        {controlsEnabled && (capabilities?.reset ?? true) && (
          <button type="button" className="btn btn-outline" onClick={onReset}>
            Reset
          </button>
        )}
        {sidebarAction}
      </div>
    </div>
  )
}

function Controls() {
  const { state, actions } = useUi()
  const st = state.status
  const capabilities = state.spec?.capabilities
  const controlsEnabled = capabilities?.controls ?? true
  const moduleNames = useModuleNames()
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const hiddenJson = new Set(['wiring', 'wiring_layout', 'module_ports', 'models'])
  const jsonControls = (state.spec?.controls || []).filter(isJsonControl).filter((c) => !hiddenJson.has(c.name))
  const updateControl = useCallback((name: string, value: string) => actions.setControls({ [name]: value }), [actions])

  const controlDefault = (name: string): number | undefined => numberControls.find((c) => c.name === name)?.default
  const duration = toFiniteNumber(state.controls.duration ?? controlDefault('duration'))
  const tickDt = toFiniteNumber(state.controls.tick_dt ?? controlDefault('tick_dt'))
  const progress = resolveRunProgress({ status: st, duration, tickDt })

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
        {st?.running && progress.simTime !== null && (
          <div className="control-derived-row">
            <span className="control-derived-label">Sim time</span>
            <span className="control-derived-value">{formatDuration(progress.simTime)}</span>
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
  if (moduleNames.length === 0) return null
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
  const moduleNames = useModuleNames()
  const numberControls = useUi().state.spec?.controls?.filter(isNumberControl) || []
  const totalControls = numberControls.length
  const [open, setOpen] = useState(true)

  const summary = `${totalControls} controls · ${moduleNames.length} modules`

  return (
    <section className={`sidebar-panel ${open ? 'is-open' : 'is-closed'}`} style={{ margin: '0 12px' }}>
      <button
        type="button"
        className="sidebar-panel-header"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <span className={`sidebar-panel-chevron ${open ? 'open' : ''}`} aria-hidden="true">
          ▸
        </span>
        <span className="sidebar-panel-title">Settings</span>
        <span className="sidebar-panel-summary">{summary}</span>
      </button>
      {open && (
        <div className="sidebar-panel-body">
          <SidebarActions {...props} />
          <Controls />
          <ModuleManager />
        </div>
      )}
    </section>
  )
}
