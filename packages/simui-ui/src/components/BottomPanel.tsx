import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useApi } from '../app/providers'
import { useUi } from '../app/ui'
import type { ChatAdapter } from '../types/chat'
import type { RunLogEntry } from '../types/api'
import ChatPanel from './ChatPanel'

type Tab = 'events' | 'logs' | 'chat'

type Props = {
  chatAdapter?: ChatAdapter
}

/** Read the externally-injected SimUI version from the CSS custom property
 *  `--simui-left-sidebar-version` set by the platform wrapper. */
function useExternalVersion(): string | null {
  const [ver, setVer] = useState<string | null>(null)
  useEffect(() => {
    const root = document.querySelector('.simui-root') as HTMLElement | null
    if (!root) return
    const raw = getComputedStyle(root).getPropertyValue('--simui-left-sidebar-version').trim()
    // Value is JSON-stringified by the platform (e.g. '"SimUI f829e20"')
    if (raw) {
      try { setVer(JSON.parse(raw)) } catch { setVer(raw) }
    }
  }, [])
  return ver
}

export default function BottomPanel({ chatAdapter }: Props) {
  const api = useApi()
  const { state, actions } = useUi()
  const events = state.events || []
  const isRunning = state.status?.running ?? false
  const bsimVersion = state.spec?.bsim_version
  const externalVersion = useExternalVersion()

  const [expanded, setExpanded] = useState(false)
  const [tab, setTab] = useState<Tab>('events')
  const [logs, setLogs] = useState<RunLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsDownloading, setLogsDownloading] = useState(false)
  const maxSeqRef = useRef(0)

  const eventsListRef = useRef<HTMLDivElement>(null)
  const logsListRef = useRef<HTMLDivElement>(null)
  const [autoScrollEvents, setAutoScrollEvents] = useState(true)
  const [autoScrollLogs, setAutoScrollLogs] = useState(true)

  // Auto-expand when events arrive during a run
  useEffect(() => {
    if (events.length > 0 && isRunning && !expanded) {
      setExpanded(true)
    }
  }, [events.length, isRunning])

  // Auto-scroll events list
  useEffect(() => {
    if (autoScrollEvents && eventsListRef.current) {
      eventsListRef.current.scrollTop = eventsListRef.current.scrollHeight
    }
  }, [events, autoScrollEvents])

  // Auto-scroll logs list
  useEffect(() => {
    if (autoScrollLogs && logsListRef.current) {
      logsListRef.current.scrollTop = logsListRef.current.scrollHeight
    }
  }, [logs, autoScrollLogs])

  const onScrollEvents = useCallback(() => {
    if (!eventsListRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = eventsListRef.current
    setAutoScrollEvents(scrollTop + clientHeight >= scrollHeight - 10)
  }, [])

  const onScrollLogs = useCallback(() => {
    if (!logsListRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = logsListRef.current
    setAutoScrollLogs(scrollTop + clientHeight >= scrollHeight - 10)
  }, [])

  // Poll for run logs when the logs tab is active
  useEffect(() => {
    if (tab !== 'logs' || !api.logs) return
    let cancelled = false
    const fetchLogs = async () => {
      if (cancelled) return
      setLogsLoading(true)
      try {
        const sinceSeq = maxSeqRef.current > 0 ? maxSeqRef.current : undefined
        const resp = await api.logs!(sinceSeq)
        if (cancelled) return
        if (resp.items && resp.items.length > 0) {
          setLogs((prev) => {
            const existingIds = new Set(prev.map((l) => l.id))
            const newLogs = resp.items.filter((l: RunLogEntry) => !existingIds.has(l.id))
            if (newLogs.length === 0) return prev
            const merged = [...prev, ...newLogs].sort((a, b) => a.seq - b.seq)
            const maxSeq = merged[merged.length - 1]?.seq ?? 0
            if (maxSeq > maxSeqRef.current) maxSeqRef.current = maxSeq
            return merged
          })
        }
      } catch (err) {
        console.error('Failed to fetch run logs:', err)
      } finally {
        if (!cancelled) setLogsLoading(false)
      }
    }
    void fetchLogs()
    const interval = setInterval(fetchLogs, 3000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [tab, api, isRunning])

  const hasLogs = !!api.logs
  const hasChat = !!chatAdapter

  const levelClass = (level: string) => {
    if (level === 'error') return 'log-level log-level--error'
    if (level === 'warning') return 'log-level log-level--warning'
    return 'log-level log-level--info'
  }

  const sourceLabel = (source: string) => {
    if (source === 'sandbox') return 'SANDBOX'
    if (source === 'system') return 'SYSTEM'
    if (source === 'runstream') return 'STREAM'
    return source.toUpperCase()
  }

  const handleDownloadEvents = useCallback(() => {
    const data = JSON.stringify(events, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `simulation-events-${new Date().toISOString()}.json`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }, [events])

  const handleDownloadLogs = useCallback(async () => {
    if (!api.logs) return
    setLogsDownloading(true)
    try {
      const allLogs: RunLogEntry[] = []
      let sinceSeq: number | undefined = undefined
      let hasMore = true
      while (hasMore) {
        const resp = await api.logs(sinceSeq)
        if (resp.items && resp.items.length > 0) {
          allLogs.push(...resp.items)
          const lastSeq = resp.items[resp.items.length - 1].seq
          sinceSeq = lastSeq
          hasMore = resp.items.length >= 200
        } else {
          hasMore = false
        }
      }
      const data = JSON.stringify(allLogs, null, 2)
      const blob = new Blob([data], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `simulation-logs-${new Date().toISOString()}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)
    } catch (error) {
      console.error('Failed to download logs:', error)
    } finally {
      setLogsDownloading(false)
    }
  }, [api])

  const activeTab: Tab = tab === 'logs' && !hasLogs ? 'events' : tab === 'chat' && !hasChat ? 'events' : tab

  return (
    <div className={`bottom-panel ${expanded ? 'bottom-panel--expanded' : ''}`}>
      {/* Collapsed bar — always visible */}
      <button
        type="button"
        className="bottom-panel-bar"
        onClick={() => setExpanded((p) => !p)}
      >
        <svg
          className={`bottom-panel-chevron ${expanded ? 'open' : ''}`}
          width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        >
          <polyline points="18 15 12 9 6 15" />
        </svg>

        <div className="bottom-panel-tabs-inline">
          <span
            className={`bottom-tab-inline ${activeTab === 'events' ? 'bottom-tab-inline--active' : ''}`}
            onClick={(e) => { e.stopPropagation(); setTab('events'); if (!expanded) setExpanded(true) }}
          >
            Events{events.length > 0 && <span className="bottom-tab-badge">{events.length}</span>}
          </span>
          {hasLogs && (
            <span
              className={`bottom-tab-inline ${activeTab === 'logs' ? 'bottom-tab-inline--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); setTab('logs'); if (!expanded) setExpanded(true) }}
            >
              Logs{logs.length > 0 && <span className="bottom-tab-badge">{logs.length}</span>}
            </span>
          )}
          {hasChat && (
            <span
              className={`bottom-tab-inline ${activeTab === 'chat' ? 'bottom-tab-inline--active' : ''}`}
              onClick={(e) => { e.stopPropagation(); setTab('chat'); if (!expanded) setExpanded(true) }}
            >
              Chat
            </span>
          )}
        </div>

        <div className="bottom-panel-actions" onClick={(e) => e.stopPropagation()}>
          {externalVersion && (
            <span className="bottom-version-chip" title={externalVersion}>
              {externalVersion}
            </span>
          )}
          {bsimVersion && (
            <span className="bottom-version-chip" title={`BioSim library version ${bsimVersion}`}>
              bsim v{bsimVersion}
            </span>
          )}
          {activeTab === 'events' && events.length > 0 && (
            <>
              <button className="btn btn-small btn-primary bottom-icon-btn" onClick={handleDownloadEvents} title="Download events">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 19h14" />
                </svg>
              </button>
              <button className="btn btn-small btn-outline" onClick={() => actions.setEvents([])}>Clear</button>
            </>
          )}
          {activeTab === 'logs' && logs.length > 0 && (
            <>
              <button
                className="btn btn-small btn-primary bottom-icon-btn"
                onClick={handleDownloadLogs}
                disabled={logsDownloading}
                title={logsDownloading ? 'Downloading...' : 'Download logs'}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 19h14" />
                </svg>
              </button>
              <button className="btn btn-small btn-outline" onClick={() => { setLogs([]); maxSeqRef.current = 0 }}>Clear</button>
            </>
          )}
        </div>
      </button>

      {/* Expanded body */}
      {expanded && (
        <div className="bottom-panel-body">
          {activeTab === 'events' && (
            <>
              {events.length === 0 ? (
                <div className="event-list empty">
                  <div className="empty-state">
                    <p>No events recorded yet</p>
                    {state.status?.phase_message && (
                      <p className="empty-state-phase">{state.status.phase_message}</p>
                    )}
                  </div>
                </div>
              ) : (
                <div className="event-list-container">
                  <div className="event-list-header">
                    <span className="event-count">{events.length} event{events.length !== 1 ? 's' : ''}</span>
                    <div className="event-controls">
                      <button
                        className={`btn btn-small ${autoScrollEvents ? 'active' : ''}`}
                        onClick={() => setAutoScrollEvents(!autoScrollEvents)}
                        title={autoScrollEvents ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
                      >
                        {'\u{1F4CC}'}
                      </button>
                    </div>
                  </div>
                  <div ref={eventsListRef} className="event-list" onScroll={onScrollEvents}>
                    {events.slice().reverse().map((ev) => (
                      <div key={ev.id} className={`event-item ${ev.event === 'phase' ? 'event-item--phase' : ''}`}>
                        <time className="event-timestamp" dateTime={ev.ts}>{ev.ts}</time>
                        <div className="event-message">
                          {ev.event === 'phase' && ev.payload?.message
                            ? String(ev.payload.message)
                            : ev.event}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'logs' && (
            <>
              {logs.length === 0 ? (
                <div className="event-list empty">
                  <div className="empty-state">
                    <p>{logsLoading ? 'Loading logs...' : 'No logs available yet'}</p>
                  </div>
                </div>
              ) : (
                <div className="event-list-container">
                  <div className="event-list-header">
                    <span className="event-count">{logs.length} log entr{logs.length !== 1 ? 'ies' : 'y'}</span>
                    <div className="event-controls">
                      <button
                        className={`btn btn-small ${autoScrollLogs ? 'active' : ''}`}
                        onClick={() => setAutoScrollLogs(!autoScrollLogs)}
                        title={autoScrollLogs ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
                      >
                        {'\u{1F4CC}'}
                      </button>
                    </div>
                  </div>
                  <div ref={logsListRef} className="event-list" onScroll={onScrollLogs}>
                    {logs.map((log) => (
                      <div key={log.id} className={`event-item log-item log-item--${log.level}`}>
                        <div className="log-item-header">
                          <time className="event-timestamp" dateTime={log.ts}>{log.ts}</time>
                          <span className={`log-source log-source--${log.source}`}>{sourceLabel(log.source)}</span>
                          <span className={levelClass(log.level)}>{log.level.toUpperCase()}</span>
                        </div>
                        {log.message && <div className="event-message">{log.message}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {activeTab === 'chat' && chatAdapter && (
            <div className="bottom-chat-wrap">
              <ChatPanel adapter={chatAdapter} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}
