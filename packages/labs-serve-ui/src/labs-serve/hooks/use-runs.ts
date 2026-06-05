import * as React from "react";
import { serveApi, type CreateRunBody } from "../api";
import type { LocalRun, RunLogEntry, ServeResults } from "../types";

const ACTIVE_RUN_STATUSES = new Set(["queued", "pending", "running", "cancelling"]);

export function isActive(run: LocalRun | null | undefined): boolean {
  return Boolean(run && ACTIVE_RUN_STATUSES.has(run.status));
}

export type RunsState = {
  runs: LocalRun[];
  selectedRunId: string | null;
  selectedRun: LocalRun | null;
  activeRun: LocalRun | null;
  results: ServeResults | null;
  logs: RunLogEntry[];
  busy: boolean;
  error: string | null;
  selectRun: (id: string | null) => void;
  refresh: (preferredRunId?: string | null) => Promise<void>;
  startRun: (body?: CreateRunBody) => Promise<LocalRun>;
  cancelRun: () => Promise<void>;
};

export function useRuns(): RunsState {
  const [runs, setRuns] = React.useState<LocalRun[]>([]);
  const [selectedRunId, setSelectedRunId] = React.useState<string | null>(null);
  const [selectedRun, setSelectedRun] = React.useState<LocalRun | null>(null);
  const [results, setResults] = React.useState<ServeResults | null>(null);
  const [logs, setLogs] = React.useState<RunLogEntry[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  // Hold the latest selection in a ref so the polling effect doesn't have to re-bind on every change.
  const selectedRunIdRef = React.useRef<string | null>(null);
  selectedRunIdRef.current = selectedRunId;

  const refresh = React.useCallback(async (preferredRunId?: string | null) => {
    try {
      const { runs: next } = await serveApi.runs();
      const sorted = [...next].sort(
        (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
      );
      setRuns(sorted);
      const target = preferredRunId ?? selectedRunIdRef.current ?? sorted[0]?.id ?? null;
      setSelectedRunId(target);
      if (target) {
        const [{ run }, { logs: nextLogs }] = await Promise.all([
          serveApi.run(target),
          serveApi.logs(target),
        ]);
        setSelectedRun(run);
        setLogs(nextLogs);
        if (isActive(run)) {
          setResults(null);
        } else {
          const { results: nextResults } = await serveApi.results(target);
          setResults(nextResults);
        }
      } else {
        setSelectedRun(null);
        setResults(null);
        setLogs([]);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  React.useEffect(() => {
    void refresh();
  }, [refresh]);

  const activeRun = React.useMemo(
    () => runs.find((run) => isActive(run)) ?? (isActive(selectedRun) ? selectedRun : null),
    [runs, selectedRun],
  );

  React.useEffect(() => {
    const interval = activeRun ? 1250 : 3500;
    const timer = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, interval);
    return () => window.clearInterval(timer);
  }, [activeRun, refresh]);

  const startRun = React.useCallback(
    async (body: CreateRunBody = {}) => {
      setBusy(true);
      try {
        const { run } = await serveApi.createRun(body);
        await refresh(run.id);
        return run;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        throw err;
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  const cancelRun = React.useCallback(async () => {
    if (!activeRun) return;
    setBusy(true);
    try {
      await serveApi.cancel(activeRun.id);
      await refresh(activeRun.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      throw err;
    } finally {
      setBusy(false);
    }
  }, [activeRun, refresh]);

  return {
    runs,
    selectedRunId,
    selectedRun,
    activeRun,
    results,
    logs,
    busy,
    error,
    selectRun: setSelectedRunId,
    refresh,
    startRun,
    cancelRun,
  };
}
