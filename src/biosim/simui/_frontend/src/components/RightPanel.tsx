import React, { useState } from 'react'
import MainContent from './MainContent'
import Footer from './Footer'
import { PropertiesPanel } from './editor'
import { useCompose } from '../app/compose'

type Tab = 'results' | 'logs' | 'properties'

const RightPanel: React.FC<{ isOpen: boolean; onToggle: () => void }> = ({ isOpen, onToggle }) => {
  const { state, actions } = useCompose()
  const [activeTab, setActiveTab] = useState<Tab>('results')

  // Auto-switch to properties tab when a node is selected
  React.useEffect(() => {
    if (state.selectedNode) {
      setActiveTab('properties')
    }
  }, [state.selectedNode])

  return (
    <div className={`right-panel ${isOpen ? 'right-panel--open' : 'right-panel--closed'}`}>
      <button className="right-panel-toggle" onClick={onToggle} title={isOpen ? 'Collapse panel' : 'Expand panel'}>
        {isOpen ? '\u25B6' : '\u25C0'}
      </button>

      {isOpen && (
        <div className="right-panel-content">
          <div className="right-panel-tabs">
            <button
              className={`right-panel-tab ${activeTab === 'results' ? 'right-panel-tab--active' : ''}`}
              onClick={() => setActiveTab('results')}
            >
              Results
            </button>
            <button
              className={`right-panel-tab ${activeTab === 'logs' ? 'right-panel-tab--active' : ''}`}
              onClick={() => setActiveTab('logs')}
            >
              Logs
            </button>
            <button
              className={`right-panel-tab ${activeTab === 'properties' ? 'right-panel-tab--active' : ''}`}
              onClick={() => setActiveTab('properties')}
            >
              Properties
            </button>
          </div>

          <div className="right-panel-body">
            {activeTab === 'results' && <MainContent />}
            {activeTab === 'logs' && <Footer />}
            {activeTab === 'properties' && (
              <PropertiesPanel
                selectedNode={state.selectedNode}
                registry={state.registry}
                onUpdateNode={actions.onUpdateNode}
                onDeleteNode={actions.onDeleteNode}
                onRenameNode={actions.onRenameNode}
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default RightPanel
