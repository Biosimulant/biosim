import * as React from "react";
import { X } from "lucide-react";
import { serveApi } from "../api";
import type { LocalRun, RunModuleVisuals, ServeResults } from "../types";
import { getSeries } from "./visuals";

const SERIES_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

export type CompareOverlayProps = {
  runIds: string[];
  onClose: () => void;
};

type LoadedRun = {
  run: LocalRun;
  results: ServeResults;
  letter: string;
};

export function CompareOverlay({ runIds, onClose }: CompareOverlayProps) {
  const [loaded, setLoaded] = React.useState<LoadedRun[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const fetched = await Promise.all(
          runIds.map(async (id) => {
            const [{ run }, { results }] = await Promise.all([
              serveApi.run(id),
              serveApi.results(id),
            ]);
            return { run, results };
          }),
        );
        if (cancelled) return;
        setLoaded(
          fetched.map((entry, index) => ({
            ...entry,
            letter: String.fromCharCode(65 + index),
          })),
        );
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [runIds]);

  // Discover modules + visuals across all runs (only timeseries are overlaid; other types listed alongside).
  const moduleSet = new Map<string, { module: string; module_class?: string }>();
  for (const entry of loaded) {
    for (const module of entry.results.visuals ?? []) {
      moduleSet.set(module.module, { module: module.module, module_class: module.module_class });
    }
  }
  const modules = Array.from(moduleSet.values());

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal large" onClick={(event) => event.stopPropagation()}>
        <div className="modal-header">
          <h2>Compare {runIds.length} runs</h2>
          <button className="icon-button" onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </div>
        <div className="modal-body">
          {error ? <div className="property-error">{error}</div> : null}
          <div className="compare-legend">
            {loaded.map((entry) => (
              <span
                key={entry.run.id}
                className="compare-legend-item"
                style={{ color: SERIES_COLORS[(entry.letter.charCodeAt(0) - 65) % SERIES_COLORS.length] }}
              >
                <strong>{entry.letter}</strong> {entry.run.id.slice(0, 8)} ({entry.run.status})
              </span>
            ))}
          </div>
          {modules.length === 0 ? (
            <div className="empty-card">No comparable visuals available yet.</div>
          ) : (
            modules.map((module) => (
              <CompareModuleSection key={module.module} module={module} loaded={loaded} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function CompareModuleSection({
  module,
  loaded,
}: {
  module: { module: string; module_class?: string };
  loaded: LoadedRun[];
}) {
  // Collect every timeseries visual at this module across runs, keyed by visual index.
  const perRunModule = loaded.map((entry) => ({
    letter: entry.letter,
    runId: entry.run.id,
    module: (entry.results.visuals ?? []).find((m) => m.module === module.module),
  }));

  const timeseriesIndices = new Set<number>();
  for (const item of perRunModule) {
    item.module?.visuals.forEach((visual, index) => {
      const render = visual.render.toLowerCase();
      if (render === "timeseries" || render === "line") timeseriesIndices.add(index);
    });
  }

  return (
    <section className="visual-module">
      <div className="visual-module-header">
        <h3>{module.module}</h3>
        {module.module_class ? <span>{module.module_class}</span> : null}
      </div>
      {Array.from(timeseriesIndices)
        .sort((a, b) => a - b)
        .map((index) => (
          <CompareTimeseriesChart key={index} perRunModule={perRunModule} visualIndex={index} />
        ))}
    </section>
  );
}

function CompareTimeseriesChart({
  perRunModule,
  visualIndex,
}: {
  perRunModule: Array<{ letter: string; runId: string; module: RunModuleVisuals | undefined }>;
  visualIndex: number;
}) {
  const traces = perRunModule.flatMap((item) => {
    const visual = item.module?.visuals[visualIndex];
    if (!visual) return [];
    const series = getSeries(visual.data);
    return series.map((entry) => ({
      key: `${item.runId}:${entry.name}`,
      label: `${item.letter} · ${entry.name}`,
      letterIndex: item.letter.charCodeAt(0) - 65,
      points: entry.points.map((p) => [Number(p[0]), Number(p[1])] as const),
    }));
  });

  if (traces.length === 0) return null;

  const flat = traces.flatMap((t) => t.points);
  const xs = flat.map((p) => p[0]).filter(Number.isFinite);
  const ys = flat.map((p) => p[1]).filter(Number.isFinite);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = 760;
  const height = 320;
  const marginLeft = 48;
  const marginRight = 14;
  const marginTop = 12;
  const marginBottom = 26;
  const plotW = width - marginLeft - marginRight;
  const plotH = height - marginTop - marginBottom;
  const xSpan = Math.max(1e-9, maxX - minX);
  const ySpan = Math.max(1e-9, maxY - minY);
  const toX = (x: number) => marginLeft + ((x - minX) / xSpan) * plotW;
  const toY = (y: number) => marginTop + (1 - (y - minY) / ySpan) * plotH;
  const tickValues = (min: number, max: number, count: number) =>
    Array.from({ length: count + 1 }, (_, i) => min + ((max - min) * i) / count);
  const fmt = (v: number) => {
    const a = Math.abs(v);
    if (a !== 0 && (a < 0.01 || a >= 10000)) return v.toExponential(1);
    if (Number.isInteger(v)) return String(v);
    return v.toFixed(a < 1 ? 3 : a < 10 ? 2 : 1);
  };

  return (
    <article className="visual-card">
      <svg className="chart" viewBox={`0 0 ${width} ${height}`}>
        {tickValues(minY, maxY, 4).map((tick, i) => (
          <g key={`y-${i}`}>
            <line className="grid-line" x1={marginLeft} y1={toY(tick)} x2={width - marginRight} y2={toY(tick)} />
            <text className="axis-label" x={marginLeft - 6} y={toY(tick) + 3} textAnchor="end">{fmt(tick)}</text>
          </g>
        ))}
        {tickValues(minX, maxX, 5).map((tick, i) => (
          <g key={`x-${i}`}>
            <line className="grid-line" x1={toX(tick)} y1={marginTop} x2={toX(tick)} y2={height - marginBottom} />
            <text className="axis-label" x={toX(tick)} y={height - 10} textAnchor="middle">{fmt(tick)}</text>
          </g>
        ))}
        <line className="axis-line" x1={marginLeft} y1={marginTop} x2={marginLeft} y2={height - marginBottom} />
        <line className="axis-line" x1={marginLeft} y1={height - marginBottom} x2={width - marginRight} y2={height - marginBottom} />
        {traces.map((trace) => (
          <polyline
            key={trace.key}
            fill="none"
            stroke={SERIES_COLORS[trace.letterIndex % SERIES_COLORS.length]}
            strokeWidth="2"
            points={trace.points.map((p) => `${toX(p[0])},${toY(p[1])}`).join(" ")}
          />
        ))}
      </svg>
      <div className="compare-trace-legend">
        {traces.map((trace) => (
          <span key={trace.key} style={{ color: SERIES_COLORS[trace.letterIndex % SERIES_COLORS.length] }}>
            {trace.label}
          </span>
        ))}
      </div>
    </article>
  );
}
