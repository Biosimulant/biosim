import React, { useCallback, useEffect, useRef, useState } from 'react'
import { useApi } from '../app/providers'
import { useUi } from '../app/ui'
import type { RunLogEntry } from '../types/api'

type Tab = 'events' | 'logs'

export default function EventsLogsPanel() {
  const api = useApi()
  const { state, actions } = useUi()
  const events = state.events || []
  const isRunning = state.status?.running ?? false
  const bsimVersion = state.spec?.bsim_version

  const [tab, setTab] = useState<Tab>('events')
  const [logs, setLogs] = useState<RunLogEntry[]>([])
  const [logsLoading, setLogsLoading] = useState(false)
  const [logsDownloading, setLogsDownloading] = useState(false)
  const maxSeqRef = useRef(0)

  const eventsListRef = useRef<HTMLDivElement>(null)
  const logsListRef = useRef<HTMLDivElement>(null)
  const [autoScrollEvents, setAutoScrollEvents] = useState(true)
  const [autoScrollLogs, setAutoScrollLogs] = useState(true)

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
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [tab, api, isRunning])

  const hasLogs = !!api.logs
  const activeTab = hasLogs ? tab : 'events'

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

      // Fetch all logs by paginating through results
      while (hasMore) {
        const resp = await api.logs(sinceSeq)
        if (resp.items && resp.items.length > 0) {
          allLogs.push(...resp.items)
          // Check if there are more logs to fetch
          const lastSeq = resp.items[resp.items.length - 1].seq
          sinceSeq = lastSeq
          // If we got fewer items than expected, we've reached the end
          hasMore = resp.items.length >= 200 // Assuming 200 is the page size
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
      // Could add user-visible error notification here
    } finally {
      setLogsDownloading(false)
    }
  }, [api])

  return (
    <div className="footer">
      <div className="footer-content">
        <header className="footer-header">
          <div className="footer-title-section">
            {hasLogs ? (
              <div className="footer-tabs">
                <button
                  className={`footer-tab ${activeTab === 'events' ? 'footer-tab--active' : ''}`}
                  onClick={() => setTab('events')}
                >
                  Events
                  {events.length > 0 && <span className="footer-tab-badge">{events.length}</span>}
                </button>
                <button
                  className={`footer-tab ${activeTab === 'logs' ? 'footer-tab--active' : ''}`}
                  onClick={() => setTab('logs')}
                >
                  Logs
                  {logs.length > 0 && <span className="footer-tab-badge">{logs.length}</span>}
                </button>
              </div>
            ) : (
              <>
                <h2 className="footer-title">Event Log</h2>
                <div className="event-stats">
                  <div className="stat-item"><span className="stat-label">Total:</span><span className="stat-value">{events.length}</span></div>
                </div>
              </>
            )}
            {bsimVersion && (
              <span className="footer-version-chip" title={`BioSim library version ${bsimVersion}`}>
                bsim v{bsimVersion}
              </span>
            )}
          </div>
          <div className="footer-actions">
            {activeTab === 'events' && events.length > 0 && (
              <>
                <button
                  className="btn btn-small btn-primary footer-icon-button"
                  onClick={handleDownloadEvents}
                  title="Download events"
                  aria-label="Download events"
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M12 3v11m0 0 4-4m-4 4-4-4M5 19h14"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                <button className="btn btn-small btn-outline" onClick={() => actions.setEvents([])}>
                  Clear
                </button>
              </>
            )}
            {activeTab === 'logs' && logs.length > 0 && (
              <>
                <button
                  className="btn btn-small btn-primary footer-icon-button"
                  onClick={handleDownloadLogs}
                  disabled={logsDownloading}
                  title={logsDownloading ? 'Downloading logs...' : 'Download logs'}
                  aria-label={logsDownloading ? 'Downloading logs' : 'Download logs'}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path
                      d="M12 3v11m0 0 4-4m-4 4-4-4M5 19h14"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
                <button className="btn btn-small btn-outline" onClick={() => { setLogs([]); maxSeqRef.current = 0 }}>
                  Clear
                </button>
              </>
            )}
          </div>
        </header>
        <div className="footer-body">
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
                      <button className={`btn btn-small ${autoScrollEvents ? 'active' : ''}`} onClick={() => setAutoScrollEvents(!autoScrollEvents)} title={autoScrollEvents ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}>
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
                      <button className={`btn btn-small ${autoScrollLogs ? 'active' : ''}`} onClick={() => setAutoScrollLogs(!autoScrollLogs)} title={autoScrollLogs ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}>
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
        </div>
      </div>
    </div>
  )
}
