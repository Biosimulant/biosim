import React, { useEffect, useMemo, useRef, useState } from 'react'
import { Viewer } from 'molstar/lib/apps/viewer/app'
import 'molstar/build/viewer/molstar.css'
import type { Structure3DAnnotation, Structure3DData, StructureSource } from '../types/api'
import { resolveConfig } from '../lib/config'

type Structure3DProps = {
  data: Record<string, unknown>
  isFullscreen?: boolean
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeSource(value: unknown): StructureSource | null {
  if (!isRecord(value) || typeof value.kind !== 'string') return null
  if (value.kind === 'url' && typeof value.url === 'string' && value.url.trim()) {
    return { kind: 'url', url: value.url }
  }
  if (value.kind === 'artifact' && typeof value.artifact_id === 'string' && value.artifact_id.trim()) {
    return { kind: 'artifact', artifact_id: value.artifact_id }
  }
  return null
}

function normalizeAnnotations(value: unknown): Structure3DAnnotation[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((entry) => {
    if (!isRecord(entry) || typeof entry.label !== 'string') return []
    const annotationValue = entry.value
    if (
      typeof annotationValue !== 'string'
      && typeof annotationValue !== 'number'
      && typeof annotationValue !== 'boolean'
    ) {
      return []
    }
    return [{ label: entry.label, value: annotationValue }]
  })
}

function normalizeStructureData(value: Record<string, unknown>): Structure3DData | null {
  const source = normalizeSource(value.source)
  const format = value.format === 'pdb' ? 'pdb' : value.format === 'mmcif' ? 'mmcif' : null
  if (!source || !format) return null

  return {
    title: typeof value.title === 'string' ? value.title : undefined,
    source,
    format,
    description: typeof value.description === 'string' ? value.description : undefined,
    annotations: normalizeAnnotations(value.annotations),
    initial_view: isRecord(value.initial_view) ? value.initial_view : undefined,
  }
}

function resolveStructureUrl(source: StructureSource): string {
  if (source.kind === 'url') return source.url
  const baseUrl = resolveConfig().baseUrl
  const artifactPath = `/api/artifacts/${encodeURIComponent(source.artifact_id)}`
  return `${baseUrl}${artifactPath}`
}

export default function Structure3D({ data, isFullscreen = false }: Structure3DProps) {
  const normalized = useMemo(() => normalizeStructureData(data), [data])
  const containerRef = useRef<HTMLDivElement | null>(null)
  const viewerRef = useRef<Viewer | null>(null)
  const [viewerReady, setViewerReady] = useState(false)
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    let cancelled = false

    async function initViewer() {
      try {
        const viewer = await Viewer.create(containerRef.current!, {
          layoutIsExpanded: false,
          layoutShowControls: false,
          viewportShowExpand: false,
          collapseLeftPanel: true,
          collapseRightPanel: true,
        })
        if (cancelled) {
          viewer.dispose()
          return
        }
        viewerRef.current = viewer
        setViewerReady(true)
      } catch (initError) {
        if (cancelled) return
        setStatus('error')
        setError(initError instanceof Error ? initError.message : 'Failed to initialize Mol* viewer')
      }
    }

    void initViewer()
    return () => {
      cancelled = true
      const viewer = viewerRef.current
      viewerRef.current = null
      setViewerReady(false)
      viewer?.dispose()
    }
  }, [])

  useEffect(() => {
    if (!normalized) {
      setStatus('error')
      setError('Structure payload is missing a supported source or format.')
      return
    }

    if (!viewerReady) return
    const viewer = viewerRef.current
    const structure = normalized
    if (!viewer) return

    let cancelled = false

    async function loadStructure() {
      setStatus('loading')
      setError(null)
      try {
        await viewer.plugin.clear()
        await viewer.loadStructureFromUrl(
          resolveStructureUrl(structure.source),
          structure.format,
          false,
          { label: structure.title ?? 'Structure' },
        )
        viewer.plugin.managers.camera.reset()
        if (!cancelled) setStatus('ready')
      } catch (loadError) {
        if (cancelled) return
        setStatus('error')
        setError(loadError instanceof Error ? loadError.message : 'Failed to load structure')
      }
    }

    void loadStructure()
    return () => {
      cancelled = true
    }
  }, [normalized, viewerReady])

  useEffect(() => {
    if (!viewerRef.current) return
    const handle = window.setTimeout(() => {
      window.dispatchEvent(new Event('resize'))
    }, 0)
    return () => window.clearTimeout(handle)
  }, [isFullscreen])

  if (!normalized) {
    return (
      <div className="error-message">
        <p>Structure payload is missing a supported source or format.</p>
      </div>
    )
  }

  return (
    <div style={{ display: 'grid', gap: 12 }}>
      <div
        style={{
          position: 'relative',
          minHeight: isFullscreen ? 560 : 360,
          border: '1px solid rgba(255, 255, 255, 0.08)',
          borderRadius: 12,
          overflow: 'hidden',
          background: '#0b1020',
        }}
      >
        <div ref={containerRef} style={{ width: '100%', height: isFullscreen ? 560 : 360 }} />
        {status !== 'ready' && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              background: 'rgba(11, 16, 32, 0.72)',
              color: '#f8fafc',
              fontSize: 13,
            }}
          >
            {status === 'loading' || status === 'idle' ? 'Loading structure...' : error ?? 'Structure failed to load'}
          </div>
        )}
      </div>
      {normalized.annotations && normalized.annotations.length > 0 && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: 8,
          }}
        >
          {normalized.annotations.map((annotation) => (
            <div
              key={annotation.label}
              style={{
                border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                borderRadius: 10,
                padding: '10px 12px',
                background: 'var(--bg-secondary, rgba(255,255,255,0.03))',
              }}
            >
              <div style={{ fontSize: 11, opacity: 0.7, marginBottom: 4 }}>{annotation.label}</div>
              <div style={{ fontSize: 14, fontWeight: 600 }}>{String(annotation.value)}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
