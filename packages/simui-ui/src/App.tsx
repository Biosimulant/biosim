import React, { useCallback, useEffect, useRef, useState } from "react";
import { ApiProvider, useApi } from "./app/providers";
import { UiProvider, useUi, isJsonControl, isNumberControl } from "./app/ui";
import type { EventRecord, RunStatus, Snapshot, TickData, UiSpec } from "./types/api";
import type { SSEMessage, SSESubscription, SimulationApi } from "./lib/api";
import type { ChatAdapter } from "./types/chat";
import Sidebar from "./components/Sidebar";
import MainContent from "./components/MainContent";
import Footer from "./components/Footer";
import { ConfigEditor } from "./components/editor";

type AppMode = "simulation" | "editor";

export interface SimuiAppProps {
  api?: SimulationApi;
  className?: string;
  style?: React.CSSProperties;
  height?: string;
  initialMode?: AppMode;
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  chatAdapter?: ChatAdapter;
}

function SimulationView({
  headerLeft,
  headerRight,
  chatAdapter,
}: {
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  chatAdapter?: ChatAdapter;
}) {
  const api = useApi();
  const { state, actions } = useUi();
  const [connected, setConnected] = useState(false);
  const sseRef = useRef<SSESubscription | null>(null);
  const storageKeyRef = useRef<string | null>(null);

  const readStoredControls = (key: string): Record<string, number | string> | null => {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.sessionStorage.getItem(key);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object") return null;
      return parsed as Record<string, number | string>;
    } catch {
      return null;
    }
  };

  const writeStoredControls = (key: string, controls: Record<string, number | string>) => {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem(key, JSON.stringify(controls));
    } catch {
      // Ignore storage errors (private mode, quota, etc).
    }
  };

  const resolveStorageKey = async (): Promise<string> => {
    try {
      const st = await api.state();
      const target = (st as any)?.target;
      const run = (st as any)?.run;
      const modelId = target?.modelId ?? run?.model_id ?? run?.modelId;
      const spaceId = target?.spaceId ?? run?.project_id ?? run?.spaceId;
      if (modelId) return `simui-controls:model:${modelId}`;
      if (spaceId) return `simui-controls:space:${spaceId}`;
    } catch {
      // Ignore and fallback to generic key.
    }
    return "simui-controls:generic";
  };

  const initialize = useCallback(async () => {
    const spec = (await api.spec()) as UiSpec;
    actions.setSpec(spec);
    const defaults: Record<string, number | string> = {};
    const controlNames = new Set<string>();
    for (const control of spec.controls || []) {
      if (isNumberControl(control)) {
        controlNames.add(control.name);
        defaults[control.name] = control.default;
      }
      if (isJsonControl(control)) {
        controlNames.add(control.name);
        defaults[control.name] = String(control.default ?? "");
      }
    }
    const storageKey = await resolveStorageKey();
    storageKeyRef.current = storageKey;
    const stored = readStoredControls(storageKey);
    const restored: Record<string, number | string> = {};
    if (stored) {
      for (const [key, value] of Object.entries(stored)) {
        if (controlNames.has(key)) restored[key] = value as number | string;
      }
    }
    actions.setControls({ ...defaults, ...restored });
  }, [api, actions]);

  const handleSSEMessage = useCallback(
    (msg: SSEMessage) => {
      switch (msg.type) {
        case "snapshot": {
          const snap = msg.data as Snapshot;
          if (snap?.status) actions.setStatus(snap.status);
          if (Array.isArray(snap?.visuals)) actions.setVisuals(snap.visuals);
          if (Array.isArray(snap?.events)) actions.setEvents(snap.events);
          break;
        }
        case "tick": {
          const tick = msg.data as TickData;
          if (tick?.status) actions.setStatus(tick.status);
          if (Array.isArray(tick?.visuals)) actions.setVisuals(tick.visuals);
          if (tick?.event) actions.appendEvent(tick.event);
          break;
        }
        case "event": {
          const event = msg.data as EventRecord;
          actions.appendEvent(event);
          break;
        }
        case "status":
        case "heartbeat": {
          const status = msg.data as RunStatus;
          actions.setStatus(status);
          break;
        }
        default:
          break;
      }
    },
    [actions],
  );

  useEffect(() => {
    const setup = async () => {
      await initialize();
      sseRef.current = api.subscribeSSE(
        handleSSEMessage,
        (err) => {
          console.error("SSE error:", err);
          setConnected(false);
        },
      );
      setConnected(true);
    };

    setup();

    return () => {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
      setConnected(false);
    };
  }, [api, handleSSEMessage, initialize]);

  useEffect(() => {
    const key = storageKeyRef.current;
    if (!key) return;
    writeStoredControls(key, state.controls as Record<string, number | string>);
  }, [state.controls]);

  const run = useCallback(async () => {
    const payload: Record<string, unknown> = {};
    for (const control of state.spec?.controls || []) {
      if (!isNumberControl(control)) continue;
      const raw = state.controls[control.name] ?? control.default;
      const value = typeof raw === "number" ? raw : Number(String(raw));
      if (Number.isFinite(value)) payload[control.name] = value;
    }
    for (const control of state.spec?.controls || []) {
      if (!isJsonControl(control)) continue;
      const raw = state.controls[control.name] ?? control.default;
      const text = typeof raw === "string" ? raw : String(raw);
      if (text.trim() === "") continue;
      try {
        payload[control.name] = JSON.parse(text);
      } catch (error) {
        console.error("Invalid JSON control:", control.name, error);
        alert(`Invalid JSON for "${control.label || control.name}". Please fix it and try again.`);
        return;
      }
    }
    const duration = Number(payload.duration);
    const tickDt = typeof payload.tick_dt === "number" ? (payload.tick_dt as number) : undefined;
    actions.setVisuals([]);
    actions.setEvents([]);
    await api.run(duration, tickDt, payload);
  }, [api, state.controls, state.spec, actions]);

  const pause = useCallback(async () => {
    await api.pause();
  }, [api]);

  const resume = useCallback(async () => {
    await api.resume();
  }, [api]);

  const reset = useCallback(async () => {
    await api.reset();
    actions.setEvents([]);
  }, [api, actions]);

  return (
    <>
      <header className="app-header">
        <div className="app-header-left">
          {headerLeft}
          <h1 className="app-title">{state.spec?.title || "BioSim UI"}</h1>
        </div>
        <div className="app-header-right">
          {headerRight}
          <div className="app-status">{connected && <div className="sse-indicator" title="Stream Connected" />}</div>
        </div>
      </header>
      <aside className="app-sidebar-left">
        <Sidebar onRun={run} onPause={pause} onResume={resume} onReset={reset} />
      </aside>
      <main className="app-main">
        <MainContent chatAdapter={chatAdapter} />
      </main>
      <aside className="app-sidebar-right">
        <Footer />
      </aside>
    </>
  );
}

