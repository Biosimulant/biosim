import React, { useCallback, useMemo } from "react";
import { useUi, useModuleNames, isNumberControl, isJsonControl } from "../app/ui";
import { formatDuration } from "../lib/time";
import { resolveRunProgress } from "../lib/progress";

export interface ControlsBarProps {
  onRun: () => void;
  onPause: () => void;
  onResume: () => void;
  onReset: () => void;
  runPending?: boolean;
  extraActions?: React.ReactNode;
}

/**
 * Horizontal control strip for embedding in the platform's bottom bar.
 * Shows runtime controls, status, and action buttons in a single row.
 */
export default function ControlsBar({
  onRun,
  onPause,
  onResume,
  onReset,
  runPending,
  extraActions,
}: ControlsBarProps) {
  const { state, actions } = useUi();
  const st = state.status;
  const capabilities = state.spec?.capabilities;
  const controlsEnabled = capabilities?.controls ?? true;
  const runEnabled = controlsEnabled && (capabilities?.run ?? true);
  const showRunWhenDisabled = capabilities?.showRunWhenDisabled ?? false;
  const showRunButton = runEnabled || showRunWhenDisabled;
  const runDisabledReason = capabilities?.runDisabledReason || "Run is disabled for this space.";
  const runButtonDisabled = !runEnabled || !!st?.running || !!runPending;
  const runButtonTitle = !runEnabled ? runDisabledReason : undefined;
  const pauseResumeEnabled = controlsEnabled && (capabilities?.pauseResume ?? true);
  const resetEnabled = controlsEnabled && (capabilities?.reset ?? true);

  const numberControls = (state.spec?.controls || []).filter(isNumberControl);
  const runtimeNames = new Set(["duration"]);
  const runtimeControls = numberControls.filter((c) => runtimeNames.has(c.name));

  const updateControl = useCallback(
    (name: string, value: string) => actions.setControls({ [name]: value }),
    [actions],
  );

  const toFiniteNumber = (value: unknown): number => {
    if (value === "" || value === null || value === undefined) return Number.NaN;
    const n = typeof value === "number" ? value : Number(String(value));
    return Number.isFinite(n) ? n : Number.NaN;
  };

  const controlDefault = (name: string): number | undefined =>
    numberControls.find((c) => c.name === name)?.default;

  const duration = toFiniteNumber(state.controls.duration ?? controlDefault("duration"));
  const progress = resolveRunProgress({ status: st, duration });

  const statusLabel = useMemo(() => {
    if (!st) return "Unknown";
    if (st.error) return "Error";
    if (st.running) return st.paused ? "Paused" : "Running";
    return "Idle";
  }, [st]);

  const statusClass = useMemo(() => {
    if (!st) return "status-unknown";
    if (st.error) return "status-error";
    if (st.running) return st.paused ? "status-paused" : "status-running";
    return "status-idle";
  }, [st]);

  return (
    <div className="controls-bar">
      {/* Runtime controls */}
      <div className="controls-bar-fields">
        {runtimeControls.map((c) => (
          <div key={c.name} className="controls-bar-field">
            <label htmlFor={`cbar-${c.name}`} className="controls-bar-label">
              {c.label || c.name}
            </label>
            <input
              id={`cbar-${c.name}`}
              type="number"
              className="controls-bar-input"
              value={String(state.controls[c.name] ?? c.default)}
              min={c.min}
              max={c.max}
              step={c.step ?? "any"}
              onChange={(e) => updateControl(c.name, e.target.value)}
              disabled={!!st?.running || !controlsEnabled}
            />
          </div>
        ))}
      </div>

      {/* Status */}
      <div className="controls-bar-status">
        <span className={`status-badge ${statusClass}`}>{statusLabel}</span>
        {st?.running && progress.simTime !== null && (
          <span className="controls-bar-simtime">{formatDuration(progress.simTime)}</span>
        )}
        {st?.running && progress.progressPct !== null && (
          <div className="controls-bar-progress" title="Simulation-time progress">
            <span className="controls-bar-progress-label">{progress.progressLabel}</span>
            <div className="sim-progress-track controls-bar-progress-track" aria-hidden="true">
              <div className="sim-progress-fill" style={{ width: `${progress.progressPct}%` }} />
            </div>
          </div>
        )}
      </div>

      {/* Action buttons */}
      <div className="controls-bar-actions">
        {showRunButton && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={runEnabled ? onRun : undefined}
            disabled={runButtonDisabled}
            title={runButtonTitle}
          >
            {runPending ? "Starting…" : "Run"}
          </button>
        )}
        {pauseResumeEnabled && st?.running && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={st.paused ? onResume : onPause}
          >
            {st.paused ? "Resume" : "Pause"}
          </button>
        )}
        {resetEnabled && (
          <button type="button" className="btn btn-outline" onClick={onReset}>
            Reset
          </button>
        )}
        {extraActions}
      </div>
    </div>
  );
}
