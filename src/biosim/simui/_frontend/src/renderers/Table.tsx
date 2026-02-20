import React from 'react'

type TableData = { columns?: string[]; rows?: (string | number)[][]; items?: Record<string, string | number>[] }

export default function Table({ data, isFullscreen }: { data: TableData; isFullscreen?: boolean }) {
  const cols = data.columns?.length ? data.columns : (data.items?.length ? Object.keys(data.items[0]!) : [])
  const rows = data.rows?.length ? data.rows : (data.items?.map((it) => cols.map((c) => (it as any)[c])) || [])

  const containerStyle: React.CSSProperties = isFullscreen
    ? { width: '100%', height: '100%', overflow: 'auto' }
    : { overflow: 'auto' }

  const tableStyle: React.CSSProperties = isFullscreen
    ? { width: '100%', borderCollapse: 'collapse', fontSize: '16px' }
    : { width: '100%', borderCollapse: 'collapse' }

  const thStyle: React.CSSProperties = isFullscreen
    ? { textAlign: 'left', borderBottom: '1px solid var(--border)', padding: '12px 16px', fontWeight: 600, fontSize: '18px' }
    : { textAlign: 'left', borderBottom: '1px solid var(--border)', padding: 8, fontWeight: 600 }

  const tdStyle: React.CSSProperties = isFullscreen
    ? { borderBottom: '1px solid var(--border)', padding: '10px 16px', fontSize: '16px' }
    : { borderBottom: '1px solid var(--border)', padding: '6px 8px' }

  return (
    <div className="table-container" style={containerStyle}>
      <table style={tableStyle}>
        <thead>
          <tr>{cols.map((c) => (<th key={c} style={thStyle}>{c}</th>))}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (<td key={j} style={tdStyle}>{String(v)}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
      {(!cols || cols.length === 0) && <div className="empty">No table data</div>}
    </div>
  )
}
