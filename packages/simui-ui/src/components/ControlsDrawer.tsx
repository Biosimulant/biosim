import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useUi, useModuleNames, isJsonControl, isNumberControl } from '../app/ui'
import { formatDuration } from '../lib/time'

type Props = {
  open: boolean
  onClose: () => void
  sidebarAction?: React.ReactNode
}

export default function ControlsDrawer({ open, onClose, sidebarAction }: Props) {
  const { state, actions } = useUi()
  const st = state.status
  const capabilities = state.spec?.capabilities
  const controlsEnabled = capabilities?.controls ?? true
  const moduleNames = useModuleNames()
  const numberControls = (state.spec?.controls || []).filter(isNumberControl)
  const hiddenJson = new Set(['wiring', 'wiring_layout', 'module_ports', 'models'])
  const jsonControls = (state.spec?.controls || []).filter(isJsonControl).filter((c) => !hiddenJson.has(c.name))

  const updateControl = useCallback(
    (name: string, value: string) => actions.setControls({ [name]: value }),
    [actions]
  )

  // Separate runtime vs module vs misc controls
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

  // Keyboard escape
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [open, onClose])

  const totalControls = numberControls.length + jsonControls.length

  return (
    <>
      {open && <div className="drawer-backdrop" onClick={onClose} />}
      <aside className={`controls-drawer ${open ? 'controls-drawer--open' : ''}`}>
        <header className="controls-drawer-header">
          <h2 className="controls-drawer-title">Parameters</h2>
          <span className="controls-drawer-badge">{totalControls}</span>
          <button className="controls-drawer-close" onClick={onClose} title="Close">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </header>

        <div className="controls-drawer-body">
          {/* Runtime controls */}
          {runtimeControls.length > 0 && (
            <section className="drawer-section">
              <h3 className="drawer-section-title">Runtime</h3>
              <div className="drawer-fields">
                {runtimeControls.map((c) => (
                  <div key={c.name} className="drawer-field">
                    <label htmlFor={`ctrl-${c.name}`} className="drawer-field-label">
                      {c.label || c.name}
                    </label>
                    <input
                      id={`ctrl-${c.name}`}
                      type="number"
                      className="drawer-field-input"
                      value={String(state.controls[c.name] ?? c.default)}
                      min={c.min}
                      max={c.max}
                      step={c.step ?? 'any'}
                      onChange={(e) => updateControl(c.name, e.target.value)}
                      disabled={!!st?.running || !controlsEnabled}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Module-grouped controls */}
          {moduleControls.size > 0 && Array.from(moduleControls.entries()).map(([alias, controls]) => (
            <section key={alias} className="drawer-section">
              <button
                type="button"
                className="drawer-section-header"
                onClick={() => setOpenModules((prev) => ({ ...prev, [alias]: !prev[alias] }))}
                aria-expanded={openModules[alias] ?? false}
              >
                <span className={`drawer-chevron ${openModules[alias] ? 'open' : ''}`}>&#9656;</span>
                <h3 className="drawer-section-title">{alias}</h3>
                <span className="drawer-section-meta">{controls.length}</span>
              </button>
              {openModules[alias] && (
                <div className="drawer-fields">
                  {controls.map((c) => {
                    const dot = c.name.indexOf('.')
                    const short = dot > 0 ? c.name.slice(dot + 1) : c.name
                    return (
                      <div key={c.name} className="drawer-field">
                        <label htmlFor={`ctrl-${c.name}`} className="drawer-field-label">
                          {c.label || short}
                        </label>
                        <input
                          id={`ctrl-${c.name}`}
                          type="number"
                          className="drawer-field-input"
                          value={String(state.controls[c.name] ?? c.default)}
                          min={c.min}
                          max={c.max}
                          step={c.step ?? 'any'}
                          onChange={(e) => updateControl(c.name, e.target.value)}
                          disabled={!!st?.running || !controlsEnabled}
                        />
                      </div>
                    )
                  })}
                </div>
              )}
            </section>
          ))}

          {/* Miscellaneous number controls */}
          {miscControls.length > 0 && (
            <section className="drawer-section">
              <h3 className="drawer-section-title">Parameters</h3>
              <div className="drawer-fields">
                {miscControls.map((c) => (
                  <div key={c.name} className="drawer-field">
                    <label htmlFor={`ctrl-${c.name}`} className="drawer-field-label">
                      {c.label || c.name}
                    </label>
                    <input
                      id={`ctrl-${c.name}`}
                      type="number"
                      className="drawer-field-input"
                      value={String(state.controls[c.name] ?? c.default)}
                      min={c.min}
                      max={c.max}
                      step={c.step ?? 'any'}
                      onChange={(e) => updateControl(c.name, e.target.value)}
                      disabled={!!st?.running || !controlsEnabled}
                    />
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* JSON advanced controls */}
          {jsonControls.length > 0 && (
            <section className="drawer-section">
              <button
                type="button"
                className="drawer-section-header"
                onClick={() => setJsonOpen((prev) => !prev)}
                aria-expanded={jsonOpen}
              >
                <span className={`drawer-chevron ${jsonOpen ? 'open' : ''}`}>&#9656;</span>
                <h3 className="drawer-section-title">Advanced (JSON)</h3>
                <span className="drawer-section-meta">{jsonControls.length}</span>
              </button>
              {jsonOpen && (
                <div className="drawer-fields">
                  {jsonControls.map((c) => (
                    <div key={c.name} className="drawer-field">
                      <label htmlFor={`ctrl-${c.name}`} className="drawer-field-label">
                        {c.label || c.name}
                      </label>
                      <textarea
                        id={`ctrl-${c.name}`}
                        className="drawer-field-input drawer-field-textarea"
                        value={String(state.controls[c.name] ?? c.default)}
                        placeholder={c.placeholder}
                        rows={c.rows ?? 6}
                        onChange={(e) => updateControl(c.name, e.target.value)}
                        disabled={!!st?.running || !controlsEnabled}
                      />
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}

          {/* Sidebar action slot */}
          {sidebarAction && (
            <section className="drawer-section">
              {sidebarAction}
            </section>
          )}
        </div>
      </aside>
    </>
  )
}
