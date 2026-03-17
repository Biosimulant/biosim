import React, { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  type NodeTypes,
  BackgroundVariant,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import ModuleNode from './editor/ModuleNode'
import { useCompose } from '../app/compose'

const ComposeCanvas: React.FC = () => {
  const { state, actions } = useCompose()
  const nodeTypes: NodeTypes = useMemo(() => ({ moduleNode: ModuleNode }), [])

  return (
    <div
      ref={actions.reactFlowWrapper as React.RefObject<HTMLDivElement>}
      className="compose-canvas"
      onDragOver={actions.onDragOver}
      onDrop={actions.onDrop}
    >
      <ReactFlow
        nodes={state.nodes}
        edges={state.edges}
        onNodesChange={actions.onNodesChange}
        onEdgesChange={actions.onEdgesChange}
        onConnect={actions.onConnect}
        onSelectionChange={actions.onSelectionChange}
        onNodeDragStop={actions.onNodeDragStop}
        nodeTypes={nodeTypes}
        fitView
        snapToGrid
        snapGrid={[15, 15]}
        deleteKeyCode={['Backspace', 'Delete']}
        onNodesDelete={() => actions.setIsDirty(true)}
        onEdgesDelete={() => actions.setIsDirty(true)}
        style={{ background: 'var(--bg)' }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
        <Controls className="compose-controls" />
        <MiniMap
          nodeColor={(node) => {
            const data = node.data as Record<string, unknown>
            const moduleType = (data.moduleType as string) || ''
            if (moduleType.includes('.neuro.')) return 'var(--primary)'
            if (moduleType.includes('.ecology.')) return '#22c55e'
            return '#a855f7'
          }}
          maskColor="rgba(11, 16, 32, 0.7)"
          className="compose-minimap"
        />
        {state.meta.title && (
          <Panel position="top-center">
            <div className="compose-title-badge">
              {state.meta.title}
            </div>
          </Panel>
        )}
      </ReactFlow>
    </div>
  )
}

export default ComposeCanvas
