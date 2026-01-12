import React, { useEffect, useMemo } from 'react'
import { useUi, useModuleNames, useVisualsByModule } from '../app/ui'
import ModuleVisuals from './ModuleVisuals'

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

  if (allModules.length === 0) {
    return (
      <div className="main-content">
        <EmptyState message="No modules found" description="The simulation doesn't have any modules to display yet." />
      </div>
    )
  }

  if (available.length === 0) {
    return (
      <div className="main-content">
        <EmptyState message="No modules selected" description="Select modules from the sidebar to view their visualizations." />
      </div>
    )
  }

  return (
    <div className="main-content">
      <div className="modules-grid">
        {available.map((m) => (
          <ModuleVisuals key={m} moduleName={m} visuals={visualsByModule.get(m) || []} />
        ))}
      </div>
    </div>
  )
}
