import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls as FlowControls,
  MiniMap,
  Panel as FlowPanel,
  useNodesState,
  useEdgesState,
  addEdge,
  type Connection,
  type Edge,
  type Node,
  type NodeTypes,
  type OnConnect,
  BackgroundVariant,
} from "@xyflow/react";
import dagre from "dagre";
import { useApi } from "../app/providers";
import { isJsonControl, isNumberControl, useModuleNames, useUi } from "../app/ui";
import type {
  ConfigGraph,
  GraphEdge,
  GraphNode,
  ModuleRegistry,
  ModuleSpec,
  SSEMessage,
  SSESubscription,
} from "../lib/api";
import { resolveRunProgress } from "../lib/progress";
import { formatDuration } from "../lib/time";
import { buildRunHistoryEntry, parseRunHistory, serializeRunHistory } from "../lib/run-history";
import {
  readStoredThemeMode,
  resolveThemeMode,
  THEME_STORAGE_KEY,
  writeStoredThemeMode,
} from "../lib/theme";
import type { RunPanelTab, ServeRunHistoryEntry, ThemeMode } from "../types/shell";
import type { EventRecord, RunStatus, Snapshot, StepData, UiSpec } from "../types/api";
import MainContent from "./MainContent";
import EventsLogsPanel from "./EventsLogsPanel";
import ModuleVisuals from "./ModuleVisuals";
import ModulePalette from "./editor/ModulePalette";
import ModuleNode, { type ModuleNodeData } from "./editor/ModuleNode";
import PropertiesPanel from "./editor/PropertiesPanel";

type DesktopLabShellProps = {
  hideHeader?: boolean;
  onConnectionChange?: (connected: boolean) => void;
  headerLeft?: React.ReactNode;
  headerRight?: React.ReactNode;
  sidebarAction?: React.ReactNode;
};

const RUN_HISTORY_STORAGE_KEY = "simui-serve-run-history";

function Icon({ name }: { name: "panel-left" | "panel-right" | "play" | "pause" | "reset" | "sun" | "moon" | "system" | "layout" | "file" | "save" | "bolt" | "x" }) {
  const paths: Record<typeof name, React.ReactNode> = {
    "panel-left": <path d="M4 5h16v14H4zM9 5v14" />,
    "panel-right": <path d="M4 5h16v14H4zM15 5v14" />,
    play: <path d="M8 5v14l11-7z" />,
    pause: <path d="M7 5h4v14H7zM15 5h4v14h-4z" />,
    reset: <path d="M4 4v6h6M20 20v-6h-6M5 15a7 7 0 0 0 11 3M19 9A7 7 0 0 0 8 6" />,
    sun: <path d="M12 4V2M12 22v-2M4.93 4.93 3.52 3.52M20.48 20.48l-1.41-1.41M4 12H2M22 12h-2M4.93 19.07l-1.41 1.41M20.48 3.52l-1.41 1.41M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8" />,
    moon: <path d="M21 13.1A8 8 0 1 1 10.9 3 6.5 6.5 0 0 0 21 13.1z" />,
    system: <path d="M4 5h16v11H4zM8 20h8M10 16v4M14 16v4" />,
    layout: <path d="M4 6h7v12H4zM13 6h7v5h-7zM13 13h7v5h-7z" />,
    file: <path d="M7 3h7l5 5v13H7zM14 3v6h5" />,
    save: <path d="M5 4h13l1 1v15H5zM8 4v6h8V4M8 20v-6h8v6" />,
    bolt: <path d="m13 2-8 12h7l-1 8 8-12h-7z" />,
    x: <path d="M6 6l12 12M18 6 6 18" />,
  };
  return (
    <svg className="shell-icon" viewBox="0 0 24 24" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}

function getLayoutedElements(
  nodes: Node<ModuleNodeData>[],
  edges: Edge[],
  direction: "TB" | "LR" = "LR",
): { nodes: Node<ModuleNodeData>[]; edges: Edge[] } {
  const dagreGraph = new dagre.graphlib.Graph();
  dagreGraph.setDefaultEdgeLabel(() => ({}));
  const nodeWidth = 220;
  const nodeHeight = 120;
  dagreGraph.setGraph({ rankdir: direction, nodesep: 60, ranksep: 110 });
  nodes.forEach((node) => dagreGraph.setNode(node.id, { width: nodeWidth, height: nodeHeight }));
  edges.forEach((edge) => dagreGraph.setEdge(edge.source, edge.target));
  dagre.layout(dagreGraph);
  return {
    nodes: nodes.map((node) => {
      const position = dagreGraph.node(node.id);
      return {
        ...node,
        position: { x: position.x - nodeWidth / 2, y: position.y - nodeHeight / 2 },
      };
    }),
    edges,
  };
}

function apiGraphToFlow(
  graph: ConfigGraph,
  registry: ModuleRegistry | null,
): { nodes: Node<ModuleNodeData>[]; edges: Edge[] } {
  const nodes: Node<ModuleNodeData>[] = graph.nodes.map((node) => {
    const spec = registry?.modules[node.type];
    return {
      id: node.id,
      type: "moduleNode",
      position: node.position,
      data: {
        label: node.id,
        moduleType: node.type,
        args: node.data.args,
        inputs: node.data.inputs.length > 0 ? node.data.inputs : spec?.inputs || [],
        outputs: node.data.outputs.length > 0 ? node.data.outputs : spec?.outputs || [],
      },
    };
  });
  const edges: Edge[] = graph.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    sourceHandle: edge.sourceHandle,
    target: edge.target,
    targetHandle: edge.targetHandle,
    type: "smoothstep",
    animated: false,
    style: { stroke: "var(--primary-muted)", strokeWidth: 2 },
  }));
  return { nodes, edges };
}

