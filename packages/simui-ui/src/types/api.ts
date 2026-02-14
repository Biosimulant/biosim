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

export type JsonControl = {
  type: 'json'
  name: string
  label?: string
  default: string
  placeholder?: string
  rows?: number
}

export type ButtonControl = { type: 'button'; label: string }
export type Control = NumberControl | JsonControl | ButtonControl

export type EventRecord = { id: number; ts: string; event: string; payload?: Record<string, unknown> }

export type VisualSpec = { render: string; data: Record<string, unknown>; description?: string }
export type ModuleVisuals = { module: string; visuals: VisualSpec[] }

export type UiCapabilities = {
  controls?: boolean
  run?: boolean
  pauseResume?: boolean
  reset?: boolean
  editor?: boolean
}

export type UiSpec = {
  version: string
  title: string
  description?: string | null
  controls: Control[]
  outputs: Array<Record<string, unknown>>
  modules: string[]
  capabilities?: UiCapabilities
}

export type RunStatus = {
  running: boolean
  paused: boolean
  tick_count?: number
  error?: { message: string }
}

export type Snapshot = {
  status: RunStatus
  visuals: ModuleVisuals[]
  events: EventRecord[]
}

export type TickData = {
  status: RunStatus
  visuals: ModuleVisuals[]
  event: EventRecord
}
