import React, { createContext, useContext, useMemo } from 'react'
import { makeApi, Api } from '../lib/api'
import { resolveConfig } from '../lib/config'

const ApiContext = createContext<Api | null>(null)

export const ApiProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const cfg = useMemo(resolveConfig, [])
  const api = useMemo(() => makeApi(cfg.baseUrl), [cfg.baseUrl])
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>
}

export function useApi(): Api {
  const ctx = useContext(ApiContext)
  if (!ctx) throw new Error('useApi must be used within ApiProvider')
  return ctx
}
