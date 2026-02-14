import React, { createContext, useContext, useMemo } from "react";
import { createSimuiApi, type SimulationApi } from "../lib/api";
import { resolveConfig } from "../lib/config";

const ApiContext = createContext<SimulationApi | null>(null);

export const ApiProvider: React.FC<{ api?: SimulationApi; children: React.ReactNode }> = ({
  api: injectedApi,
  children,
}) => {
  const cfg = useMemo(resolveConfig, []);
  const api = useMemo(() => injectedApi ?? createSimuiApi(cfg.baseUrl), [cfg.baseUrl, injectedApi]);
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
};

export function useApi(): SimulationApi {
  const ctx = useContext(ApiContext);
  if (!ctx) throw new Error("useApi must be used within ApiProvider");
  return ctx;
}
