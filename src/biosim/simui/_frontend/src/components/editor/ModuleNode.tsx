import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

export interface ModuleNodeData {
  label: string
  moduleType: string
  args: Record<string, unknown>
  inputs: string[]
  outputs: string[]
  selected?: boolean
}

const ModuleNode: React.FC<NodeProps> = ({ data, selected }) => {
  const nodeData = data as ModuleNodeData
  const { label, moduleType, inputs, outputs } = nodeData

  // Extract just the class name from the full path
  const className = moduleType.split('.').pop() || moduleType

  // Determine category for color coding
  const category = moduleType.includes('.neuro.') ? 'neuro' : moduleType.includes('.ecology.') ? 'ecology' : 'custom'

  // Dark theme colors matching globals.css
  const categoryColors: Record<string, { bg: string; border: string; header: string; text: string }> = {
    neuro: { bg: '#1a2744', border: '#3b82f6', header: '#2563eb', text: '#e0f2fe' },
    ecology: { bg: '#14352a', border: '#22c55e', header: '#16a34a', text: '#dcfce7' },
    custom: { bg: '#2e1a47', border: '#a855f7', header: '#9333ea', text: '#f3e8ff' },
  }

  const colors = categoryColors[category]

  return (
    <div
      className="module-node"
      style={{
        background: colors.bg,
        border: `2px solid ${selected ? '#fbbf24' : colors.border}`,
        borderRadius: '10px',
        minWidth: '180px',
        boxShadow: selected ? '0 0 0 2px #fbbf24' : '0 4px 16px rgba(0,0,0,0.5)',
        fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
      }}
    >
      {/* Header */}
      <div
        style={{
          background: colors.header,
          color: '#fff',
          padding: '10px 14px',
          borderRadius: '8px 8px 0 0',
          fontWeight: 600,
          fontSize: '14px',
          letterSpacing: '0.01em',
        }}
      >
        {label}
      </div>

      {/* Class name */}
      <div
        style={{
          padding: '6px 14px',
          fontSize: '12px',
          color: colors.text,
          borderBottom: `1px solid ${colors.border}50`,
          opacity: 0.85,
        }}
      >
        {className}
      </div>

      {/* Ports container */}
      <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0' }}>
        {/* Input ports */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {inputs.map((port) => (
            <div key={port} style={{ position: 'relative', paddingLeft: '14px' }}>
              <Handle
                type="target"
                position={Position.Left}
                id={port}
                style={{
                  width: '12px',
                  height: '12px',
                  background: '#6b7280',
                  border: '2px solid #1a2744',
                  left: '-6px',
                }}
              />
              <span style={{ fontSize: '12px', color: colors.text, fontWeight: 500 }}>{port}</span>
            </div>
          ))}
          {inputs.length === 0 && (
            <div style={{ paddingLeft: '14px', fontSize: '12px', color: '#9aa6c1', fontStyle: 'italic' }}>
              no inputs
            </div>
          )}
        </div>

        {/* Output ports */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'flex-end' }}>
          {outputs.map((port) => (
            <div key={port} style={{ position: 'relative', paddingRight: '14px' }}>
              <span style={{ fontSize: '12px', color: colors.text, fontWeight: 500 }}>{port}</span>
              <Handle
                type="source"
                position={Position.Right}
                id={port}
                style={{
                  width: '12px',
                  height: '12px',
                  background: colors.header,
                  border: '2px solid #1a2744',
                  right: '-6px',
                }}
              />
            </div>
          ))}
          {outputs.length === 0 && (
            <div style={{ paddingRight: '14px', fontSize: '12px', color: '#9aa6c1', fontStyle: 'italic' }}>
              no outputs
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default memo(ModuleNode)
