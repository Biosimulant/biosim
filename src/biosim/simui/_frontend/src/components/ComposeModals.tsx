import React from 'react'
import { useApi } from '../app/providers'
import { useCompose } from '../app/compose'

export function FileListModal() {
  const { state, actions } = useCompose()
  const api = useApi()

  if (!state.showFileList) return null

  const handleClick = (f: { name: string; path: string; is_dir: boolean }) => {
    if (f.is_dir) {
      api.editor.listFiles(f.path).then(actions.setFiles).catch(console.error)
    } else {
      actions.loadConfig(f.path)
    }
  }

  return (
    <div className="modal-overlay" onClick={() => actions.setShowFileList(false)}>
      <div className="modal-dialog modal-dialog--sm" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">Open Configuration</h3>
        </div>
        <div className="modal-body">
          {state.files.map((f) => (
            <div key={f.path} onClick={() => handleClick(f)} className="modal-file-item">
              <span>{f.is_dir ? '\uD83D\uDCC1' : '\uD83D\uDCC4'}</span>
              <span>{f.name}</span>
            </div>
          ))}
          {state.files.length === 0 && (
            <div className="empty-state"><p>No config files found</p></div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn btn-small" onClick={() => actions.setShowFileList(false)}>Cancel</button>
        </div>
      </div>
    </div>
  )
}

export function YamlPreviewModal() {
  const { state, actions } = useCompose()

  if (!state.showYaml) return null

  return (
    <div className="modal-overlay" onClick={() => actions.setShowYaml(false)}>
      <div className="modal-dialog modal-dialog--lg" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 className="modal-title">YAML Preview</h3>
          <button
            className="btn btn-small"
            onClick={() => navigator.clipboard.writeText(state.yamlPreview)}
          >
            Copy
          </button>
        </div>
        <pre className="modal-yaml-content">{state.yamlPreview}</pre>
        <div className="modal-footer">
          <button className="btn btn-small" onClick={() => actions.setShowYaml(false)}>Close</button>
        </div>
      </div>
    </div>
  )
}
