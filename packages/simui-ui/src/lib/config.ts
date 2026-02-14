export type FrontendConfig = {
  baseUrl: string
}

// Detect mount path from the Python-served HTML if present
declare global {
  interface Window {
    __BSIM_UI__?: { mountPath?: string }
  }
}

export function resolveConfig(): FrontendConfig {
  const mountPath = window.__BSIM_UI__?.mountPath ?? ''
  // API is served under the same mount path
  const baseUrl = mountPath
  return { baseUrl }
}
