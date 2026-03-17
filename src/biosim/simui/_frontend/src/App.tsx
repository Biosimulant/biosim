import React, { useCallback, useEffect, useRef, useState } from 'react'
import { ApiProvider, useApi } from './app/providers'
import { UiProvider, useUi, isNumberControl } from './app/ui'
import { ComposeProvider, useCompose } from './app/compose'
import type { EventRecord, RunStatus, Snapshot, TickData, UiSpec } from './types/api'
import type { SSEMessage, SSESubscription } from './lib/api'
import Sidebar from './components/Sidebar'
import ComposeCanvas from './components/ComposeCanvas'
import ComposeToolbar from './components/ComposeToolbar'
import RightPanel from './components/RightPanel'
import { FileListModal, YamlPreviewModal } from './components/ComposeModals'

function UnifiedView() {
  const api = useApi()
  const { state: uiState, actions: uiActions } = useUi()
  const { state: composeState, actions: composeActions } = useCompose()
  const [connected, setConnected] = useState(false)
  const [rightPanelOpen, setRightPanelOpen] = useState(false)
  const sseRef = useRef<SSESubscription | null>(null)

  // Initialize simulation UI spec
  const initialize = useCallback(async () => {
    const spec = await api.spec() as UiSpec
    uiActions.setSpec(spec)
    const defaults: Record<string, number | string> = {}
    for (const c of spec.controls || []) if (isNumberControl(c)) defaults[c.name] = c.default
    uiActions.setControls(defaults)
  }, [api, uiActions])

  // SSE message handler
  const handleSSEMessage = useCallback((msg: SSEMessage) => {
    switch (msg.type) {
      case 'snapshot': {
        const snap = msg.data as Snapshot
        if (snap?.status) uiActions.setStatus(snap.status)
        if (Array.isArray(snap?.visuals)) uiActions.setVisuals(snap.visuals)
        if (Array.isArray(snap?.events)) uiActions.setEvents(snap.events)
        break
      }
      case 'tick': {
        const tick = msg.data as TickData
        if (tick?.status) uiActions.setStatus(tick.status)
        if (Array.isArray(tick?.visuals)) uiActions.setVisuals(tick.visuals)
        if (tick?.event) uiActions.appendEvent(tick.event)
        // Auto-open right panel on first results
        if (!rightPanelOpen && Array.isArray(tick?.visuals) && tick.visuals.length > 0) {
          setRightPanelOpen(true)
        }
        break
      }
      case 'event': {
        const event = msg.data as EventRecord
        uiActions.appendEvent(event)
        break
      }
      case 'status':
      case 'heartbeat': {
        const status = msg.data as RunStatus
        uiActions.setStatus(status)
        break
      }
    }
  }, [uiActions, rightPanelOpen])

  // Connect SSE on mount
  useEffect(() => {
    const setup = async () => {
      await initialize()
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

  // Simulation actions
  const run = useCallback(async () => {
    const payload: Record<string, number> = {}
    for (const c of uiState.spec?.controls || []) {
      if (!isNumberControl(c)) continue
      const raw = uiState.controls[c.name] ?? c.default
      const value = typeof raw === 'number' ? raw : Number(String(raw))
      if (Number.isFinite(value)) payload[c.name] = value
    }
    const duration = Number(payload.duration)
    const tickDt = payload.tick_dt
    uiActions.setVisuals([])
    uiActions.setEvents([])
    setRightPanelOpen(true)
    await api.run(duration, tickDt, payload)
  }, [api, uiState.controls, uiState.spec, uiActions])

  const pause = useCallback(async () => { await api.pause() }, [api])
  const resume = useCallback(async () => { await api.resume() }, [api])
  const reset = useCallback(async () => { await api.reset(); uiActions.setEvents([]) }, [api, uiActions])

  return (
    <>
      {/* Header */}
      <header className="app-header">
        <h1 className="app-title">{uiState.spec?.title || 'BioSim UI'}</h1>
        <div className="app-status">
          {connected && <div className="sse-indicator" title="SSE Connected" />}
        </div>
      </header>

      {/* Toolbar */}
      <div className="app-toolbar">
        <ComposeToolbar />
        {composeState.error && (
          <div className={`toolbar-message ${composeState.error.includes('success') ? 'toolbar-message--success' : 'toolbar-message--error'}`}>
            {composeState.error}
            <button className="toolbar-message-close" onClick={() => composeActions.setError(null)}>{'\u2715'}</button>
          </div>
        )}
      </div>

      {/* Main body: sidebar | center | right panel */}
      <div className="app-body">
        <aside className="app-sidebar-left">
          <Sidebar onRun={run} onPause={pause} onResume={resume} onReset={reset} />
        </aside>

        <main className="app-center">
          {composeState.centerView === 'canvas' ? (
            <ComposeCanvas />
          ) : (
            <div className="yaml-view">
              <pre className="yaml-content">{composeState.yamlPreview || 'Click "YAML" in the toolbar to generate a preview.'}</pre>
            </div>
          )}
        </main>

        <RightPanel isOpen={rightPanelOpen} onToggle={() => setRightPanelOpen(!rightPanelOpen)} />
      </div>

      {/* Modals */}
      <FileListModal />
      <YamlPreviewModal />
    </>
  )
}

function AppCore() {
  const api = useApi()

  return (
    <ComposeProvider api={api}>
      <div className="app">
        <UnifiedView />
      </div>
    </ComposeProvider>
  )
}

export const App: React.FC = () => (
  <ApiProvider>
    <UiProvider>
      <AppCore />
    </UiProvider>
  </ApiProvider>
)