function EditorView() {
  const api = useApi();
  if (!api.editor) {
    return null;
  }
  return <ConfigEditor api={api} />;
}

function AppCore({
  initialMode,
  editorEnabled,
  headerLeft,
  headerRight,
  chatAdapter,
}: {
  initialMode?: AppMode;
  editorEnabled: boolean;
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  chatAdapter?: ChatAdapter;
}) {
  const [mode, setMode] = useState<AppMode>(initialMode ?? "simulation");

  useEffect(() => {
    if (!editorEnabled) {
      setMode("simulation");
      return;
    }

    const hash = window.location.hash.slice(1);
    if (hash === "editor") setMode("editor");

    const handleHashChange = () => {
      const newHash = window.location.hash.slice(1);
      setMode(newHash === "editor" ? "editor" : "simulation");
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, [editorEnabled]);

  const toggleMode = () => {
    if (!editorEnabled) return;
    const newMode = mode === "simulation" ? "editor" : "simulation";
    window.location.hash = newMode === "editor" ? "editor" : "";
    setMode(newMode);
  };

  if (mode === "editor" && editorEnabled) {
    return (
      <div className="app" style={{ height: "100%" }}>
        <div style={{ position: "absolute", top: "8px", right: "8px", zIndex: 1001 }}>
          <button
            onClick={toggleMode}
            style={{
              padding: "6px 12px",
              background: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "4px",
              cursor: "pointer",
              fontSize: "13px",
              boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
            }}
          >
            Back to Simulation
          </button>
        </div>
        <EditorView />
      </div>
    );
  }

  return (
    <div className="app">
      <div className="app-layout">
        <SimulationView headerLeft={headerLeft} headerRight={headerRight} chatAdapter={chatAdapter} />
      </div>
      {editorEnabled && (
        <div style={{ position: "fixed", bottom: "16px", right: "16px", zIndex: 1000 }}>
          <button
            onClick={toggleMode}
            title="Open Config Editor"
            style={{
              padding: "10px 16px",
              background: "#3b82f6",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              fontSize: "13px",
              fontWeight: 500,
              boxShadow: "0 2px 8px rgba(59, 130, 246, 0.4)",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span style={{ fontSize: "16px" }}>&#9881;</span>
            Config Editor
          </button>
        </div>
      )}
    </div>
  );
}

function AppShell({
  initialMode,
  headerLeft,
  headerRight,
  chatAdapter,
}: {
  initialMode?: AppMode;
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  chatAdapter?: ChatAdapter;
}) {
  const api = useApi();
  const editorEnabled = Boolean(api.editor);
  return (
    <AppCore
      initialMode={initialMode}
      editorEnabled={editorEnabled}
      headerLeft={headerLeft}
      headerRight={headerRight}
      chatAdapter={chatAdapter}
    />
  );
}

export const SimuiApp: React.FC<SimuiAppProps> = ({
  api,
  className,
  style,
  height = "100vh",
  initialMode,
  headerLeft,
  headerRight,
  chatAdapter,
}) => {
  const combinedClassName = className ? `simui-root ${className}` : "simui-root";
  return (
    <div className={combinedClassName} style={{ height, ...style }}>
      <ApiProvider api={api}>
        <UiProvider>
          <AppShell initialMode={initialMode} headerLeft={headerLeft} headerRight={headerRight} chatAdapter={chatAdapter} />
        </UiProvider>
      </ApiProvider>
    </div>
  );
};

// Backwards-compatible export used by the static bundle entrypoint.
export const App: React.FC = () => <SimuiApp />;
