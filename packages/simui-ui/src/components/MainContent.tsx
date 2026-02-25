import React, { useMemo } from 'react'
import { useUi, useModuleNames, useVisualsByModule } from '../app/ui'
import ModuleVisuals from './ModuleVisuals'
import DescriptionPanel from './DescriptionPanel'
import WiringPanel from './WiringPanel'

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

export default function MainContent() {
  const { state } = useUi()
  const allModules = useModuleNames()
  const available = useMemo(
    () => (state.visibleModules.size ? allModules.filter((m) => state.visibleModules.has(m)) : allModules),
    [allModules, state.visibleModules]
  )
  const visualsByModule = useVisualsByModule()
  const description = state.spec?.description
  const hasWiring = useMemo(
    () => Boolean(state.spec?.controls?.some((c) => (c as any).type === 'json' && (c as any).name === 'wiring')),
    [state.spec]
  )

  const infoPanels = (
    <>
      {description && <DescriptionPanel description={description} />}
      {hasWiring && <WiringPanel />}
    </>
  )

  if (allModules.length === 0) {
    return (
      <div className="main-content">
        {infoPanels}
        <EmptyState message="No modules found" description="The simulation doesn't have any modules to display yet." />
      </div>
    )
  }

  if (available.length === 0) {
    return (
      <div className="main-content">
        {infoPanels}
        <EmptyState message="No modules selected" description="Select modules from the sidebar to view their visualizations." />
      </div>
    )
  }

  return (
    <div className="main-content">
      {infoPanels}
      <div className="modules-grid">
        {available.map((m) => (
          <ModuleVisuals key={m} moduleName={m} visuals={visualsByModule.get(m) || []} />
        ))}
      </div>
    </div>
  )
}
