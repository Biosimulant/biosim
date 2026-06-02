import * as React from "react";
import { GitBranch, Maximize2 } from "lucide-react";
import type { RunModuleVisuals, RunVisualSpec } from "../types";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function compactJson(value: unknown): string {
  if (value == null) return "-";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function visualTitle(visual: RunVisualSpec): string {
  const title = visual.data?.title;
  return typeof title === "string" && title.trim() ? title : visual.render;
}

export function VisualsPanel({ visuals }: { visuals: RunModuleVisuals[] }) {
  const [expanded, setExpanded] = React.useState<{ title: string; visual: RunVisualSpec } | null>(null);
  if (!visuals.length) return <div className="empty-card">Run visuals will appear here after results are available.</div>;
  return (
    <>
      <div className="visual-stack">
        {visuals.map((module) => (
          <section key={module.module} className="visual-module">
            <div className="visual-module-header">
              <h3>{module.module}</h3>
              {module.module_class ? <span>{module.module_class}</span> : null}
            </div>
            {module.visuals.map((visual, index) => (
              <article key={`${module.module}-${index}`} className="visual-card">
                <div className="visual-card-header">
                  <div className="visual-card-title">
                    <h4>{visualTitle(visual)}</h4>
                    <span className="renderer-badge">{visual.render}</span>
                  </div>
                  <button className="icon-button small" onClick={() => setExpanded({ title: module.module, visual })}>
                    <Maximize2 size={12} />
                  </button>
                </div>
                {visual.description ? <p>{visual.description}</p> : null}
                <VisualRenderer visual={visual} />
              </article>
            ))}
          </section>
        ))}
      </div>
      {expanded ? (
        <div className="modal-backdrop" onClick={() => setExpanded(null)}>
          <div className="modal large" onClick={(event) => event.stopPropagation()}>
            <div className="modal-header">
              <h2>{expanded.title}</h2>
              <button className="icon-button" onClick={() => setExpanded(null)}>
                ×
              </button>
            </div>
            <VisualRenderer visual={expanded.visual} expanded />
          </div>
        </div>
      ) : null}
    </>
  );
}

export function VisualRenderer({ visual, expanded = false }: { visual: RunVisualSpec; expanded?: boolean }) {
  const render = visual.render.toLowerCase();
  if (render === "table") return <TableVisual data={visual.data} />;
  if (render === "image") return <ImageVisual data={visual.data} />;
  if (render === "timeseries" || render === "line") return <SeriesVisual data={visual.data} expanded={expanded} />;
  if (render === "bar") return <BarVisual data={visual.data} />;
  if (render === "scatter") return <ScatterVisual data={visual.data} />;
  if (render === "heatmap") return <HeatmapVisual data={visual.data} />;
  if (render === "graph") return <GraphVisual data={visual.data} />;
  return <pre className="json-block compact">{compactJson(visual.data)}</pre>;
}

function TableVisual({ data }: { data: Record<string, unknown> }) {
  // Accept three row shapes: array-row (`["Metric A", 1.0]`), record-row (`{Metric: "A", Value: 1}`),
  // and items-array (`{items: [{...}]}`) — same coverage as the desktop run-visuals.tsx table.
  const items = Array.isArray(data.items) ? data.items : [];
  const rowsRaw = Array.isArray(data.rows) ? data.rows : items;
  const columns = Array.isArray(data.columns)
    ? data.columns.map(String)
    : rowsRaw[0] && isRecord(rowsRaw[0])
      ? Object.keys(rowsRaw[0] as Record<string, unknown>)
      : [];
  if (!columns.length) return <pre className="json-block compact">{compactJson(data)}</pre>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rowsRaw.slice(0, 50).map((row, index) => (
            <tr key={index}>
              {columns.map((column, colIndex) => {
                let cell: unknown = "";
                if (Array.isArray(row)) cell = row[colIndex];
                else if (isRecord(row)) cell = row[column];
                return <td key={column}>{cell == null ? "" : String(cell)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ImageVisual({ data }: { data: Record<string, unknown> }) {
  const src =
    typeof data.url === "string" ? data.url : typeof data.src === "string" ? data.src : undefined;
  if (!src) return <pre className="json-block compact">{compactJson(data)}</pre>;
  return <img className="image-visual" src={src} alt={typeof data.alt === "string" ? data.alt : "visual"} />;
}

export function getSeries(data: Record<string, unknown>) {
  const series = Array.isArray(data.series) ? data.series : [];
  return series.flatMap((entry) => {
    if (!isRecord(entry) || !Array.isArray(entry.points)) return [];
    return [
      {
        name: typeof entry.name === "string" ? entry.name : "series",
        points: entry.points.filter(Array.isArray) as unknown[][],
      },
    ];
  });
}

function formatTick(value: number): string {
  if (!Number.isFinite(value)) return "";
  const abs = Math.abs(value);
  if (abs !== 0 && (abs < 0.01 || abs >= 10000)) return value.toExponential(1);
  if (Number.isInteger(value)) return value.toString();
  return value.toFixed(abs < 1 ? 3 : abs < 10 ? 2 : 1);
}

function ticks(min: number, max: number, count: number): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max) || min === max) return [min];
  return Array.from({ length: count + 1 }, (_, index) => min + ((max - min) * index) / count);
}

function SeriesVisual({ data, expanded }: { data: Record<string, unknown>; expanded: boolean }) {
  const series = getSeries(data);
  if (!series.length) return <pre className="json-block compact">{compactJson(data)}</pre>;
  const points = series.flatMap((entry) =>
    entry.points.map((point) => [Number(point[0]), Number(point[1])] as const),
  );
  const xs = points.map((point) => point[0]).filter(Number.isFinite);
  const ys = points.map((point) => point[1]).filter(Number.isFinite);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = 520;
  const height = expanded ? 360 : 200;
  const marginLeft = 44;
  const marginRight = 12;
  const marginTop = 10;
  const marginBottom = 22;
  const plotW = width - marginLeft - marginRight;
  const plotH = height - marginTop - marginBottom;
  const xSpan = Math.max(1e-9, maxX - minX);
  const ySpan = Math.max(1e-9, maxY - minY);
  const toX = (x: number) => marginLeft + ((x - minX) / xSpan) * plotW;
  const toY = (y: number) => marginTop + (1 - (y - minY) / ySpan) * plotH;
  const xTicks = ticks(minX, maxX, 4);
  const yTicks = ticks(minY, maxY, 4);
  return (
    <svg className="chart" viewBox={`0 0 ${width} ${height}`}>
      {/* horizontal grid + Y-axis ticks */}
      {yTicks.map((tick, i) => (
        <g key={`y-${i}`}>
          <line className="grid-line" x1={marginLeft} y1={toY(tick)} x2={width - marginRight} y2={toY(tick)} />
          <text className="axis-label" x={marginLeft - 6} y={toY(tick) + 3} textAnchor="end">
            {formatTick(tick)}
          </text>
        </g>
      ))}
      {/* vertical grid + X-axis ticks */}
      {xTicks.map((tick, i) => (
        <g key={`x-${i}`}>
          <line className="grid-line" x1={toX(tick)} y1={marginTop} x2={toX(tick)} y2={height - marginBottom} />
          <text className="axis-label" x={toX(tick)} y={height - 8} textAnchor="middle">
            {formatTick(tick)}
          </text>
        </g>
      ))}
      {/* axes */}
      <line className="axis-line" x1={marginLeft} y1={marginTop} x2={marginLeft} y2={height - marginBottom} />
      <line className="axis-line" x1={marginLeft} y1={height - marginBottom} x2={width - marginRight} y2={height - marginBottom} />
      {/* data series */}
      {series.map((entry, index) => (
        <polyline
          key={entry.name}
          fill="none"
          stroke={`var(--chart-${(index % 5) + 1})`}
          strokeWidth="2"
          points={entry.points
            .map((point) => `${toX(Number(point[0]))},${toY(Number(point[1]))}`)
            .join(" ")}
        />
      ))}
    </svg>
  );
}

function BarVisual({ data }: { data: Record<string, unknown> }) {
  const items = Array.isArray(data.items) ? data.items : Array.isArray(data.bars) ? data.bars : [];
  const parsed = items.flatMap((item) =>
    isRecord(item) ? [{ label: String(item.label ?? ""), value: Number(item.value ?? 0) }] : [],
  );
  const max = Math.max(1, ...parsed.map((item) => item.value));
  if (!parsed.length) return <pre className="json-block compact">{compactJson(data)}</pre>;
  return (
    <div className="bar-list">
      {parsed.map((item) => (
        <div key={item.label} className="bar-row">
          <span>{item.label}</span>
          <div>
            <i style={{ width: `${(item.value / max) * 100}%` }} />
          </div>
          <b>{item.value}</b>
        </div>
      ))}
    </div>
  );
}

function ScatterVisual({ data }: { data: Record<string, unknown> }) {
  const points = Array.isArray(data.points)
    ? data.points.flatMap((point) =>
        isRecord(point) ? [{ x: Number(point.x), y: Number(point.y) }] : [],
      )
    : [];
  if (!points.length) return <pre className="json-block compact">{compactJson(data)}</pre>;
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return (
    <svg className="chart" viewBox="0 0 360 180">
      {points.map((point, index) => (
        <circle
          key={index}
          cx={18 + ((point.x - minX) / Math.max(1, maxX - minX)) * 324}
          cy={162 - ((point.y - minY) / Math.max(1, maxY - minY)) * 144}
          r="3"
        />
      ))}
    </svg>
  );
}

function HeatmapVisual({ data }: { data: Record<string, unknown> }) {
  const matrix = Array.isArray(data.matrix) ? data.matrix : [];
  if (!matrix.length) return <pre className="json-block compact">{compactJson(data)}</pre>;
  return (
    <div className="heatmap">
      {matrix.map((row, rowIndex) =>
        Array.isArray(row)
          ? row.map((value, columnIndex) => (
              <span
                key={`${rowIndex}-${columnIndex}`}
                style={{ opacity: Math.max(0.2, Math.min(1, Number(value) || 0)) }}
              />
            ))
          : null,
      )}
    </div>
  );
}

function GraphVisual({ data }: { data: Record<string, unknown> }) {
  const nodes = Array.isArray(data.nodes) ? data.nodes : [];
  const edges = Array.isArray(data.edges) ? data.edges : [];
  return (
    <div className="graph-summary">
      <GitBranch size={14} /> {nodes.length} nodes / {edges.length} edges
    </div>
  );
}

export function LogsPanel({ logs }: { logs: import("../types").RunLogEntry[] }) {
  if (!logs.length) return <div className="empty-card">No logs for this run.</div>;
  return (
    <div className="logs-list">
      {logs.map((entry) => (
        <div key={`${entry.run_id}-${entry.seq}`} className="log-line">
          <span>{entry.seq}</span>
          <span>{entry.level}</span>
          <code>{entry.source}</code>
          <p>{entry.message}</p>
        </div>
      ))}
    </div>
  );
}
