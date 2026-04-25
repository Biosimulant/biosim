import React, { useCallback, useEffect, useRef, useState } from "react";
import { ApiProvider, useApi } from "../app/providers";
import { UiProvider, useUi, isJsonControl, isNumberControl } from "../app/ui";
import type { EventRecord, RunStatus, Snapshot, StepData, UiSpec } from "../types/api";
import type { SSEMessage, SSESubscription, SimulationApi } from "../lib/api";
import MainContent from "./MainContent";
import EventsLogsPanel from "./EventsLogsPanel";

export interface ResultsPanelProps {
  api: SimulationApi;
  showDescription?: boolean;
  showEvents?: boolean;
  onConnectionChange?: (connected: boolean) => void;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Headless results-only view that wraps ApiProvider + UiProvider + SSE subscription
 * + MainContent + EventsLogsPanel. This is SimulationView minus the sidebar/header/editor.
 *
 * Designed for embedding inside the platform's unified Lab tab.
 */
function ResultsPanelInner({
  showDescription = false,
  showEvents = true,
  onConnectionChange,
}: Omit<ResultsPanelProps, "api" | "className" | "style">) {
  const api = useApi();
  const { state, actions } = useUi();
  const [connected, setConnected] = useState(false);
  const sseRef = useRef<SSESubscription | null>(null);

  const initialize = useCallback(async () => {
    const spec = (await api.spec()) as UiSpec;
    // If showDescription is false, strip description before setting spec
    if (!showDescription && spec) {
      actions.setSpec({ ...spec, description: undefined });
    } else {
      actions.setSpec(spec);
    }
    const defaults: Record<string, number | string> = {};
    for (const control of spec.controls || []) {
      if (isNumberControl(control)) {
        defaults[control.name] = control.default;
      }
      if (isJsonControl(control)) {
        defaults[control.name] = String(control.default ?? "");
      }
    }
    actions.setControlsIfUnset(defaults);
  }, [api, actions, showDescription]);

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
        case "step": {
          const step = msg.data as StepData;
          if (step?.status) actions.setStatus(step.status);
          if (Array.isArray(step?.visuals)) actions.setVisuals(step.visuals);
          if (step?.event) actions.appendEvent(step.event);
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
      sseRef.current = api.subscribeSSE(handleSSEMessage, (err) => {
        console.error("SSE error:", err);
        setConnected(false);
        onConnectionChange?.(false);
      });
      setConnected(true);
      onConnectionChange?.(true);
    };

    setup();

    return () => {
      if (sseRef.current) {
        sseRef.current.close();
        sseRef.current = null;
      }
      setConnected(false);
      onConnectionChange?.(false);
    };
  }, [api, handleSSEMessage, initialize]);

  const hasVisuals = state.visuals.length > 0;
  const hasEvents = (state.events || []).length > 0;
  const isIdle = !state.status?.running && !hasVisuals && !hasEvents;

  return (
    <div className="results-panel">
      <div className="results-panel-main">
        {isIdle ? (
          <div className="results-panel-empty">
            <p>Run a simulation to see results here.</p>
          </div>
        ) : (
          <MainContent />
        )}
      </div>
      {showEvents && (hasEvents || state.status?.running) && (
        <div className="results-panel-events">
          <EventsLogsPanel />
        </div>
      )}
    </div>
  );
}

export default function ResultsPanel({
  api,
  showDescription = false,
  showEvents = true,
  onConnectionChange,
  className,
  style,
}: ResultsPanelProps) {
  const cn = className ? `simui-root ${className}` : "simui-root";
  return (
    <div className={cn} style={style}>
      <ApiProvider api={api}>
        <UiProvider>
          <ResultsPanelInner
            showDescription={showDescription}
            showEvents={showEvents}
            onConnectionChange={onConnectionChange}
          />
        </UiProvider>
      </ApiProvider>
    </div>
  );
}
