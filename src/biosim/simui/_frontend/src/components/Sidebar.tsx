import React, { useCallback, useEffect, useState } from 'react'
import { useUi, useModuleNames, isNumberControl } from '../app/ui'
import { useCompose } from '../app/compose'
import { formatDuration } from '../lib/time'
import type { ModuleSpec } from '../lib/api'

type SimProps = { onRun: () => void; onPause: () => void; onResume: () => void; onReset: () => void }

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
      <div className="status-info">Steps: {st.step_count?.toLocaleString() || 0}</div>
    </div>
  )
  return <div className="status-display"><div className="status-badge status-idle">Idle</div></div>
}

function Controls({ onRun, onPause, onResume, onReset }: SimProps) {
  const { state, actions } = useUi()
  const st = state.status
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const updateControl = useCallback((name: string, value: string) => actions.setControls({ [name]: value }), [actions])

  const toFiniteNumber = (value: unknown): number => {
    if (value === '' || value === null || value === undefined) return Number.NaN
    const n = typeof value === 'number' ? value : Number(String(value))
    return Number.isFinite(n) ? n : Number.NaN
  }
  const controlDefault = (name: string): number | undefined => numberControls.find((c) => c.name === name)?.default
  const duration = toFiniteNumber(state.controls.duration ?? controlDefault('duration'))
  const simTime = toFiniteNumber(st?.sim_time)

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
      <div className="control-derived">
        <div className="control-derived-row">
          <span className="control-derived-label">Duration</span>
          <span className="control-derived-value">{Number.isFinite(duration) ? formatDuration(duration) : '\u2014'}</span>
        </div>
        {st?.running && Number.isFinite(simTime) && (
          <div className="control-derived-row">
            <span className="control-derived-label">Sim time</span>
            <span className="control-derived-value">{formatDuration(simTime)}</span>
          </div>
        )}
      </div>
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
        <button className="btn btn-small" onClick={showAll}>Show All</button>
        <button className="btn btn-small" onClick={hideAll}>Hide All</button>
      </div>
    </div>
  )
}

function PaletteSection() {
  const { state, actions } = useCompose()
  const [expanded, setExpanded] = useState(true)
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['neuro', 'ecology']))
  const [search, setSearch] = useState('')

  const registry = state.registry

  const categoryColors: Record<string, string> = {
    neuro: 'var(--primary)',
    ecology: '#22c55e',
    custom: '#a855f7',
  }

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories)
    newExpanded.has(category) ? newExpanded.delete(category) : newExpanded.add(category)
    setExpandedCategories(newExpanded)
  }

  const filteredCategories = registry
    ? Object.entries(registry.categories).map(([category, paths]) => {
        const modules = paths
          .map(path => ({ path, spec: registry.modules[path] }))
          .filter(({ spec }) => {
            if (!spec) return false
            if (!search) return true
            const s = search.toLowerCase()
            return spec.name.toLowerCase().includes(s) || spec.description?.toLowerCase().includes(s) || category.toLowerCase().includes(s)
          })
        return { category, modules }
      }).filter(({ modules }) => modules.length > 0)
    : []

  const handleDragStart = (event: React.DragEvent, moduleType: string, spec: ModuleSpec) => {
    actions.onPaletteDragStart(event, moduleType, spec)
  }

  return (
    <div className="sidebar-section">
      <h2 className="section-title section-title--collapsible" onClick={() => setExpanded(!expanded)}>
        <span>{expanded ? '\u25BC' : '\u25B6'}</span> Module Palette
      </h2>
      {expanded && (
        <div className="palette-content">
          <input
            type="text"
            placeholder="Search modules..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="control-input palette-search"
          />
          {!registry && <div className="empty-state"><p>Loading modules...</p></div>}
          {filteredCategories.map(({ category, modules }) => (
            <div key={category} className="palette-category">
              <button className="palette-category-header" onClick={() => toggleCategory(category)}>
                <span className="palette-chevron" style={{ transform: expandedCategories.has(category) ? 'rotate(90deg)' : 'none' }}>{'\u25B6'}</span>
                <span className="palette-dot" style={{ background: categoryColors[category] || '#666' }} />
                {category.charAt(0).toUpperCase() + category.slice(1)}
                <span className="palette-count">{modules.length}</span>
              </button>
              {expandedCategories.has(category) && (
                <div className="palette-modules">
                  {modules.map(({ path, spec }) => (
                    <div
                      key={path}
                      draggable
                      onDragStart={(e) => handleDragStart(e, path, spec)}
                      className="palette-module"
                      title={spec.description || path}
                    >
                      <div className="palette-module-name">{spec.name}</div>
                      <div className="palette-module-ports">
                        {spec.inputs.length > 0 && <span>in: {spec.inputs.join(', ')}</span>}
                        {spec.inputs.length > 0 && spec.outputs.length > 0 && ' | '}
                        {spec.outputs.length > 0 && <span>out: {spec.outputs.join(', ')}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {registry && filteredCategories.length === 0 && (
            <div className="empty-state"><p>No modules found</p></div>
          )}
          <div className="palette-hint">Drag modules to canvas</div>
        </div>
      )}
    </div>
  )
}

export default function Sidebar(props: SimProps) {
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
        <PaletteSection />
      </div>
    </div>
  )
}