function flowToApiGraph(
  nodes: Node<ModuleNodeData>[],
  edges: Edge[],
  meta: ConfigGraph["meta"],
): ConfigGraph {
  const apiNodes: GraphNode[] = nodes.map((node) => ({
    id: node.id,
    type: node.data.moduleType,
    position: node.position,
    data: {
      args: node.data.args,
      inputs: node.data.inputs,
      outputs: node.data.outputs,
    },
  }));
  const apiEdges: GraphEdge[] = edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    sourceHandle: edge.sourceHandle || "",
    target: edge.target,
    targetHandle: edge.targetHandle || "",
  }));
  return { nodes: apiNodes, edges: apiEdges, meta };
}

function fallbackGraphFromModules(moduleNames: string[]): { nodes: Node<ModuleNodeData>[]; edges: Edge[] } {
  const nodes: Node<ModuleNodeData>[] = moduleNames.map((name, index) => ({
    id: name,
    type: "moduleNode",
    position: { x: 80 + (index % 3) * 260, y: 80 + Math.floor(index / 3) * 180 },
    data: {
      label: name,
      moduleType: name,
      args: {},
      inputs: [],
      outputs: [],
    },
  }));
  return getLayoutedElements(nodes, []);
}

function toFiniteNumber(value: unknown): number {
  if (value === "" || value === null || value === undefined) return Number.NaN;
  const parsed = typeof value === "number" ? value : Number(String(value));
  return Number.isFinite(parsed) ? parsed : Number.NaN;
}

function statusLabel(status: RunStatus | null) {
  if (!status) return "Unknown";
  if (status.error) return "Error";
  if (status.running) return status.paused ? "Paused" : "Running";
  return "Idle";
}

function statusClass(status: RunStatus | null) {
  if (!status) return "unknown";
  if (status.error) return "error";
  if (status.running) return status.paused ? "paused" : "running";
  return "idle";
}

function useThemeMode(): [ThemeMode, (mode: ThemeMode) => void, "light" | "dark"] {
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() =>
    typeof window === "undefined" ? "system" : readStoredThemeMode(window.localStorage),
  );
  const [prefersDark, setPrefersDark] = useState(() =>
    typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches,
  );

  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setPrefersDark(media.matches);
    onChange();
    media.addEventListener?.("change", onChange);
    return () => media.removeEventListener?.("change", onChange);
  }, []);

  const setThemeMode = useCallback((mode: ThemeMode) => {
    setThemeModeState(mode);
    if (typeof window !== "undefined") writeStoredThemeMode(window.localStorage, mode);
  }, []);

  return [themeMode, setThemeMode, resolveThemeMode(themeMode, prefersDark)];
}

function ThemeToggle({
  themeMode,
  setThemeMode,
}: {
  themeMode: ThemeMode;
  setThemeMode: (mode: ThemeMode) => void;
}) {
  const modes: ThemeMode[] = ["system", "light", "dark"];
  return (
    <div className="shell-segmented shell-theme-toggle" aria-label="Theme mode">
      {modes.map((mode) => (
        <button
          key={mode}
          type="button"
          className={themeMode === mode ? "active" : ""}
          onClick={() => setThemeMode(mode)}
          title={`${mode[0]!.toUpperCase()}${mode.slice(1)} theme`}
          aria-label={`${mode} theme`}
        >
          <Icon name={mode === "system" ? "system" : mode === "light" ? "sun" : "moon"} />
        </button>
      ))}
    </div>
  );
}

function RuntimeControls({ disabled }: { disabled: boolean }) {
  const { state, actions } = useUi();
  const controls = state.spec?.controls || [];
  const numberControls = controls.filter(isNumberControl);
  const jsonControls = controls.filter(isJsonControl);
  const updateControl = useCallback((name: string, value: string) => actions.setControls({ [name]: value }), [actions]);

  if (numberControls.length === 0 && jsonControls.length === 0) {
    return <p className="shell-muted">No runtime controls are exposed by this lab.</p>;
  }

  return (
    <div className="shell-form-grid">
      {numberControls.map((control) => (
        <label key={control.name} className="shell-field">
          <span>{control.label || control.name}</span>
          <input
            type="number"
            value={String(state.controls[control.name] ?? control.default)}
            min={control.min}
            max={control.max}
            step={control.step ?? "any"}
            disabled={disabled}
            onChange={(event) => updateControl(control.name, event.target.value)}
          />
        </label>
      ))}
      {jsonControls.map((control) => (
        <label key={control.name} className="shell-field shell-field-wide">
          <span>{control.label || control.name}</span>
          <textarea
            value={String(state.controls[control.name] ?? control.default ?? "")}
            rows={control.rows ?? 4}
            placeholder={control.placeholder}
            disabled={disabled}
            onChange={(event) => updateControl(control.name, event.target.value)}
          />
        </label>
      ))}
    </div>
  );
}

