import React, { createContext, useContext, useMemo, useState } from 'react'
import type { Control, EventRecord, ModuleVisuals, RunStatus, UiSpec } from '../types/api'

export type ControlsState = Record<string, number | string>

type UiState = {
  spec: UiSpec | null
  status: RunStatus | null
  visuals: ModuleVisuals[]
  events: EventRecord[]
  controls: ControlsState
  visibleModules: Set<string>
}

type UiActions = {
  setSpec: (s: UiSpec) => void
  setStatus: (s: RunStatus) => void
  setVisuals: (v: ModuleVisuals[]) => void
  setEvents: (e: EventRecord[]) => void
  appendEvent: (e: EventRecord) => void
  setControls: (c: Partial<ControlsState>) => void
  setVisibleModules: (mods: Set<string>) => void
}

const UiCtx = createContext<{ state: UiState; actions: UiActions } | null>(null)

export function UiProvider({ children }: { children: React.ReactNode }) {
  const [spec, setSpecState] = useState<UiSpec | null>(null)
  const [status, setStatusState] = useState<RunStatus | null>(null)
  const [visuals, setVisualsState] = useState<ModuleVisuals[]>([])
  const [events, setEventsState] = useState<EventRecord[]>([])
  const [controls, setControlsState] = useState<ControlsState>({ duration: 10, tick_dt: 0.1 })
  const [visibleModules, setVisibleModulesState] = useState<Set<string>>(new Set())

  const actions: UiActions = React.useMemo(() => ({
    setSpec: setSpecState,
    setStatus: setStatusState,
    setVisuals: setVisualsState,
    setEvents: setEventsState,
    appendEvent: (e) => setEventsState((prev) => [...prev, e]),
    setControls: (c) => setControlsState((prev) => ({ ...prev, ...c }) as ControlsState),
    setVisibleModules: setVisibleModulesState,
  }), [])

  const state: UiState = { spec, status, visuals, events, controls, visibleModules }
  const value = useMemo(() => ({ state, actions }), [spec, status, visuals, events, controls, visibleModules, actions])
  return <UiCtx.Provider value={value}>{children}</UiCtx.Provider>
}

export function useUi() {
  const ctx = useContext(UiCtx)
  if (!ctx) throw new Error('useUi must be used within UiProvider')
  return ctx
}

export function useModuleNames(): string[] {
  const { state } = useUi()
  return useMemo(() => {
    const specMods = Array.isArray(state.spec?.modules) ? state.spec!.modules! : []
    const visualMods = state.visuals.map((v) => v.module)
    const out: string[] = []
    const seen = new Set<string>()
    for (const m of specMods) {
      if (m && !seen.has(m)) { out.push(m); seen.add(m) }
    }
    for (const m of visualMods) {
      if (m && !seen.has(m)) { out.push(m); seen.add(m) }
    }
    return out
  }, [state.spec, state.visuals])
}

export function useVisualsByModule(): Map<string, ModuleVisuals['visuals']> {
  const { state } = useUi()
  return useMemo(() => {
    const map = new Map<string, ModuleVisuals['visuals']>()
    for (const m of state.visuals) {
      const existing = map.get(m.module)
      if (existing) {
        // Merge visuals for modules with the same class name
        map.set(m.module, [...existing, ...(m.visuals || [])])
      } else {
        map.set(m.module, m.visuals || [])
      }
    }
    return map
  }, [state.visuals])
}

export function isNumberControl(c: Control): c is Extract<Control, { type: 'number' }> {
  return (c as any).type === 'number'
}
