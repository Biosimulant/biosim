import type { EventRecord, ModuleVisuals, RunStatus } from "../types/api";
import type { ServeRunHistoryEntry } from "../types/shell";

export const RUN_HISTORY_LIMIT = 12;

export function countVisuals(visuals: ModuleVisuals[]): number {
  return visuals.reduce((sum, entry) => sum + (Array.isArray(entry.visuals) ? entry.visuals.length : 0), 0);
}

export function runStatusForHistory(status: RunStatus | null): ServeRunHistoryEntry["status"] {
  if (status?.error) return "failed";
  if (status && status.running === false) return "completed";
  return "unknown";
}

export function buildRunHistoryEntry({
  id,
  startedAt,
  finishedAt,
  status,
  visuals,
  events,
}: {
  id: string;
  startedAt: Date;
  finishedAt: Date;
  status: RunStatus | null;
  visuals: ModuleVisuals[];
  events: EventRecord[];
}): ServeRunHistoryEntry {
  const durationSeconds = Math.max(0, (finishedAt.getTime() - startedAt.getTime()) / 1000);
  const finalStatus = runStatusForHistory(status);
  return {
    id,
    label: id.replace(/^run-/, "").slice(0, 12),
    status: finalStatus,
    startedAt: startedAt.toISOString(),
    finishedAt: finishedAt.toISOString(),
    durationSeconds,
    stepCount: typeof status?.step_count === "number" ? status.step_count : null,
    visualCount: countVisuals(visuals),
    eventCount: events.length,
    errorMessage: status?.error?.message ?? null,
    snapshot: {
      status,
      visuals,
      events,
    },
  };
}

export function serializeRunHistory(entries: ServeRunHistoryEntry[]): string {
  return JSON.stringify(entries.slice(0, RUN_HISTORY_LIMIT));
}

export function parseRunHistory(value: string | null | undefined): ServeRunHistoryEntry[] {
  if (!value) return [];
  try {
    const parsed = JSON.parse(value);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((entry): entry is ServeRunHistoryEntry => {
      return (
        entry &&
        typeof entry === "object" &&
        typeof entry.id === "string" &&
        typeof entry.startedAt === "string" &&
        typeof entry.finishedAt === "string" &&
        entry.snapshot &&
        typeof entry.snapshot === "object"
      );
    }).slice(0, RUN_HISTORY_LIMIT);
  } catch {
    return [];
  }
}
