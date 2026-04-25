import type { RunStatus } from "../types/api";

export type RunProgress = {
  progress: number | null;
  progressPct: number | null;
  progressLabel: string;
  simTime: number | null;
  simRemaining: number | null;
  estimated: boolean;
};

type ProgressInput = {
  status: RunStatus | null | undefined;
  duration: number;
};

function toFiniteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(String(value));
  return Number.isFinite(n) ? n : null;
}

function clamp(value: number, low: number, high: number): number {
  return Math.min(high, Math.max(low, value));
}

export function resolveRunProgress({ status, duration }: ProgressInput): RunProgress {
  const backendProgress = toFiniteNumber(status?.progress);
  const backendProgressPct = toFiniteNumber(status?.progress_pct);
  let progress: number | null = null;
  let progressPct: number | null = null;

  if (backendProgressPct !== null) {
    progressPct = clamp(backendProgressPct, 0, 100);
    progress = backendProgress !== null ? clamp(backendProgress, 0, 1) : progressPct / 100;
  } else if (backendProgress !== null) {
    progress = clamp(backendProgress, 0, 1);
    progressPct = progress * 100;
  }

  const statusSimTime = toFiniteNumber(status?.sim_time);
  const simTime = statusSimTime !== null ? Math.max(0, statusSimTime) : null;

  const statusRemaining = toFiniteNumber(status?.sim_remaining);
  let simRemaining: number | null = null;
  if (statusRemaining !== null) {
    simRemaining = Math.max(0, statusRemaining);
  } else if (simTime !== null && duration > 0 && Number.isFinite(duration)) {
    simRemaining = Math.max(0, duration - simTime);
  }

  return {
    progress,
    progressPct,
    progressLabel: progressPct === null ? "—" : `${progressPct.toFixed(1)}%`,
    simTime,
    simRemaining,
    estimated: false,
  };
}
