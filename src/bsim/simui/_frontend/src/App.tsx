import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ApiProvider, useApi } from './app/providers'
import { UiProvider, useUi, isNumberControl } from './app/ui'
import type { EventRecord, RunStatus, Snapshot, TickData, UiSpec } from './types/api'
import type { SSEMessage, SSESubscription } from './lib/api'
import Sidebar from './components/Sidebar'
import MainContent from './components/MainContent'
import Footer from './components/Footer'

function AppCore() {
  const api = useApi()
  const { state, actions } = useUi()
  const [connected, setConnected] = useState(false)
  const sseRef = useRef<SSESubscription | null>(null)

  const initialize = useCallback(async () => {
    const spec = await api.spec() as UiSpec
    actions.setSpec(spec)
    // Prime controls defaults
    const defaults: Record<string, number | string> = {}
    for (const c of spec.controls || []) if (isNumberControl(c)) defaults[c.name] = c.default
    actions.setControls(defaults)
  }, [api, actions])

  const handleSSEMessage = useCallback((msg: SSEMessage) => {
    switch (msg.type) {
      case 'snapshot': {
        const snap = msg.data as Snapshot
        if (snap?.status) actions.setStatus(snap.status)
        if (Array.isArray(snap?.visuals)) actions.setVisuals(snap.visuals)
        if (Array.isArray(snap?.events)) actions.setEvents(snap.events)
        break
      }
      case 'tick': {
        const tick = msg.data as TickData
        if (tick?.status) actions.setStatus(tick.status)
        if (Array.isArray(tick?.visuals)) actions.setVisuals(tick.visuals)
        if (tick?.event) actions.appendEvent(tick.event)
        break
      }
      case 'event': {
        const event = msg.data as EventRecord
        actions.appendEvent(event)
        break
      }
      case 'status':
      case 'heartbeat': {
        const status = msg.data as RunStatus
        actions.setStatus(status)
        break
      }
    }
  }, [actions])

  useEffect(() => {
    const setup = async () => {
      await initialize()
      // Connect to SSE stream
      sseRef.current = api.subscribeSSE(
        handleSSEMessage,
        (err) => {
          console.error('SSE error:', err)
          setConnected(false)
        }
      )
      setConnected(true)
    }
    setup()
    return () => {
      if (sseRef.current) {
        sseRef.current.close()
        sseRef.current = null
      }
      setConnected(false)
    }
  }, [])

  const run = useCallback(async () => {
    const payload: any = { steps: Number(state.controls['steps']), dt: Number(state.controls['dt']) }
    if (state.controls['temperature'] !== undefined) payload.temperature = Number(state.controls['temperature'])
    // Clear existing visuals before starting a new run
    actions.setVisuals([])
    // Clear existing events so the new run log starts fresh
    actions.setEvents([])
    await api.run(payload.steps, payload.dt, payload)
  }, [api, state.controls, actions])
  const pause = useCallback(async () => { await api.pause() }, [api])
  const resume = useCallback(async () => { await api.resume() }, [api])
  const reset = useCallback(async () => { await api.reset(); actions.setEvents([]) }, [api, actions])

  return (
    <div className="app">
      <div className="app-layout">
        <header className="app-header">
          <h1 className="app-title">{state.spec?.title || 'BioSim UI'}</h1>
          <div className="app-status">{connected && <div className="sse-indicator" title="SSE Connected" />}</div>
        </header>
        <aside className="app-sidebar-left">
          <Sidebar onRun={run} onPause={pause} onResume={resume} onReset={reset} />
        </aside>
        <main className="app-main">
          <MainContent />
        </main>
        <aside className="app-sidebar-right">
          <Footer />
        </aside>
      </div>
    </div>
  )
}

export const App: React.FC = () => (
  <ApiProvider>
    <UiProvider>
      <AppCore />
    </UiProvider>
  </ApiProvider>
)
