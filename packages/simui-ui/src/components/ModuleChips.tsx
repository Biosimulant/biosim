import React, { useCallback, useEffect } from 'react'
import { useUi, useModuleNames } from '../app/ui'

export default function ModuleChips() {
  const { state, actions } = useUi()
  const moduleNames = useModuleNames()

  useEffect(() => {
    if (moduleNames.length > 0 && state.visibleModules.size === 0) {
      actions.setVisibleModules(new Set(moduleNames))
    }
  }, [moduleNames, state.visibleModules.size, actions])

  const toggle = useCallback((name: string) => {
    const next = new Set(state.visibleModules)
    next.has(name) ? next.delete(name) : next.add(name)
    actions.setVisibleModules(next)
  }, [state.visibleModules, actions])

  const allSelected = moduleNames.every((m) => state.visibleModules.has(m))

  const toggleAll = useCallback(() => {
    if (allSelected) {
      actions.setVisibleModules(new Set())
    } else {
      actions.setVisibleModules(new Set(moduleNames))
    }
  }, [allSelected, moduleNames, actions])

  if (moduleNames.length <= 1) return null

  return (
    <div className="module-chips">
      <button
        className={`module-chip module-chip--all ${allSelected ? 'module-chip--active' : ''}`}
        onClick={toggleAll}
        title={allSelected ? 'Hide all modules' : 'Show all modules'}
      >
        All
      </button>
      {moduleNames.map((m) => (
        <button
          key={m}
          className={`module-chip ${state.visibleModules.has(m) ? 'module-chip--active' : ''}`}
          onClick={() => toggle(m)}
          title={state.visibleModules.has(m) ? `Hide ${m}` : `Show ${m}`}
        >
          <span className="module-chip-dot" />
          {m}
        </button>
      ))}
    </div>
  )
}
