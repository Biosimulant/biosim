export { SimuiApp } from "./App";
export type { SimuiAppProps } from "./App";

// Embeddable sub-components for platform integration
export { default as ResultsPanel } from "./components/ResultsPanel";
export type { ResultsPanelProps } from "./components/ResultsPanel";
export { default as ControlsBar } from "./components/ControlsBar";
export type { ControlsBarProps } from "./components/ControlsBar";

// Context providers (for wrapping custom component trees)
export { UiProvider, useUi, useModuleNames, useVisualsByModule, isNumberControl, isJsonControl } from "./app/ui";
export type { ControlsState } from "./app/ui";
export { ApiProvider, useApi } from "./app/providers";

// Individual components for fine-grained embedding
export { default as SimuiMainContent } from "./components/MainContent";
export { default as SimuiSidebar } from "./components/Sidebar";
export { default as SimuiEventsLogsPanel } from "./components/EventsLogsPanel";
export { default as SimuiDescriptionPanel } from "./components/DescriptionPanel";

export { createSimuiApi } from "./lib/api";
export type {
  SimulationApi,
  SimulationEditorApi,
  SSEMessage,
  SSESubscription,
  ModuleArg,
  ModuleSpec,
  ModuleRegistry,
  GraphNode,
  GraphEdge,
  GraphMeta,
  ConfigGraph,
  ConfigFileInfo,
  ValidateResponse,
  CurrentConfigResponse,
  ApplyConfigResponse,
} from "./lib/api";

export type {
  NumberControl,
  ButtonControl,
  Control,
  EventRecord,
  VisualSpec,
  ModuleVisuals,
  UiSpec,
  UiCapabilities,
  RunStatus,
  Snapshot,
} from "./types/api";

export type { ChatMessageRole, ChatMessage, ChatThread, ChatAdapter } from "./types/chat";
