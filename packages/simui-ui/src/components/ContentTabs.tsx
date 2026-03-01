import React, { useMemo } from 'react'
import { useUi, useModuleNames, useVisualsByModule } from '../app/ui'
import ModuleVisuals from './ModuleVisuals'
import DescriptionPanel from './DescriptionPanel'
import WiringPanel from './WiringPanel'
import ModuleChips from './ModuleChips'

export type ContentTab = 'visuals' | 'wiring' | 'about'

type Props = {
  activeTab: ContentTab
  onTabChange: (tab: ContentTab) => void
}

export default function ContentTabs({ activeTab, onTabChange }: Props) {
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

  const secondaryTabs: { id: ContentTab; label: string; show: boolean }[] = [
    { id: 'wiring', label: 'Wiring', show: hasWiring },
    { id: 'about', label: 'About', show: !!description },
  ]

  const hasSecondary = secondaryTabs.some((t) => t.show)
  const showChipsOnly = !hasSecondary && allModules.length > 1
  const hideBar = !hasSecondary && !showChipsOnly

  return (
    <>
      {/* Always render the tabs-bar div so the CSS grid child count stays
          consistent (toolbar | tabs-bar | content-area | bottom-panel). */}
      <div className={`content-tabs-bar${showChipsOnly ? ' content-tabs-bar--chips-only' : ''}${hideBar ? ' content-tabs-bar--hidden' : ''}`}>
        {hasSecondary && (
          <div className="content-tabs">
            <button
              className={`content-tab ${activeTab === 'visuals' ? 'content-tab--active' : ''}`}
              onClick={() => onTabChange('visuals')}
            >
              Visuals
            </button>
            {secondaryTabs.filter((t) => t.show).map((t) => (
              <button
                key={t.id}
                className={`content-tab ${activeTab === t.id ? 'content-tab--active' : ''}`}
                onClick={() => onTabChange(t.id)}
              >
                {t.label}
              </button>
            ))}
          </div>
        )}
        {activeTab === 'visuals' && allModules.length > 1 && <ModuleChips />}
      </div>

      <div className="content-area">
        {activeTab === 'visuals' && (
          <>
            {allModules.length === 0 ? (
              <div className="content-empty">
                <div className="empty-state">
                  <h3>No modules found</h3>
                  <p>The simulation doesn&apos;t have any modules to display yet.</p>
                </div>
              </div>
            ) : available.length === 0 ? (
              <div className="content-empty">
                <div className="empty-state">
                  <h3>No modules selected</h3>
                  <p>Select modules from the chips above to view their visualizations.</p>
                </div>
              </div>
            ) : (
              <div className="modules-grid">
                {available.map((m) => (
                  <ModuleVisuals key={m} moduleName={m} visuals={visualsByModule.get(m) || []} />
                ))}
              </div>
            )}
          </>
        )}
        {activeTab === 'wiring' && hasWiring && (
          <div className="content-wiring-wrap">
            <WiringPanel />
          </div>
        )}
        {activeTab === 'about' && description && (
          <div className="content-about-wrap">
            <DescriptionPanel description={description} />
          </div>
        )}
      </div>
    </>
  )
}
