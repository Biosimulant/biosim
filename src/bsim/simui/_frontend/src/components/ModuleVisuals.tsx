import React, { memo, useState, useCallback } from 'react'
import type { VisualSpec } from '../types/api'
import Timeseries from '../renderers/Timeseries'
import Bar from '../renderers/Bar'
import Table from '../renderers/Table'
import ImageView from '../renderers/ImageView'
import Graph from '../renderers/Graph'

const RENDERERS: Record<string, React.ComponentType<{ data: any; isFullscreen?: boolean }>> = {
  timeseries: Timeseries,
  bar: Bar,
  table: Table,
  image: ImageView,
  graph: Graph,
}

function FullscreenButton({ isFullscreen, onClick }: { isFullscreen: boolean; onClick: () => void }) {
  return (
    <button className="btn btn-small btn-outline fullscreen-btn" onClick={onClick} title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}>
      {isFullscreen ? (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M8 3v3a2 2 0 0 1-2 2H3m18 0h-3a2 2 0 0 1-2-2V3m0 18v-3a2 2 0 0 1 2-2h3M3 16h3a2 2 0 0 1 2 2v3" />
        </svg>
      ) : (
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
        </svg>
      )}
    </button>
  )
}

function VisualizationCard({ visual, index }: { visual: VisualSpec; index: number }) {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const Renderer = RENDERERS[visual.render]

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(prev => !prev)
  }, [])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && isFullscreen) {
      setIsFullscreen(false)
    }
  }, [isFullscreen])

  if (!Renderer) {
    return (
      <div className="visualization-card error">
        <div className="card-header">
          <h4 className="card-title">Unknown Renderer</h4>
          <span className="card-type error">{visual.render}</span>
        </div>
        <div className="card-content">
          <div className="error-message">
            <p>Renderer type "{visual.render}" is not supported.</p>
          </div>
        </div>
      </div>
    )
  }

  const title = (visual.data as any)?.title || `${visual.render.charAt(0).toUpperCase() + visual.render.slice(1)} #${index + 1}`

  const cardContent = (
    <>
      <div className="card-header">
        <h4 className="card-title">{title}</h4>
        <div className="card-actions">
          <span className="card-type">{visual.render}</span>
          <FullscreenButton isFullscreen={isFullscreen} onClick={toggleFullscreen} />
        </div>
      </div>
      <div className="card-content">
        <Renderer data={visual.data} isFullscreen={isFullscreen} />
      </div>
    </>
  )

  if (isFullscreen) {
    return (
      <>
        <div className="visualization-card placeholder" />
        <div className="fullscreen-overlay" onClick={toggleFullscreen} onKeyDown={handleKeyDown} tabIndex={0}>
          <div className="fullscreen-card" onClick={e => e.stopPropagation()}>
            {cardContent}
          </div>
        </div>
      </>
    )
  }

  return <div className="visualization-card">{cardContent}</div>
}

function ModuleHeader({ moduleName, visualCount }: { moduleName: string; visualCount: number }) {
  return (
    <header className="module-header">
      <div className="module-info">
        <h3 className="module-title">{moduleName}</h3>
        <span className="module-meta">{visualCount} visualization{visualCount !== 1 ? 's' : ''}</span>
      </div>
    </header>
  )
}

function ModuleVisuals({ moduleName, visuals }: { moduleName: string; visuals: VisualSpec[] }) {
  if (!visuals || visuals.length === 0) {
    return (
      <div className="module-visuals">
        <ModuleHeader moduleName={moduleName} visualCount={0} />
        <div className="empty-state"><p>No visualizations available for this module</p></div>
      </div>
    )
  }
  return (
    <div className="module-visuals">
      <ModuleHeader moduleName={moduleName} visualCount={visuals.length} />
      <div className="visualizations-grid">
        {visuals.map((v, i) => (
          <VisualizationCard key={`${moduleName}-${v.render}-${i}`} visual={v} index={i} />
        ))}
      </div>
    </div>
  )
}

export default memo(ModuleVisuals)
