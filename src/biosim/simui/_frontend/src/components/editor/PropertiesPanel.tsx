import React from 'react'
import type { Node } from '@xyflow/react'
import type { ModuleNodeData } from './ModuleNode'
import type { ModuleRegistry } from '../../lib/api'

interface PropertiesPanelProps {
  selectedNode: Node | null
  registry: ModuleRegistry | null
  onUpdateNode: (nodeId: string, args: Record<string, unknown>) => void
  onDeleteNode: (nodeId: string) => void
  onRenameNode: (nodeId: string, newId: string) => void
}

const PropertiesPanel: React.FC<PropertiesPanelProps> = ({
  selectedNode,
  registry,
  onUpdateNode,
  onDeleteNode,
  onRenameNode,
}) => {
  // Dark theme colors
  const bg = '#0f1628'
  const surface = '#11182b'
  const text = '#e6eaf2'
  const muted = '#9aa6c1'
  const border = '#1e2a44'
  const accent = '#22d3ee'

  if (!selectedNode) {
    return (
      <div className="properties-panel" style={{ padding: '16px', background: surface, color: muted, fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
        <h3 style={{ margin: '0 0 10px 0', fontSize: '14px', fontWeight: 600, color: text }}>Properties</h3>
        <p style={{ fontSize: '13px', color: muted }}>Select a node to edit its properties</p>
      </div>
    )
  }

  const nodeData = selectedNode.data as ModuleNodeData
  const moduleSpec = registry?.modules[nodeData.moduleType]

  const handleArgChange = (argName: string, value: unknown) => {
    const newArgs = { ...nodeData.args, [argName]: value }
    onUpdateNode(selectedNode.id, newArgs)
  }

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newId = e.target.value.trim()
    if (newId && newId !== selectedNode.id) {
      onRenameNode(selectedNode.id, newId)
    }
  }

  const parseValue = (value: string, type: string): unknown => {
    if (type === 'int' || type === 'float' || type === 'number') {
      const num = parseFloat(value)
      return isNaN(num) ? 0 : num
    }
    if (type === 'bool' || type === 'boolean') {
      return value === 'true' || value === '1'
    }
    if (type === 'list' || type === 'List') {
      try {
        return JSON.parse(value)
      } catch {
        return []
      }
    }
    return value
  }

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return ''
    if (typeof value === 'object') return JSON.stringify(value)
    return String(value)
  }

  const inputStyle = {
    width: '100%',
    padding: '8px 12px',
    border: `1px solid ${border}`,
    borderRadius: '8px',
    fontSize: '13px',
    background: bg,
    color: text,
  }

  return (
    <div className="properties-panel" style={{ height: '100%', display: 'flex', flexDirection: 'column', background: surface, fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif' }}>
      <div style={{ padding: '14px', borderBottom: `1px solid ${border}` }}>
        <h3 style={{ margin: '0', fontSize: '14px', fontWeight: 600, color: text }}>Properties</h3>
      </div>

      <div style={{ flex: 1, overflow: 'auto', padding: '14px' }}>
        {/* Node ID */}
        <div style={{ marginBottom: '18px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: text }}>
            Node ID
          </label>
          <input
            type="text"
            defaultValue={selectedNode.id}
            onBlur={handleNameChange}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.currentTarget.blur()
              }
            }}
            style={inputStyle}
          />
        </div>

        {/* Module Type */}
        <div style={{ marginBottom: '18px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 500, marginBottom: '6px', color: text }}>
            Module Type
          </label>
          <div style={{ padding: '8px 12px', background: bg, borderRadius: '8px', fontSize: '12px', color: muted, border: `1px solid ${border}` }}>
            {nodeData.moduleType}
          </div>
        </div>

        {/* Module Description */}
        {moduleSpec?.description && (
          <div style={{ marginBottom: '18px', padding: '10px', background: '#0c2135', borderRadius: '8px', fontSize: '12px', color: accent, border: `1px solid ${border}` }}>
            {moduleSpec.description.split('\n')[0]}
          </div>
        )}

        {/* Arguments */}
        <div style={{ marginBottom: '10px' }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '10px', color: text }}>
            Arguments
          </label>

          {moduleSpec?.args.map((arg) => {
            const currentValue = nodeData.args[arg.name] ?? arg.default
            const inputType = arg.type === 'bool' || arg.type === 'boolean' ? 'checkbox' : 'text'

            return (
              <div key={arg.name} style={{ marginBottom: '14px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', marginBottom: '6px', color: muted }}>
                  <span style={{ fontWeight: 500, color: text }}>{arg.name}</span>
                  <span style={{ color: muted }}>({arg.type})</span>
                  {arg.required && <span style={{ color: '#ef4444' }}>*</span>}
                </label>

                {inputType === 'checkbox' ? (
                  <input
                    type="checkbox"
                    checked={Boolean(currentValue)}
                    onChange={(e) => handleArgChange(arg.name, e.target.checked)}
                    style={{ width: '18px', height: '18px', accentColor: accent }}
                  />
                ) : arg.options ? (
                  <select
                    value={String(currentValue)}
                    onChange={(e) => handleArgChange(arg.name, parseValue(e.target.value, arg.type))}
                    style={inputStyle}
                  >
                    {arg.options.map((opt) => (
                      <option key={String(opt)} value={String(opt)}>
                        {String(opt)}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={formatValue(currentValue)}
                    onChange={(e) => handleArgChange(arg.name, parseValue(e.target.value, arg.type))}
                    placeholder={arg.default !== null ? `Default: ${formatValue(arg.default)}` : ''}
                    style={inputStyle}
                  />
                )}

                {arg.description && (
                  <div style={{ fontSize: '11px', color: muted, marginTop: '4px' }}>
                    {arg.description}
                  </div>
                )}
              </div>
            )
          })}

          {(!moduleSpec || moduleSpec.args.length === 0) && (
            <div style={{ fontSize: '13px', color: muted, fontStyle: 'italic' }}>
              No configurable arguments
            </div>
          )}
        </div>

        {/* Ports info */}
        <div style={{ marginTop: '18px', paddingTop: '18px', borderTop: `1px solid ${border}` }}>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, marginBottom: '10px', color: text }}>
            Ports
          </label>
          <div style={{ display: 'flex', gap: '20px' }}>
            <div>
              <div style={{ fontSize: '12px', color: muted, marginBottom: '6px' }}>Inputs</div>
              {nodeData.inputs.length > 0 ? (
                nodeData.inputs.map((port) => (
                  <div key={port} style={{ fontSize: '12px', color: text }}>
                    {port}
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '12px', color: muted, fontStyle: 'italic' }}>none</div>
              )}
            </div>
            <div>
              <div style={{ fontSize: '12px', color: muted, marginBottom: '6px' }}>Outputs</div>
              {nodeData.outputs.length > 0 ? (
                nodeData.outputs.map((port) => (
                  <div key={port} style={{ fontSize: '12px', color: text }}>
                    {port}
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '12px', color: muted, fontStyle: 'italic' }}>none</div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Delete button */}
      <div style={{ padding: '14px', borderTop: `1px solid ${border}` }}>
        <button
          onClick={() => onDeleteNode(selectedNode.id)}
          style={{
            width: '100%',
            padding: '10px',
            background: '#3b1c1c',
            border: '1px solid #7f1d1d',
            borderRadius: '8px',
            color: '#fca5a5',
            fontSize: '13px',
            fontWeight: 500,
            cursor: 'pointer',
          }}
        >
          Delete Node
        </button>
      </div>
    </div>
  )
}

export default PropertiesPanel
