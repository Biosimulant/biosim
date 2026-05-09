import React, { useMemo } from "react";

type ScatterPoint = { x: number; y: number; label?: string; series?: string };

function toFiniteNumber(value: unknown, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export default function Scatter({
  data,
  isFullscreen,
}: {
  data: { points?: ScatterPoint[] };
  isFullscreen?: boolean;
}) {
  const width = 560;
  const height = 280;
  const marginLeft = 56;
  const marginRight = 20;
  const marginTop = 20;
  const marginBottom = 40;
  const points = useMemo(
    () =>
      (Array.isArray(data?.points) ? data.points : []).map((point) => ({
        x: toFiniteNumber(point?.x),
        y: toFiniteNumber(point?.y),
        label: typeof point?.label === "string" ? point.label : undefined,
        series: typeof point?.series === "string" ? point.series : undefined,
      })),
    [JSON.stringify(data?.points || [])],
  );

  if (points.length === 0) return <div className="empty-state"><p>No scatter data</p></div>;

  let xMin = points[0]!.x;
  let xMax = points[0]!.x;
  let yMin = points[0]!.y;
  let yMax = points[0]!.y;
  for (const point of points) {
    if (point.x < xMin) xMin = point.x;
    if (point.x > xMax) xMax = point.x;
    if (point.y < yMin) yMin = point.y;
    if (point.y > yMax) yMax = point.y;
  }
  if (xMax <= xMin) xMax = xMin + 1;
  if (yMax <= yMin) yMax = yMin + 1;

  const sx = (value: number) => marginLeft + ((value - xMin) / (xMax - xMin)) * (width - marginLeft - marginRight);
  const sy = (value: number) => marginTop + (1 - (value - yMin) / (yMax - yMin)) * (height - marginTop - marginBottom);
  const ticks = (min: number, max: number, count = 4) =>
    Array.from({ length: count + 1 }, (_, index) => min + ((max - min) * index) / count);

  const seriesNames = Array.from(new Set(points.map((point) => point.series).filter(Boolean))) as string[];
  const colorBySeries = new Map<string, string>();
  const palette = ["#2563eb", "#059669", "#d97706", "#dc2626", "#0891b2", "#9333ea"];
  seriesNames.forEach((name, index) => colorBySeries.set(name, palette[index % palette.length]!));
  const colorForPoint = (point: ScatterPoint) =>
    point.series ? colorBySeries.get(point.series) || palette[0]! : palette[0]!;

  return (
    <div className={isFullscreen ? "renderer-fill" : undefined}>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height={isFullscreen ? "100%" : height}
        preserveAspectRatio={isFullscreen ? "xMidYMid meet" : undefined}
      >
        <line x1={marginLeft} y1={height - marginBottom} x2={width - marginRight} y2={height - marginBottom} className="axis" />
        <line x1={marginLeft} y1={marginTop} x2={marginLeft} y2={height - marginBottom} className="axis" />
        {ticks(xMin, xMax).map((tick) => (
          <g key={`x-${tick}`}>
            <line x1={sx(tick)} y1={height - marginBottom} x2={sx(tick)} y2={height - marginBottom + 4} className="tick" />
            <text x={sx(tick)} y={height - 8} className="ticklbl" textAnchor="middle">{tick.toFixed(2)}</text>
          </g>
        ))}
        {ticks(yMin, yMax).map((tick) => (
          <g key={`y-${tick}`}>
            <line x1={marginLeft - 4} y1={sy(tick)} x2={marginLeft} y2={sy(tick)} className="tick" />
            <text x={marginLeft - 8} y={sy(tick) + 3} className="ticklbl" textAnchor="end">{tick.toFixed(2)}</text>
          </g>
        ))}
        {points.map((point, index) => (
          <circle key={`${point.label || "point"}-${index}`} cx={sx(point.x)} cy={sy(point.y)} r={4} fill={colorForPoint(point)} opacity={0.86}>
            {point.label ? <title>{`${point.label}: (${point.x.toFixed(3)}, ${point.y.toFixed(3)})`}</title> : null}
          </circle>
        ))}
      </svg>
      {seriesNames.length > 0 ? (
        <div className="renderer-legend">
          {seriesNames.map((series) => (
            <div key={series} className="renderer-legend-item">
              <span style={{ background: colorBySeries.get(series) }} />
              <span>{series}</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
