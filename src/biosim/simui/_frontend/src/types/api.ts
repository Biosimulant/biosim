// Backend API data shapes

export type NumberControl = {
  type: 'number'
  name: string
  label?: string
  default: number
  min?: number
  max?: number
  step?: number
}

export type ButtonControl = { type: 'button'; label: string }
export type Control = NumberControl | ButtonControl

export type EventRecord = { id: number; ts: string; event: string; payload?: Record<string, unknown> }

export type StructureArtifactSource = {
  kind: 'artifact'
  artifact_id: string
}

export type StructureUrlSource = {
  kind: 'url'
  url: string
}

export type StructureSource = StructureArtifactSource | StructureUrlSource

export type Structure3DAnnotation = {
  label: string
  value: string | number | boolean
}

export type Structure3DData = {
  title?: string
  source: StructureSource
  format: 'mmcif' | 'pdb'
  description?: string
  annotations?: Structure3DAnnotation[]
  initial_view?: Record<string, unknown>
}

export type VisualSpec = { render: string; data: Record<string, unknown>; description?: string }
export type ModuleVisuals = { module: string; visuals: VisualSpec[] }

export type UiSpec = {
  version: string
  title: string
  description?: string | null
  controls: Control[]
  outputs: Array<Record<string, unknown>>
  modules: string[]
}

export type RunStatus = {
  running: boolean
  paused: boolean
  step_count?: number
  phase?: string
  phase_message?: string
  error?: { message: string }
}

export type Snapshot = {
  status: RunStatus
  visuals: ModuleVisuals[]
  events: EventRecord[]
}

export type StepData = {
  status: RunStatus
  visuals: ModuleVisuals[]
  event: EventRecord
}
