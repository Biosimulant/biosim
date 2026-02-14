import type { EventRecord, ModuleVisuals, RunStatus, Snapshot, UiSpec } from "../types/api";

export type SSEMessage = {
  type: "snapshot" | "event" | "status" | "tick" | "heartbeat";
  data: unknown;
};

export type SSESubscription = {
  close: () => void;
};

// Editor types
export interface ModuleArg {
  name: string;
  type: string;
  default: unknown;
  required: boolean;
  description?: string;
  options?: unknown[];
}

export interface ModuleSpec {
  name: string;
  category: string;
  description?: string;
  inputs: string[];
  outputs: string[];
  args: ModuleArg[];
}

export interface ModuleRegistry {
  modules: Record<string, ModuleSpec>;
  categories: Record<string, string[]>;
}

export interface GraphNode {
  id: string;
  type: string;
  position: { x: number; y: number };
  data: {
    args: Record<string, unknown>;
    inputs: string[];
    outputs: string[];
  };
}

export interface GraphEdge {
  id: string;
  source: string;
  sourceHandle: string;
  target: string;
  targetHandle: string;
}

export interface GraphMeta {
  title?: string;
  description?: string;
}

export interface ConfigGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: GraphMeta;
}

export interface ConfigFileInfo {
  name: string;
  path: string;
  is_dir: boolean;
}

export interface ValidateResponse {
  valid: boolean;
  errors: string[];
}

export interface CurrentConfigResponse {
  available: boolean;
  path: string | null;
  graph: ConfigGraph | null;
  error?: string;
}

export interface ApplyConfigResponse {
  ok: boolean;
  path: string;
  error?: string;
}

export interface SimulationEditorApi {
  getModules: () => Promise<ModuleRegistry>;
  getConfig: (path: string) => Promise<ConfigGraph>;
  getCurrent: () => Promise<CurrentConfigResponse>;
  saveConfig: (path: string, graph: ConfigGraph) => Promise<{ ok: boolean; path: string }>;
  applyConfig: (graph: ConfigGraph, savePath?: string) => Promise<ApplyConfigResponse>;
  validate: (graph: ConfigGraph) => Promise<ValidateResponse>;
  layout: (graph: ConfigGraph) => Promise<ConfigGraph>;
  toYaml: (graph: ConfigGraph) => Promise<{ yaml: string }>;
  fromYaml: (yaml: string) => Promise<ConfigGraph>;
  listFiles: (path?: string) => Promise<ConfigFileInfo[]>;
}

export interface SimulationApi {
  spec: () => Promise<UiSpec>;
  status: () => Promise<RunStatus>;
  state: () => Promise<Record<string, unknown>>;
  events: (since_id?: number, limit?: number) => Promise<{ events: EventRecord[]; next_since_id: number }>;
  visuals: () => Promise<ModuleVisuals[]>;
  snapshot: () => Promise<Snapshot>;
  run: (duration: number, tick_dt?: number, extra?: Record<string, unknown>) => Promise<unknown>;
  pause: () => Promise<unknown>;
  resume: () => Promise<unknown>;
  reset: () => Promise<unknown>;
  subscribeSSE: (onMessage: (msg: SSEMessage) => void, onError?: (err: Event) => void) => SSESubscription;
  editor?: SimulationEditorApi;
}

export type Api = SimulationApi;

export function createSimuiApi(baseUrl: string): SimulationApi {
  const base = baseUrl.replace(/\/$/, "");

  async function get<T>(path: string): Promise<T> {
    const res = await fetch(`${base}${path}`);
    if (!res.ok) {
      throw new Error(`GET ${path} failed: ${res.status}`);
    }
    return res.json() as Promise<T>;
  }

  async function post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`POST ${path} failed: ${res.status}`);
    }
    return res.json() as Promise<T>;
  }

  async function put<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${base}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(`PUT ${path} failed: ${res.status}`);
    }
    return res.json() as Promise<T>;
  }

  function subscribeSSE(onMessage: (msg: SSEMessage) => void, onError?: (err: Event) => void): SSESubscription {
    const eventSource = new EventSource(`${base}/api/stream`);
    eventSource.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as SSEMessage;
        onMessage(msg);
      } catch (error) {
        // Keep parsing errors non-fatal so the stream can continue.
        console.error("Failed to parse SSE message:", error);
      }
    };
    eventSource.onerror = (err) => {
      if (onError) onError(err);
    };
    return {
      close: () => eventSource.close(),
    };
  }

  return {
    // Simulation API
    spec: () => get("/api/spec"),
    status: () => get("/api/status"),
    state: () => get("/api/state"),
    events: (since_id?: number, limit = 200) =>
      get(
        `/api/events?${new URLSearchParams({
          ...(since_id != null ? { since_id: String(since_id) } : {}),
          limit: String(limit),
        }).toString()}`,
      ),
    visuals: () => get("/api/visuals"),
    snapshot: () => get("/api/snapshot"),
    run: (duration: number, tick_dt?: number, extra?: Record<string, unknown>) =>
      post("/api/run", { duration, tick_dt, ...(extra || {}) }),
    pause: () => post("/api/pause", {}),
    resume: () => post("/api/resume", {}),
    reset: () => post("/api/reset", {}),
    subscribeSSE,

    // Editor API
    editor: {
      getModules: () => get<ModuleRegistry>("/api/editor/modules"),
      getConfig: (path: string) => get<ConfigGraph>(`/api/editor/config?path=${encodeURIComponent(path)}`),
      getCurrent: () => get<CurrentConfigResponse>("/api/editor/current"),
      saveConfig: (path: string, graph: ConfigGraph) => put<{ ok: boolean; path: string }>("/api/editor/config", { path, graph }),
      applyConfig: (graph: ConfigGraph, savePath?: string) => post<ApplyConfigResponse>("/api/editor/apply", { graph, save_path: savePath }),
      validate: (graph: ConfigGraph) => post<ValidateResponse>("/api/editor/validate", graph),
      layout: (graph: ConfigGraph) => post<ConfigGraph>("/api/editor/layout", graph),
      toYaml: (graph: ConfigGraph) => post<{ yaml: string }>("/api/editor/to-yaml", graph),
      fromYaml: (yaml: string) => post<ConfigGraph>("/api/editor/from-yaml", { yaml }),
      listFiles: (path?: string) => get<ConfigFileInfo[]>(`/api/editor/files${path ? `?path=${encodeURIComponent(path)}` : ""}`),
    },
  };
}