function LabContentsSidebar({
  registry,
  editorAvailable,
  configPath,
  isDirty,
  nodes,
  selectedNode,
  onSelectNode,
  onOpenFiles,
  onNewConfig,
  onPaletteDragStart,
  sidebarAction,
}: {
  registry: ModuleRegistry | null;
  editorAvailable: boolean;
  configPath: string;
  isDirty: boolean;
  nodes: Node<ModuleNodeData>[];
  selectedNode: Node<ModuleNodeData> | null;
  onSelectNode: (node: Node<ModuleNodeData>) => void;
  onOpenFiles: () => void;
  onNewConfig: () => void;
  onPaletteDragStart: (event: React.DragEvent, moduleType: string, spec: ModuleSpec) => void;
  sidebarAction?: React.ReactNode;
}) {
  const { state, actions } = useUi();
  const moduleNames = useModuleNames();
  const [search, setSearch] = useState("");
  const initializedVisibleModulesRef = useRef(false);

  useEffect(() => {
    if (initializedVisibleModulesRef.current || moduleNames.length === 0) return;
    initializedVisibleModulesRef.current = true;
    actions.setVisibleModules(new Set(moduleNames));
  }, [actions, moduleNames]);

  const visible = state.visibleModules;
  const searchLower = search.trim().toLowerCase();
  const filteredNodes = nodes.filter((node) => {
    if (!searchLower) return true;
    return (
      node.id.toLowerCase().includes(searchLower) ||
      node.data.moduleType.toLowerCase().includes(searchLower)
    );
  });

  const toggleModule = (name: string) => {
    const next = new Set(visible);
    if (next.has(name)) next.delete(name);
    else next.add(name);
    actions.setVisibleModules(next);
  };

  return (
    <div className="desktop-left-sidebar">
      <div className="sidebar-heading">
        <div className="sidebar-title-row">
          <div>
            <h2>{state.spec?.title || "Biosimulant Lab"}</h2>
            <p>{moduleNames.length} module{moduleNames.length === 1 ? "" : "s"}</p>
          </div>
        </div>
        <div className="sidebar-search">
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search lab..." />
        </div>
      </div>

      <div className="sidebar-scroll">
        <section className="shell-section">
          <div className="shell-section-header">
            <span>Lab Contents</span>
            <span>{filteredNodes.length}</span>
          </div>
          {filteredNodes.length === 0 ? (
            <p className="shell-empty-inline">No matching modules.</p>
          ) : (
            <div className="lab-tree">
              {filteredNodes.map((node) => {
                const selected = selectedNode?.id === node.id;
                const className = node.data.moduleType.split(".").pop() || node.data.moduleType;
                return (
                  <button
                    key={node.id}
                    type="button"
                    className={`lab-tree-item ${selected ? "active" : ""}`}
                    onClick={() => onSelectNode(node)}
                  >
                    <span className="lab-tree-item-title">{node.id}</span>
                    <span className="lab-tree-item-subtitle">{className}</span>
                  </button>
                );
              })}
            </div>
          )}
        </section>

        <section className="shell-section">
          <div className="shell-section-header">
            <span>Visualization Modules</span>
            <button type="button" onClick={() => actions.setVisibleModules(new Set(moduleNames))}>Show all</button>
          </div>
          <div className="module-visibility-list">
            {moduleNames.length === 0 ? (
              <p className="shell-empty-inline">No modules yet.</p>
            ) : (
              moduleNames.map((name) => (
                <label key={name} className="module-visibility-row">
                  <input type="checkbox" checked={visible.has(name)} onChange={() => toggleModule(name)} />
                  <span>{name}</span>
                </label>
              ))
            )}
          </div>
        </section>

        <section className="shell-section">
          <div className="shell-section-header">
            <span>Config</span>
            <span>{editorAvailable ? "Editable" : "Read-only"}</span>
          </div>
          <div className="config-summary">
            <div>
              <span>Path</span>
              <strong>{configPath || "Current runtime"}</strong>
            </div>
            <div>
              <span>Status</span>
              <strong>{isDirty ? "Unsaved" : "Synced"}</strong>
            </div>
          </div>
          {editorAvailable ? (
            <div className="sidebar-action-row">
              <button type="button" className="btn btn-small btn-outline" onClick={onOpenFiles}><Icon name="file" />Open</button>
              <button type="button" className="btn btn-small btn-outline" onClick={onNewConfig}>New</button>
            </div>
          ) : null}
        </section>

        {editorAvailable ? (
          <section className="shell-section palette-shell-section">
            <div className="shell-section-header">
              <span>Palette</span>
              <span>Drag to canvas</span>
            </div>
            <ModulePalette registry={registry} onDragStart={onPaletteDragStart} />
          </section>
        ) : null}
      </div>

      {sidebarAction ? <div className="desktop-sidebar-extra">{sidebarAction}</div> : null}
    </div>
  );
}

function CanvasWorkspace({
  nodes,
  edges,
  editorAvailable,
  meta,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onSelectionChange,
  onNodeDragStop,
  onNodesDelete,
  onEdgesDelete,
  onDragOver,
  onDrop,
  wrapperRef,
}: {
  nodes: Node<ModuleNodeData>[];
  edges: Edge[];
  editorAvailable: boolean;
  meta: ConfigGraph["meta"];
  onNodesChange: ReturnType<typeof useNodesState<Node<ModuleNodeData>>>[2];
  onEdgesChange: ReturnType<typeof useEdgesState<Edge>>[2];
  onConnect: OnConnect;
  onSelectionChange: (params: { nodes: Node<ModuleNodeData>[] }) => void;
  onNodeDragStop: () => void;
  onNodesDelete: () => void;
  onEdgesDelete: () => void;
  onDragOver: (event: React.DragEvent) => void;
  onDrop: (event: React.DragEvent) => void;
  wrapperRef: React.RefObject<HTMLDivElement>;
}) {
  const nodeTypes: NodeTypes = useMemo(() => ({ moduleNode: ModuleNode }), []);

  return (
    <div ref={wrapperRef} className="desktop-canvas" onDragOver={onDragOver} onDrop={onDrop}>
      {nodes.length === 0 ? (
        <div className="canvas-empty">
          <h3>No modules on the canvas</h3>
          <p>{editorAvailable ? "Drag modules from the palette to build a lab." : "Run metadata did not expose a graph for this lab."}</p>
        </div>
      ) : (
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onSelectionChange={onSelectionChange}
          onNodeDragStop={onNodeDragStop}
          nodeTypes={nodeTypes}
          fitView
          snapToGrid
          snapGrid={[15, 15]}
          nodesDraggable={editorAvailable}
          nodesConnectable={editorAvailable}
          edgesReconnectable={editorAvailable}
          deleteKeyCode={editorAvailable ? ["Backspace", "Delete"] : null}
          onNodesDelete={onNodesDelete}
          onEdgesDelete={onEdgesDelete}
          style={{ background: "var(--bg)" }}
        >
          <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--canvas-dot)" />
          <FlowControls className="compose-controls" />
          <MiniMap
            nodeColor={(node) => {
              const data = node.data as unknown as ModuleNodeData;
              if (data.moduleType.includes(".neuro.")) return "var(--primary)";
              if (data.moduleType.includes(".ecology.")) return "var(--success)";
              return "var(--accent-2)";
            }}
            maskColor="var(--minimap-mask)"
            className="compose-minimap"
          />
          <FlowPanel position="top-center">
            <div className="compose-title-badge">{meta.title || "Canvas"}</div>
          </FlowPanel>
        </ReactFlow>
      )}
    </div>
  );
}

