import React from 'react'

type TableData = { columns?: string[]; rows?: (string | number)[][]; items?: Record<string, string | number>[] }

export default function Table({ data }: { data: TableData }) {
  const cols = data.columns?.length ? data.columns : (data.items?.length ? Object.keys(data.items[0]!) : [])
  const rows = data.rows?.length ? data.rows : (data.items?.map((it) => cols.map((c) => (it as any)[c])) || [])
  return (
    <div className="table-container" style={{ overflow: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>{cols.map((c) => (<th key={c} style={{ textAlign: 'left', borderBottom: '1px solid var(--border)', padding: 8, fontWeight: 600 }}>{c}</th>))}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((v, j) => (<td key={j} style={{ borderBottom: '1px solid var(--border)', padding: '6px 8px' }}>{String(v)}</td>))}
            </tr>
          ))}
        </tbody>
      </table>
      {(!cols || cols.length === 0) && <div className="empty">No table data</div>}
    </div>
  )
}
