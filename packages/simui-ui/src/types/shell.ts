import type { EventRecord, ModuleVisuals, RunStatus } from "./api";

export type ThemeMode = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";
export type CenterView = "canvas";
export type RunPanelTab = "visuals" | "logs" | "json";

export type DesktopLabShellState = {
  centerView: CenterView;
  leftPanelOpen: boolean;
  rightPanelOpen: boolean;
  inspectorOpen: boolean;
  runPanelTab: RunPanelTab;
  themeMode: ThemeMode;
};

export type ServeRunHistoryEntry = {
  id: string;
  label: string;
  status: "completed" | "failed" | "cancelled" | "unknown";
  startedAt: string;
  finishedAt: string;
  durationSeconds: number | null;
  stepCount: number | null;
  visualCount: number;
  eventCount: number;
  errorMessage?: string | null;
  snapshot: {
    status: RunStatus | null;
    visuals: ModuleVisuals[];
    events: EventRecord[];
  };
};