function WorldInspector({
  nodes,
  edges,
  editorAvailable,
  onClose,
}: {
  nodes: Node<ModuleNodeData>[];
  edges: Edge[];
  editorAvailable: boolean;
  onClose: () => void;
}) {
  const { state } = useUi();
  const duration = toFiniteNumber(state.controls.duration ?? 10);
  const progress = resolveRunProgress({ status: state.status, duration });
  return (
    <div className="desktop-inspector">
      <div className="inspector-header">
        <h3>World Properties</h3>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close inspector"><Icon name="x" /></button>
      </div>
      <div className="inspector-body">
        <section className="property-section">
          <h4>Runtime</h4>
          <RuntimeControls disabled={!!state.status?.running} />
        </section>
        <section className="property-section">
          <h4>Composition</h4>
          <dl className="property-list">
            <div><dt>Modules</dt><dd>{nodes.length}</dd></div>
            <div><dt>Connections</dt><dd>{edges.length}</dd></div>
            <div><dt>Editor</dt><dd>{editorAvailable ? "Available" : "Read-only"}</dd></div>
            <div><dt>Progress</dt><dd>{progress.progressLabel}</dd></div>
          </dl>
        </section>
      </div>
    </div>
  );
}

function VisualsSnapshot({ visuals }: { visuals: Snapshot["visuals"] }) {
  if (!visuals.length) {
    return (
      <div className="main-content">
        <div className="empty-state">
          <div className="empty-content">
            <h3>No visualizations</h3>
            <p>This run did not return visualization output.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      <div className="modules-grid">
        {visuals.map((entry, index) => (
          <ModuleVisuals key={`${entry.module}-${index}`} moduleName={entry.module} visuals={entry.visuals || []} />
        ))}
      </div>
    </div>
  );
}

function EventsSnapshot({ events }: { events: EventRecord[] }) {
  if (!events.length) {
    return (
      <div className="event-list empty">
        <div className="empty-state"><p>No events recorded for this run.</p></div>
      </div>
    );
  }
  return (
    <div className="event-list-container historical-events">
      <div className="event-list-header">
        <span className="event-count">{events.length} event{events.length === 1 ? "" : "s"}</span>
      </div>
      <div className="event-list">
        {events.slice().reverse().map((event) => (
          <div key={event.id} className={`event-item ${event.event === "phase" ? "event-item--phase" : ""}`}>
            <time className="event-timestamp" dateTime={event.ts}>{event.ts}</time>
            <div className="event-message">
              {event.event === "phase" && event.payload?.message ? String(event.payload.message) : event.event}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RunPanel({
  activeTab,
  setActiveTab,
  history,
  selectedHistoryId,
  setSelectedHistoryId,
  onRun,
  onPause,
  onResume,
  onReset,
  runPending,
}: {
  activeTab: RunPanelTab;
  setActiveTab: (tab: RunPanelTab) => void;
  history: ServeRunHistoryEntry[];
  selectedHistoryId: string | null;
  setSelectedHistoryId: (id: string | null) => void;
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onReset: () => void;
  runPending: boolean;
}) {
  const { state } = useUi();
  const selectedHistory = history.find((entry) => entry.id === selectedHistoryId) ?? null;
  const status = selectedHistory?.snapshot.status ?? state.status;
  const visuals = selectedHistory?.snapshot.visuals ?? state.visuals;
  const events = selectedHistory?.snapshot.events ?? state.events;
  const duration = toFiniteNumber(state.controls.duration ?? 10);
  const progress = resolveRunProgress({ status, duration });
  const canRun = !state.status?.running && !runPending;

  return (
    <div className="desktop-run-panel">
      <div className="run-panel-header">
        <div>
          <h3>Run</h3>
          <p>{selectedHistory ? `Viewing ${selectedHistory.label}` : "Local session"}</p>
        </div>
        <span className={`shell-status-dot ${statusClass(status)}`} />
      </div>

      <section className="run-card">
        <div className="run-status-line">
          <span className={`status-badge status-${statusClass(status)}`}>{statusLabel(status)}</span>
          {typeof status?.step_count === "number" ? <span>Steps {status.step_count.toLocaleString()}</span> : null}
        </div>
        {status?.error ? <div className="run-error">{status.error.message}</div> : null}
        <div className="run-progress-block">
          <div className="run-progress-label">
            <span>{progress.progressLabel}</span>
            {progress.simTime !== null ? <span>{formatDuration(progress.simTime)}</span> : null}
          </div>
          <div className="sim-progress-track">
            <div className="sim-progress-fill" style={{ width: `${progress.progressPct ?? 0}%` }} />
          </div>
        </div>
        <RuntimeControls disabled={!!state.status?.running} />
        <div className="run-actions">
          <button type="button" className="btn btn-primary" onClick={onRun} disabled={!canRun}>
            <Icon name="play" />{runPending ? "Starting..." : "Run"}
          </button>
          {state.status?.running ? (
            <button type="button" className="btn btn-secondary" onClick={state.status.paused ? onResume : onPause}>
              <Icon name={state.status.paused ? "play" : "pause"} />{state.status.paused ? "Resume" : "Pause"}
            </button>
          ) : null}
          <button type="button" className="btn btn-outline" onClick={onReset}>
            <Icon name="reset" />Reset
          </button>
        </div>
      </section>

      <div className="run-tabs">
        {(["visuals", "logs", "json"] as const).map((tab) => (
          <button key={tab} type="button" className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab === "json" ? "JSON" : tab[0]!.toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      <div className="run-tab-body">
        {activeTab === "visuals" ? (
          selectedHistory ? <VisualsSnapshot visuals={visuals} /> : <MainContent />
        ) : activeTab === "logs" ? (
          selectedHistory ? <EventsSnapshot events={events} /> : <EventsLogsPanel />
        ) : (
          <pre className="raw-json-renderer shell-json-panel">
            {JSON.stringify({ status, visuals, events }, null, 2)}
          </pre>
        )}
      </div>

      <section className="run-history">
        <div className="shell-section-header">
          <span>History</span>
          {selectedHistory ? <button type="button" onClick={() => setSelectedHistoryId(null)}>Live</button> : null}
        </div>
        {history.length === 0 ? (
          <p className="shell-empty-inline">No completed runs in this browser session.</p>
        ) : (
          <div className="run-history-list">
            {history.map((entry) => (
              <button
                key={entry.id}
                type="button"
                className={selectedHistoryId === entry.id ? "active" : ""}
                onClick={() => setSelectedHistoryId(entry.id)}
              >
                <span className={`shell-status-dot ${entry.status}`} />
                <span className="run-history-main">
                  <strong>{entry.label}</strong>
                  <small>{entry.visualCount} visuals · {entry.eventCount} events</small>
                </span>
                <span>{entry.durationSeconds == null ? "-" : `${entry.durationSeconds.toFixed(1)}s`}</span>
              </button>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function FileListModal({
  files,
  onClose,
  onOpenPath,
}: {
  files: { name: string; path: string; is_dir: boolean }[];
  onClose: () => void;
  onOpenPath: (file: { name: string; path: string; is_dir: boolean }) => void;
}) {
  return (
    <div className="shell-modal-backdrop" onClick={onClose}>
      <div className="shell-modal" onClick={(event) => event.stopPropagation()}>
        <header className="shell-modal-header">
          <h3>Open Configuration</h3>
          <button type="button" className="icon-button" onClick={onClose}><Icon name="x" /></button>
        </header>
        <div className="shell-modal-list">
          {files.length === 0 ? <p className="shell-empty-inline">No config files found.</p> : null}
          {files.map((file) => (
            <button key={file.path} type="button" onClick={() => onOpenPath(file)}>
              <span>{file.is_dir ? "Folder" : "YAML"}</span>
              <strong>{file.name}</strong>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function YamlModal({ yaml, onClose }: { yaml: string; onClose: () => void }) {
  return (
    <div className="shell-modal-backdrop" onClick={onClose}>
      <div className="shell-modal shell-modal-wide" onClick={(event) => event.stopPropagation()}>
        <header className="shell-modal-header">
          <h3>YAML Preview</h3>
          <div className="shell-modal-actions">
            <button type="button" className="btn btn-small btn-outline" onClick={() => navigator.clipboard?.writeText(yaml)}>Copy</button>
            <button type="button" className="icon-button" onClick={onClose}><Icon name="x" /></button>
          </div>
        </header>
        <pre className="shell-yaml-preview">{yaml}</pre>
      </div>
    </div>
  );
}

export default function DesktopLabShell({
  hideHeader,
  onConnectionChange,
  headerLeft,
  headerRight,
  sidebarAction,
}: DesktopLabShellProps) {
  const api = useApi();
  const { state, actions } = useUi();
  const moduleNames = useModuleNames();
  const defaultPanelsOpen = () => (typeof window === "undefined" ? true : window.innerWidth > 860);
  const [connected, setConnected] = useState(false);
  const [leftPanelOpen, setLeftPanelOpen] = useState(defaultPanelsOpen);
  const [rightPanelOpen, setRightPanelOpen] = useState(defaultPanelsOpen);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [runPanelTab, setRunPanelTab] = useState<RunPanelTab>("visuals");
  const [themeMode, setThemeMode, resolvedTheme] = useThemeMode();
  const [runPending, setRunPending] = useState(false);
  const [registry, setRegistry] = useState<ModuleRegistry | null>(null);
  const [editorAvailable, setEditorAvailable] = useState(false);
  const [editorLoading, setEditorLoading] = useState(true);
  const [configPath, setConfigPath] = useState("");
  const [meta, setMeta] = useState<ConfigGraph["meta"]>({});
  const [isDirty, setIsDirty] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [files, setFiles] = useState<{ name: string; path: string; is_dir: boolean }[]>([]);
  const [showFiles, setShowFiles] = useState(false);
  const [showYaml, setShowYaml] = useState(false);
  const [yamlPreview, setYamlPreview] = useState("");
  const [selectedNode, setSelectedNode] = useState<Node<ModuleNodeData> | null>(null);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string | null>(null);
  const [runHistory, setRunHistory] = useState<ServeRunHistoryEntry[]>(() =>
    typeof window === "undefined" ? [] : parseRunHistory(window.sessionStorage.getItem(RUN_HISTORY_STORAGE_KEY)),
  );
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<ModuleNodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const sseRef = useRef<SSESubscription | null>(null);
  const wasRunningRef = useRef(false);
  const activeRunRef = useRef<{ id: string; startedAt: Date } | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.sessionStorage.setItem(RUN_HISTORY_STORAGE_KEY, serializeRunHistory(runHistory));
  }, [runHistory]);

  const applyFallbackGraph = useCallback((names: string[]) => {
    const fallback = fallbackGraphFromModules(names);
    setNodes(fallback.nodes);
    setEdges(fallback.edges);
  }, [setEdges, setNodes]);

  const initializeEditor = useCallback(async (spec: UiSpec) => {
    if (!api.editor || spec.capabilities?.editor === false) {
      setEditorAvailable(false);
      applyFallbackGraph(spec.modules || []);
      setEditorLoading(false);
      return;
    }

    try {
      const [registryData, currentConfig] = await Promise.all([
        api.editor.getModules(),
        api.editor.getCurrent(),
      ]);
      setRegistry(registryData);
      setEditorAvailable(true);
      if (currentConfig.available && currentConfig.graph) {
        const flow = apiGraphToFlow(currentConfig.graph, registryData);
        const needsLayout = flow.nodes.every((node) => node.position.x === 0 && node.position.y === 0);
        const next = needsLayout && flow.nodes.length > 0 ? getLayoutedElements(flow.nodes, flow.edges) : flow;
        setNodes(next.nodes);
        setEdges(next.edges);
        setMeta(currentConfig.graph.meta);
        setConfigPath(currentConfig.path || "");
        setIsDirty(false);
      } else {
        applyFallbackGraph(spec.modules || []);
      }
    } catch (error) {
      console.error("Failed to initialize editor APIs:", error);
      setEditorAvailable(false);
      applyFallbackGraph(spec.modules || []);
    } finally {
      setEditorLoading(false);
    }
  }, [api.editor, applyFallbackGraph, setEdges, setNodes]);

  const handleSSEMessage = useCallback((msg: SSEMessage) => {
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
        setRightPanelOpen(true);
        break;
      }
      case "event": {
        actions.appendEvent(msg.data as EventRecord);
        break;
      }
      case "status":
      case "heartbeat": {
        actions.setStatus(msg.data as RunStatus);
        break;
      }
      default:
        break;
    }
  }, [actions]);

  useEffect(() => {
    let cancelled = false;
    async function setup() {
      try {
        const rawSpec = (await api.spec()) as UiSpec;
        if (cancelled) return;
        const spec: UiSpec = {
          ...rawSpec,
          capabilities: {
            ...rawSpec.capabilities,
            editor: rawSpec.capabilities?.editor ?? Boolean(api.editor),
          },
        };
        actions.setSpec(spec);
        const defaults: Record<string, number | string> = {};
        for (const control of spec.controls || []) {
          if (isNumberControl(control)) defaults[control.name] = control.default;
          if (isJsonControl(control)) defaults[control.name] = String(control.default ?? "");
        }
        actions.setControlsIfUnset(defaults);
        await initializeEditor(spec);
        if (cancelled) return;
        sseRef.current = api.subscribeSSE(handleSSEMessage, (error) => {
          console.error("SSE error:", error);
          setConnected(false);
          onConnectionChange?.(false);
        });
        setConnected(true);
        onConnectionChange?.(true);
      } catch (error) {
        console.error("Failed to initialize SimUI:", error);
        setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to initialize SimUI." });
        setEditorLoading(false);
      }
    }
    void setup();
    return () => {
      cancelled = true;
      sseRef.current?.close();
      sseRef.current = null;
      setConnected(false);
      onConnectionChange?.(false);
    };
  }, [actions, api, handleSSEMessage, initializeEditor, onConnectionChange]);

  useEffect(() => {
    if (editorAvailable) return;
    if (nodes.length > 0 || moduleNames.length === 0 || editorLoading) return;
    applyFallbackGraph(moduleNames);
  }, [applyFallbackGraph, editorAvailable, editorLoading, moduleNames, nodes.length]);

  useEffect(() => {
    const running = !!state.status?.running;
    if (running && !wasRunningRef.current) {
      activeRunRef.current = { id: `run-${Date.now()}`, startedAt: new Date() };
    }
    if (!running && wasRunningRef.current && activeRunRef.current) {
      const active = activeRunRef.current;
      activeRunRef.current = null;
      const entry = buildRunHistoryEntry({
        id: active.id,
        startedAt: active.startedAt,
        finishedAt: new Date(),
        status: state.status,
        visuals: state.visuals,
        events: state.events,
      });
      setRunHistory((current) => [entry, ...current.filter((item) => item.id !== entry.id)].slice(0, 12));
    }
    wasRunningRef.current = running;
  }, [state.events, state.status, state.visuals]);

  const run = useCallback(async () => {
    if (runPending || state.status?.running) return;
    setRunPending(true);
    setSelectedHistoryId(null);
    try {
      const payload: Record<string, unknown> = {};
      for (const control of state.spec?.controls || []) {
        if (isNumberControl(control)) {
          const raw = state.controls[control.name] ?? control.default;
          const value = typeof raw === "number" ? raw : Number(String(raw));
          if (Number.isFinite(value)) payload[control.name] = value;
        }
        if (isJsonControl(control)) {
          const raw = state.controls[control.name] ?? control.default;
          const text = typeof raw === "string" ? raw : String(raw ?? "");
          if (!text.trim()) continue;
          try {
            payload[control.name] = JSON.parse(text);
          } catch {
            setMessage({ tone: "error", text: `Invalid JSON for "${control.label || control.name}".` });
            return;
          }
        }
      }
      const duration = Number(payload.duration);
      actions.setVisuals([]);
      actions.setEvents([]);
      setRightPanelOpen(true);
      setRunPanelTab("logs");
      await api.run(Number.isFinite(duration) ? duration : 10, payload);
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to start run." });
    } finally {
      setRunPending(false);
    }
  }, [actions, api, runPending, state.controls, state.spec?.controls, state.status?.running]);

  const pause = useCallback(async () => { await api.pause(); }, [api]);
  const resume = useCallback(async () => { await api.resume(); }, [api]);
  const reset = useCallback(async () => {
    await api.reset();
    actions.setEvents([]);
    actions.setVisuals([]);
    setSelectedHistoryId(null);
  }, [actions, api]);

  const onConnect: OnConnect = useCallback((params: Connection) => {
    if (!editorAvailable) return;
    const edge: Edge = {
      ...params,
      id: `e${Date.now()}`,
      type: "smoothstep",
      style: { stroke: "var(--primary-muted)", strokeWidth: 2 },
    } as Edge;
    setEdges((current) => addEdge(edge, current));
    setIsDirty(true);
  }, [editorAvailable, setEdges]);

  const onSelectionChange = useCallback(({ nodes: selectedNodes }: { nodes: Node<ModuleNodeData>[] }) => {
    const next = selectedNodes.length === 1 ? selectedNodes[0] : null;
    setSelectedNode(next);
    if (next) setInspectorOpen(true);
  }, []);

  const onLayout = useCallback(() => {
    const layouted = getLayoutedElements(nodes, edges);
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
    if (editorAvailable) setIsDirty(true);
  }, [edges, editorAvailable, nodes, setEdges, setNodes]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    if (!editorAvailable) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, [editorAvailable]);

  const onDrop = useCallback((event: React.DragEvent) => {
    if (!editorAvailable) return;
    event.preventDefault();
    const moduleType = event.dataTransfer.getData("application/moduleType");
    const specJson = event.dataTransfer.getData("application/moduleSpec");
    if (!moduleType || !specJson) return;
    const spec = JSON.parse(specJson) as ModuleSpec;
    const bounds = reactFlowWrapper.current?.getBoundingClientRect();
    if (!bounds) return;
    const position = { x: event.clientX - bounds.left - 110, y: event.clientY - bounds.top - 60 };
    const baseName = spec.name.toLowerCase().replace(/[^a-z0-9]/g, "_") || "module";
    let nextId = baseName;
    let index = 1;
    while (nodes.some((node) => node.id === nextId)) nextId = `${baseName}_${index++}`;
    const node: Node<ModuleNodeData> = {
      id: nextId,
      type: "moduleNode",
      position,
      data: { label: nextId, moduleType, args: {}, inputs: spec.inputs, outputs: spec.outputs },
    };
    setNodes((current) => [...current, node]);
    setIsDirty(true);
  }, [editorAvailable, nodes, setNodes]);

  const onPaletteDragStart = useCallback((event: React.DragEvent, moduleType: string, spec: ModuleSpec) => {
    event.dataTransfer.setData("application/moduleType", moduleType);
    event.dataTransfer.setData("application/moduleSpec", JSON.stringify(spec));
    event.dataTransfer.effectAllowed = "move";
  }, []);

  const updateNode = useCallback((nodeId: string, args: Record<string, unknown>) => {
    setNodes((current) => current.map((node) => node.id === nodeId ? { ...node, data: { ...node.data, args } } : node));
    setIsDirty(true);
  }, [setNodes]);

  const deleteNode = useCallback((nodeId: string) => {
    setNodes((current) => current.filter((node) => node.id !== nodeId));
    setEdges((current) => current.filter((edge) => edge.source !== nodeId && edge.target !== nodeId));
    setSelectedNode(null);
    setIsDirty(true);
  }, [setEdges, setNodes]);

  const renameNode = useCallback((oldId: string, newId: string) => {
    if (!newId || nodes.some((node) => node.id === newId && node.id !== oldId)) {
      setMessage({ tone: "error", text: `Node ID "${newId}" already exists.` });
      return;
    }
    setNodes((current) => current.map((node) => node.id === oldId ? { ...node, id: newId, data: { ...node.data, label: newId } } : node));
    setEdges((current) => current.map((edge) => ({
      ...edge,
      source: edge.source === oldId ? newId : edge.source,
      target: edge.target === oldId ? newId : edge.target,
    })));
    setSelectedNode((current) => current?.id === oldId ? { ...current, id: newId, data: { ...current.data, label: newId } } : current);
    setIsDirty(true);
  }, [nodes, setEdges, setNodes]);

  const openFiles = useCallback(async () => {
    if (!api.editor) return;
    try {
      setFiles(await api.editor.listFiles());
      setShowFiles(true);
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to list files." });
    }
  }, [api.editor]);

  const loadConfig = useCallback(async (path: string) => {
    if (!api.editor) return;
    try {
      const graph = await api.editor.getConfig(path);
      const flow = apiGraphToFlow(graph, registry);
      const next = flow.nodes.every((node) => node.position.x === 0 && node.position.y === 0) && flow.nodes.length > 0
        ? getLayoutedElements(flow.nodes, flow.edges)
        : flow;
      setNodes(next.nodes);
      setEdges(next.edges);
      setMeta(graph.meta);
      setConfigPath(path);
      setIsDirty(false);
      setShowFiles(false);
      setMessage(null);
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to load config." });
    }
  }, [api.editor, registry, setEdges, setNodes]);

  const saveConfig = useCallback(async () => {
    if (!api.editor || !configPath) return;
    try {
      await api.editor.saveConfig(configPath, flowToApiGraph(nodes, edges, meta));
      setIsDirty(false);
      setMessage({ tone: "success", text: "Configuration saved." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to save config." });
    }
  }, [api.editor, configPath, edges, meta, nodes]);

  const applyConfig = useCallback(async () => {
    if (!api.editor || !configPath) return;
    try {
      const result = await api.editor.applyConfig(flowToApiGraph(nodes, edges, meta), configPath);
      if (!result.ok) {
        setMessage({ tone: "error", text: result.error || "Failed to apply configuration." });
        return;
      }
      setIsDirty(false);
      setMessage({ tone: "success", text: "Configuration applied to the running lab." });
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to apply config." });
    }
  }, [api.editor, configPath, edges, meta, nodes]);

  const previewYaml = useCallback(async () => {
    if (!api.editor) return;
    try {
      const result = await api.editor.toYaml(flowToApiGraph(nodes, edges, meta));
      setYamlPreview(result.yaml);
      setShowYaml(true);
    } catch (error) {
      setMessage({ tone: "error", text: error instanceof Error ? error.message : "Failed to generate YAML." });
    }
  }, [api.editor, edges, meta, nodes]);

  const newConfig = useCallback(() => {
    setNodes([]);
    setEdges([]);
    setMeta({ title: "New Configuration" });
    setConfigPath("");
    setIsDirty(true);
    setSelectedNode(null);
  }, [setEdges, setNodes]);

  const rootClassName = [
    "desktop-lab-shell",
    !leftPanelOpen ? "left-collapsed" : "",
    !rightPanelOpen ? "right-collapsed" : "",
    inspectorOpen ? "inspector-open" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={rootClassName} data-theme={resolvedTheme} data-theme-mode={themeMode} data-theme-storage-key={THEME_STORAGE_KEY}>
      {!hideHeader ? (
        <header className="desktop-command-bar">
          <div className="command-left">
            {headerLeft}
            <button type="button" className="icon-button" onClick={() => setLeftPanelOpen((value) => !value)} title={leftPanelOpen ? "Hide lab contents" : "Show lab contents"}>
              <Icon name="panel-left" />
            </button>
            <div className="command-title">
              <h1>{state.spec?.title || meta.title || "Biosimulant Lab"}</h1>
              <p>{connected ? "Stream connected" : "Connecting stream"}</p>
            </div>
          </div>

          <div className="command-center">
            <div className="shell-segmented" aria-label="Lab view mode">
              <button type="button" className="active"><Icon name="layout" />Canvas</button>
            </div>
          </div>

          <div className="command-right">
            {message ? (
              <div className={`shell-message ${message.tone}`}>
                {message.text}
                <button type="button" onClick={() => setMessage(null)}><Icon name="x" /></button>
              </div>
            ) : null}
            {editorAvailable ? (
              <div className="command-editor-actions">
                <button type="button" className="btn btn-small btn-outline" onClick={saveConfig} disabled={!isDirty || !configPath}><Icon name="save" />Save</button>
                <button type="button" className="btn btn-small btn-outline" onClick={applyConfig} disabled={!configPath}><Icon name="bolt" />Apply</button>
                <button type="button" className="btn btn-small btn-outline" onClick={previewYaml}>YAML</button>
                <button type="button" className="btn btn-small btn-outline" onClick={onLayout}><Icon name="layout" /></button>
              </div>
            ) : null}
            <button type="button" className="btn btn-small btn-primary" onClick={run} disabled={!!state.status?.running || runPending}><Icon name="play" />{runPending ? "Starting" : "Run"}</button>
            {state.status?.running ? (
              <button type="button" className="btn btn-small btn-secondary" onClick={state.status.paused ? resume : pause}>
                <Icon name={state.status.paused ? "play" : "pause"} />{state.status.paused ? "Resume" : "Pause"}
              </button>
            ) : null}
            <button type="button" className="icon-button" onClick={reset} title="Reset"><Icon name="reset" /></button>
            <ThemeToggle themeMode={themeMode} setThemeMode={setThemeMode} />
            {headerRight}
            <button type="button" className="icon-button" onClick={() => setRightPanelOpen((value) => !value)} title={rightPanelOpen ? "Hide run panel" : "Show run panel"}>
              <Icon name="panel-right" />
            </button>
          </div>
        </header>
      ) : null}

      <div className="desktop-shell-body">
        <aside className="desktop-panel desktop-panel-left">
          <LabContentsSidebar
            registry={registry}
            editorAvailable={editorAvailable}
            configPath={configPath}
            isDirty={isDirty}
            nodes={nodes}
            selectedNode={selectedNode}
            onSelectNode={(node) => {
              setSelectedNode(node);
              setInspectorOpen(true);
            }}
            onOpenFiles={openFiles}
            onNewConfig={newConfig}
            onPaletteDragStart={onPaletteDragStart}
            sidebarAction={sidebarAction}
          />
        </aside>

        {!leftPanelOpen ? (
          <div className="collapsed-strip collapsed-left">
            <button type="button" className="icon-button" onClick={() => setLeftPanelOpen(true)}><Icon name="panel-left" /></button>
          </div>
        ) : null}

        <main className="desktop-main">
          <CanvasWorkspace
            nodes={nodes}
            edges={edges}
            editorAvailable={editorAvailable}
            meta={meta}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onSelectionChange={onSelectionChange}
            onNodeDragStop={() => editorAvailable && setIsDirty(true)}
            onNodesDelete={() => editorAvailable && setIsDirty(true)}
            onEdgesDelete={() => editorAvailable && setIsDirty(true)}
            onDragOver={onDragOver}
            onDrop={onDrop}
            wrapperRef={reactFlowWrapper}
          />
        </main>

        {inspectorOpen ? (
          <aside className="desktop-panel desktop-panel-inspector">
            {selectedNode ? (
              <PropertiesPanel
                selectedNode={selectedNode}
                registry={registry}
                onUpdateNode={updateNode}
                onDeleteNode={deleteNode}
                onRenameNode={renameNode}
              />
            ) : (
              <WorldInspector
                nodes={nodes}
                edges={edges}
                editorAvailable={editorAvailable}
                onClose={() => setInspectorOpen(false)}
              />
            )}
          </aside>
        ) : null}

        <aside className="desktop-panel desktop-panel-right">
          <RunPanel
            activeTab={runPanelTab}
            setActiveTab={setRunPanelTab}
            history={runHistory}
            selectedHistoryId={selectedHistoryId}
            setSelectedHistoryId={setSelectedHistoryId}
            onRun={run}
            onPause={pause}
            onResume={resume}
            onReset={reset}
            runPending={runPending}
          />
        </aside>

        {!rightPanelOpen ? (
          <div className="collapsed-strip collapsed-right">
            <button type="button" className="icon-button" onClick={() => setRightPanelOpen(true)}><Icon name="panel-right" /></button>
          </div>
        ) : null}
      </div>

      {(leftPanelOpen || rightPanelOpen) ? <button type="button" className="mobile-drawer-backdrop" onClick={() => { setLeftPanelOpen(false); setRightPanelOpen(false); }} aria-label="Close panels" /> : null}

      {showFiles ? (
        <FileListModal
          files={files}
          onClose={() => setShowFiles(false)}
          onOpenPath={(file) => {
            if (!api.editor) return;
            if (file.is_dir) void api.editor.listFiles(file.path).then(setFiles);
            else void loadConfig(file.path);
          }}
        />
      ) : null}
      {showYaml ? <YamlModal yaml={yamlPreview} onClose={() => setShowYaml(false)} /> : null}
    </div>
  );
}
