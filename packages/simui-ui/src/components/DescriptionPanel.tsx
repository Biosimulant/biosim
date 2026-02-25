import React, { useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface DescriptionPanelProps {
  description: string
}

export default function DescriptionPanel({ description }: DescriptionPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)

  if (!description) return null

  return (
    <div className={`description-panel ${isExpanded ? 'expanded' : 'collapsed'}`}>
      <div className="description-header" onClick={() => setIsExpanded(!isExpanded)}>
        <div className="description-title">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
          <span>About this Simulation</span>
        </div>
        <button className="expand-btn" onClick={(e) => { e.stopPropagation(); setIsExpanded(!isExpanded) }}>
          {isExpanded ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="18 15 12 9 6 15" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          )}
          <span>{isExpanded ? 'Collapse' : 'Expand'}</span>
        </button>
      </div>
      {isExpanded && (
        <div className="description-content">
          <Markdown remarkPlugins={[remarkGfm]}>{description}</Markdown>
        </div>
      )}
    </div>
  )
}
