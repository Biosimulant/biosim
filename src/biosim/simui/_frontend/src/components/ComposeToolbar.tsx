import React from 'react'
import { useCompose } from '../app/compose'

const ComposeToolbar: React.FC = () => {
  const { state, actions } = useCompose()

  return (
    <div className="compose-toolbar">
      <button className="btn btn-small" onClick={() => actions.setShowFileList(true)}>Open</button>
      <button className="btn btn-small" onClick={actions.onNewConfig}>New</button>
      <button
        className={`btn btn-small ${state.isDirty && state.configPath ? 'btn-primary' : ''}`}
        onClick={actions.saveConfig}
        disabled={!state.isDirty || !state.configPath}
      >
        Save
      </button>
      <button
        className={`btn btn-small ${state.configPath && !state.isApplying ? 'btn-success' : ''}`}
        onClick={actions.applyConfig}
        disabled={state.isApplying || !state.configPath}
      >
        {state.isApplying ? 'Applying...' : 'Apply'}
      </button>

      <div className="toolbar-divider" />

      <button className="btn btn-small" onClick={actions.onLayout}>Auto Layout</button>
      <button className="btn btn-small" onClick={actions.previewYaml}>YAML</button>

      <div className="toolbar-divider" />

      <div className="toolbar-view-toggle">
        <button
          className={`btn btn-small ${state.centerView === 'canvas' ? 'btn-active' : ''}`}
          onClick={() => actions.setCenterView('canvas')}
        >
          Canvas
        </button>
        <button
          className={`btn btn-small ${state.centerView === 'yaml' ? 'btn-active' : ''}`}
          onClick={() => actions.setCenterView('yaml')}
        >
          YAML
        </button>
      </div>

      <div className="toolbar-spacer" />

      {state.configPath && (
        <span className="toolbar-path">
          {state.configPath}
          {state.isDirty && <span className="toolbar-unsaved"> (unsaved)</span>}
        </span>
      )}
    </div>
  )
}

export default ComposeToolbar
