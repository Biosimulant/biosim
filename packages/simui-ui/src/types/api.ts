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
  showRunWhenDisabled?: boolean
  runDisabledReason?: string
  pauseResume?: boolean
  reset?: boolean
  editor?: boolean
}

export type UiSpec = {
  version: string
  bsim_version?: string
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
  step_count?: number
  sim_time?: number
  sim_start?: number
  sim_end?: number
  sim_remaining?: number
  progress?: number
  progress_pct?: number
  phase?: string
  phase_message?: string
  error?: { message: string }
}

export type RunLogEntry = {
  id: string
  run_id: string
  seq: number
  ts: string
  source: string
  level: string
  event_type?: string | null
  message?: string | null
  truncated: boolean
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
