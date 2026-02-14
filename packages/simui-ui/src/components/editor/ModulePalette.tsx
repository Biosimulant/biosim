import React, { useState } from 'react'
import type { ModuleRegistry, ModuleSpec } from '../../lib/api'

interface ModulePaletteProps {
  registry: ModuleRegistry | null
  onDragStart: (event: React.DragEvent, moduleType: string, spec: ModuleSpec) => void
}

const ModulePalette: React.FC<ModulePaletteProps> = ({ registry, onDragStart }) => {
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['neuro', 'ecology']))
  const [search, setSearch] = useState('')

  // Dark theme colors
  const bg = '#0f1628'
  const surface = '#11182b'
  const text = '#e6eaf2'
  const muted = '#9aa6c1'
  const border = '#1e2a44'

  if (!registry) {
    return (
      <div className="module-palette" style={{ padding: '16px', background: surface, color: muted }}>
        <div>Loading modules...</div>
      </div>
    )
  }

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories)
    if (newExpanded.has(category)) {
      newExpanded.delete(category)
    } else {
      newExpanded.add(category)
    }
    setExpandedCategories(newExpanded)
  }

  const categoryColors: Record<string, string> = {
    neuro: '#3b82f6',
    ecology: '#22c55e',
    custom: '#a855f7',
  }

  const filteredCategories = Object.entries(registry.categories).map(([category, paths]) => {
    const modules = paths
      .map(path => ({ path, spec: registry.modules[path] }))
      .filter(({ spec }) => {
        if (!spec) return false
        if (!search) return true
        const searchLower = search.toLowerCase()
        return (
          spec.name.toLowerCase().includes(searchLower) ||
          spec.description?.toLowerCase().includes(searchLower) ||
          category.toLowerCase().includes(searchLower)
        )
      })
    return { category, modules }
  }).filter(({ modules }) => modules.length > 0)

  return (
    <div className="module-palette" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: surface, fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
      <div style={{ padding: '14px', borderBottom: `1px solid ${border}` }}>
        <h3 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 600, color: text }}>Modules</h3>
        <input
          type="text"
          placeholder="Search modules..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            width: '100%',
            padding: '8px 12px',
            border: `1px solid ${border}`,
            borderRadius: '8px',
            fontSize: '13px',
            background: bg,
            color: text,
          }}
        />
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '8px' }}>
        {filteredCategories.map(({ category, modules }) => (
          <div key={category} style={{ marginBottom: '8px' }}>
            <button
              onClick={() => toggleCategory(category)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 600,
                color: text,
                textAlign: 'left',
              }}
            >
              <span style={{ transform: expandedCategories.has(category) ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform 0.2s', color: muted }}>
                ▶
              </span>
              <span
                style={{
                  width: '10px',
                  height: '10px',
                  borderRadius: '50%',
                  background: categoryColors[category] || '#666',
                }}
              />
              {category.charAt(0).toUpperCase() + category.slice(1)}
              <span style={{ marginLeft: 'auto', fontSize: '12px', color: muted }}>
                {modules.length}
              </span>
            </button>

            {expandedCategories.has(category) && (
              <div style={{ paddingLeft: '16px' }}>
                {modules.map(({ path, spec }) => (
                  <div
                    key={path}
                    draggable
                    onDragStart={(e) => onDragStart(e, path, spec)}
                    style={{
                      padding: '10px 12px',
                      marginBottom: '6px',
                      background: bg,
                      border: `1px solid ${border}`,
                      borderRadius: '8px',
                      cursor: 'grab',
                      fontSize: '13px',
                    }}
                    title={spec.description || path}
                  >
                    <div style={{ fontWeight: 500, color: text }}>{spec.name}</div>
                    <div style={{ fontSize: '11px', color: muted, marginTop: '4px' }}>
                      {spec.inputs.length > 0 && <span>in: {spec.inputs.join(', ')}</span>}
                      {spec.inputs.length > 0 && spec.outputs.length > 0 && ' | '}
                      {spec.outputs.length > 0 && <span>out: {spec.outputs.join(', ')}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {filteredCategories.length === 0 && (
          <div style={{ padding: '16px', textAlign: 'center', color: muted, fontSize: '13px' }}>
            No modules found
          </div>
        )}
      </div>

      <div style={{ padding: '10px 14px', borderTop: `1px solid ${border}`, fontSize: '12px', color: muted }}>
        Drag modules to canvas
      </div>
    </div>
  )
}

export default ModulePalette
