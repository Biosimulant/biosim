import React, { useEffect, useRef, useState } from 'react'
import { useUi } from '../app/ui'

export default function Footer() {
  const { state, actions } = useUi()
  const events = state.events || []
  const listRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)

  useEffect(() => {
    if (autoScroll && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [events, autoScroll])

  const onScroll = () => {
    if (!listRef.current) return
    const { scrollTop, scrollHeight, clientHeight } = listRef.current
    const atBottom = scrollTop + clientHeight >= scrollHeight - 10
    setAutoScroll(atBottom)
  }

  return (
    <div className="footer">
      <div className="footer-content">
        <header className="footer-header">
          <div className="footer-title-section">
            <h2 className="footer-title">Event Log</h2>
            <div className="event-stats">
              <div className="stat-item"><span className="stat-label">Total:</span><span className="stat-value">{events.length}</span></div>
            </div>
          </div>
          <div className="footer-actions">
            {events.length > 0 && <button className="btn btn-small btn-outline" onClick={() => actions.setEvents([])}>Clear</button>}
          </div>
        </header>
        <div className="footer-body">
          {events.length === 0 ? (
            <div className="event-list empty"><div className="empty-state"><p>No events recorded yet</p></div></div>
          ) : (
            <div className="event-list-container">
              <div className="event-list-header">
                <span className="event-count">{events.length} event{events.length !== 1 ? 's' : ''}</span>
                <div className="event-controls">
                  <button className={`btn btn-small ${autoScroll ? 'active' : ''}`} onClick={() => setAutoScroll(!autoScroll)} title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}>📌</button>
                  <button className="btn btn-small" onClick={() => { if (listRef.current) { listRef.current.scrollTop = listRef.current.scrollHeight; setAutoScroll(true) } }} title="Scroll to bottom">⬇️</button>
                </div>
              </div>
              <div ref={listRef} className="event-list" onScroll={onScroll}>
                {events.slice().reverse().map((ev) => (
                  <div key={ev.id} className="event-item">
                    <time className="event-timestamp" dateTime={ev.ts}>{ev.ts}</time>
                    <div className="event-message">{ev.event}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
