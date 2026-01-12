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

export type VisualSpec = { render: string; data: Record<string, unknown> }
export type ModuleVisuals = { module: string; visuals: VisualSpec[] }

export type UiSpec = {
  version: string
  title: string
  controls: Control[]
  outputs: Array<Record<string, unknown>>
  modules: string[]
}

export type RunStatus = {
  running: boolean
  paused: boolean
  step_count?: number
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
