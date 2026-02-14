import React, { useMemo, useState } from 'react'
import { useUi, useModuleNames, useVisualsByModule } from '../app/ui'
import type { ChatAdapter } from '../types/chat'
import ModuleVisuals from './ModuleVisuals'
import DescriptionPanel from './DescriptionPanel'
import WiringPanel from './WiringPanel'
import ChatPanel from './ChatPanel'

function EmptyState({ message, description }: { message: string; description?: string }) {
  return (
    <div className="empty-state">
      <div className="empty-content">
        <h3>{message}</h3>
        {description && <p>{description}</p>}
      </div>
    </div>
  )
}

export default function MainContent({ chatAdapter }: { chatAdapter?: ChatAdapter }) {
  const { state } = useUi()
  const allModules = useModuleNames()
  const available = useMemo(
    () => (state.visibleModules.size ? allModules.filter((m) => state.visibleModules.has(m)) : allModules),
    [allModules, state.visibleModules]
  )
  const visualsByModule = useVisualsByModule()
  const description = state.spec?.description
  const hasChat = Boolean(chatAdapter)
  const hasWiring = useMemo(
    () => Boolean(state.spec?.controls?.some((c) => (c as any).type === 'json' && (c as any).name === 'wiring')),
    [state.spec]
  )
  const [activeTab, setActiveTab] = useState<'visuals' | 'wiring' | 'chat'>('visuals')

  const visualsContent = (() => {
    if (allModules.length === 0) {
      return (
        <>
          {description && <DescriptionPanel description={description} />}
          <EmptyState message="No modules found" description="The simulation doesn't have any modules to display yet." />
        </>
      )
    }
    if (available.length === 0) {
      return (
        <>
          {description && <DescriptionPanel description={description} />}
          <EmptyState message="No modules selected" description="Select modules from the sidebar to view their visualizations." />
        </>
      )
    }
    return (
      <>
        {description && <DescriptionPanel description={description} />}
        <div className="modules-grid">
          {available.map((m) => (
            <ModuleVisuals key={m} moduleName={m} visuals={visualsByModule.get(m) || []} />
          ))}
        </div>
      </>
    )
  })()

  return (
    <div className="main-content">
      <div className="main-tabs">
        <button
          type="button"
          className={`main-tab ${activeTab === 'visuals' ? 'active' : ''}`}
          onClick={() => setActiveTab('visuals')}
        >
          Visualizations
        </button>
        {hasWiring && (
          <button
            type="button"
            className={`main-tab ${activeTab === 'wiring' ? 'active' : ''}`}
            onClick={() => setActiveTab('wiring')}
          >
            Wiring
          </button>
        )}
        {hasChat && (
          <button
            type="button"
            className={`main-tab ${activeTab === 'chat' ? 'active' : ''}`}
            onClick={() => setActiveTab('chat')}
          >
            Chat
          </button>
        )}
      </div>
      {activeTab === 'chat' && chatAdapter && <ChatPanel adapter={chatAdapter} />}
      {activeTab === 'wiring' && hasWiring && <WiringPanel />}
      {activeTab === 'visuals' && visualsContent}
    </div>
  )
}
