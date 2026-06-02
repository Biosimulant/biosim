import { BarChart3 } from "lucide-react";
import type { LocalRun } from "../types";

export type RunSidebarProps = {
  runs: LocalRun[];
  selectedRunId: string | null;
  onSelect: (id: string) => void;
  comparedIds: Set<string>;
  onCompareToggle: (id: string) => void;
  onOpenCompare: () => void;
};

function statusClass(status: string | null | undefined) {
  return `status-pill ${String(status || "unknown").toLowerCase()}`;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function RunSidebar(props: RunSidebarProps) {
  return (
    <aside className="right-panel runs-panel">
      <RunHistoryPanel {...props} />
    </aside>
  );
}

export function RunHistoryPanel(props: RunSidebarProps) {
  const { runs, selectedRunId, onSelect, comparedIds, onCompareToggle, onOpenCompare } = props;
  const compareCount = comparedIds.size;

  return (
    <div className="runs-history">
      <div className="runs-history-header">
        <span className="section-label">History</span>
        <button
          className="link-button"
          disabled={compareCount < 2}
          onClick={onOpenCompare}
          title={compareCount < 2 ? "Pick at least two runs to compare" : "Open comparison"}
        >
          <BarChart3 size={12} />
          Compare {compareCount > 0 ? `(${compareCount})` : ""}
        </button>
      </div>
      {runs.length === 0 ? (
        <p className="muted">No runs yet.</p>
      ) : (
        <div className="run-rows">
          {runs.slice(0, 50).map((run) => {
            const checked = comparedIds.has(run.id);
            return (
              <div
                key={run.id}
                className={`run-row ${run.id === selectedRunId ? "selected" : ""}`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => onCompareToggle(run.id)}
                  aria-label={`Toggle ${run.id} for comparison`}
                />
                <button
                  type="button"
                  className="run-row-body"
                  onClick={() => onSelect(run.id)}
                >
                  <span className={statusClass(run.status)}>{run.status}</span>
                  <span className="run-id">{run.id.slice(0, 8)}</span>
                  <span className="run-time muted">{formatDate(run.created_at)}</span>
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
