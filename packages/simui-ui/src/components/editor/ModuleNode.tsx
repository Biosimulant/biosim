import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

export interface ModuleNodeData {
  label: string
  moduleType: string
  args: Record<string, unknown>
  inputs: string[]
  outputs: string[]
  selected?: boolean
  [key: string]: unknown
}

const ModuleNode: React.FC<NodeProps> = ({ data, selected }) => {
  const nodeData = data as unknown as ModuleNodeData
  const { label, moduleType, inputs, outputs } = nodeData

  // Extract just the class name from the full path
  const className = moduleType.split('.').pop() || moduleType

  // Determine category for color coding
  const category = moduleType.includes('.neuro.') ? 'neuro' : moduleType.includes('.ecology.') ? 'ecology' : 'custom'

  const categoryColors: Record<string, { bg: string; border: string; header: string; text: string }> = {
    neuro: { bg: 'var(--module-neuro-bg)', border: 'var(--module-neuro-border)', header: 'var(--module-neuro-header)', text: 'var(--module-neuro-text)' },
    ecology: { bg: 'var(--module-ecology-bg)', border: 'var(--module-ecology-border)', header: 'var(--module-ecology-header)', text: 'var(--module-ecology-text)' },
    custom: { bg: 'var(--module-custom-bg)', border: 'var(--module-custom-border)', header: 'var(--module-custom-header)', text: 'var(--module-custom-text)' },
  }

  const colors = categoryColors[category]

  return (
    <div
      className="module-node"
      style={{
        background: colors.bg,
        border: `2px solid ${selected ? 'var(--warning)' : colors.border}`,
        borderRadius: '8px',
        minWidth: '180px',
        boxShadow: selected ? '0 0 0 2px color-mix(in srgb, var(--warning) 45%, transparent)' : '0 8px 18px rgba(15, 23, 42, 0.16)',
        fontFamily: 'ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif',
      }}
    >
      {/* Header */}
      <div
        style={{
          background: colors.header,
          color: '#fff',
          padding: '10px 14px',
          borderRadius: '6px 6px 0 0',
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
                  background: 'var(--muted)',
                  border: '2px solid var(--surface)',
                  left: '-6px',
                }}
              />
              <span style={{ fontSize: '12px', color: colors.text, fontWeight: 500 }}>{port}</span>
            </div>
          ))}
          {inputs.length === 0 && (
              <div style={{ paddingLeft: '14px', fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
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
                  border: '2px solid var(--surface)',
                  right: '-6px',
                }}
              />
            </div>
          ))}
          {outputs.length === 0 && (
              <div style={{ paddingRight: '14px', fontSize: '12px', color: 'var(--muted)', fontStyle: 'italic' }}>
              no outputs
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default memo(ModuleNode)
