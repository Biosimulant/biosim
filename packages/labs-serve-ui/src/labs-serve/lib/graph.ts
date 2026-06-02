import { MarkerType, type Edge, type Node } from "@xyflow/react";
import dagre from "dagre";
import {
  WORLD_INPUT_RAIL_ID,
  WORLD_OUTPUT_RAIL_ID,
  type LabChildEntry,
  type LabModelEntry,
  type LocalLab,
  type WiringEntry,
  type WorldIoPort,
} from "../types";

export const DEFAULT_NODE_WIDTH = 260;
export const DEFAULT_NODE_HEIGHT = 180;
export const DEFAULT_RAIL_WIDTH = 220;
export const RAIL_HEADER_HEIGHT = 36;
export const RAIL_PILL_HEIGHT = 26;
export const RAIL_PILL_GAP = 6;
export const RAIL_VERTICAL_PADDING = 8;
export const RAIL_HORIZONTAL_GAP = 80;

export function railHeight(portCount: number): number {
  const rows = Math.max(portCount, 1);
  return (
    RAIL_HEADER_HEIGHT +
    RAIL_VERTICAL_PADDING * 2 +
    rows * RAIL_PILL_HEIGHT +
    Math.max(0, rows - 1) * RAIL_PILL_GAP
  );
}

export type ModelNodeData = {
  alias: string;
  title: string;
  subtitle: string;
  inputs: string[];
  outputs: string[];
  warning?: string;
  kind: "model" | "lab";
};

export type WorldRailData = {
  variant: "inputs" | "outputs";
  ports: string[];
};

export function titleForModel(entry: LabModelEntry): string {
  return entry.resolved_model?.title || entry.alias;
}

export function titleForLab(entry: LabChildEntry): string {
  return entry.resolved_space?.title || entry.alias;
}

function resolvedModelPorts(entry: LabModelEntry, direction: "inputs" | "outputs"): string[] {
  const list = entry.resolved_model?.io?.[direction];
  return Array.isArray(list) ? list.map((p) => p.name).filter((name): name is string => Boolean(name)) : [];
}
function resolvedLabPorts(entry: LabChildEntry, direction: "inputs" | "outputs"): string[] {
  const list = entry.resolved_space?.io?.[direction];
  return Array.isArray(list) ? list.map((p) => p.name).filter((name): name is string => Boolean(name)) : [];
}

/**
 * Collect every port name referenced for a given alias from the manifest.
 *
 * Locally-pathed models don't have `resolved_model.io` populated by the backend, so we derive
 * port names from `io.inputs[].maps_to` (world-input mappings target model input ports),
 * `io.outputs[].maps_to` (world-output mappings target model output ports), and from
 * `wiring[].from / .to`. This guarantees every wired port has a `<Handle>` to anchor an edge.
 */
function manifestPortsFor(lab: LocalLab, alias: string): { inputs: Set<string>; outputs: Set<string> } {
  const inputs = new Set<string>();
  const outputs = new Set<string>();

  for (const port of lab.manifest.io?.inputs ?? []) {
    const parsed = parseEndpoint(port.maps_to);
    if (parsed?.node === alias && parsed.port) inputs.add(parsed.port);
  }
  for (const port of lab.manifest.io?.outputs ?? []) {
    const parsed = parseEndpoint(port.maps_to);
    if (parsed?.node === alias && parsed.port) outputs.add(parsed.port);
  }

  for (const wire of lab.manifest.wiring ?? []) {
    const source = parseEndpoint(wire.from ?? wire.source);
    if (source?.node === alias && source.port) outputs.add(source.port);
    for (const targetStr of asTargetList(wire.to ?? wire.target)) {
      const target = parseEndpoint(targetStr);
      if (target?.node === alias && target.port) inputs.add(target.port);
    }
  }

  return { inputs, outputs };
}

function unionPorts(resolved: string[], manifest: Set<string>): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const name of resolved) {
    if (!seen.has(name)) {
      seen.add(name);
      out.push(name);
    }
  }
  for (const name of manifest) {
    if (!seen.has(name)) {
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/** Public helper so the inspector can list the same ports the canvas renders as handles. */
export function getModelPorts(
  lab: LocalLab,
  entry: LabModelEntry,
): { inputs: string[]; outputs: string[] } {
  const manifest = manifestPortsFor(lab, entry.alias);
  return {
    inputs: unionPorts(resolvedModelPorts(entry, "inputs"), manifest.inputs),
    outputs: unionPorts(resolvedModelPorts(entry, "outputs"), manifest.outputs),
  };
}

export function getLabPorts(
  lab: LocalLab,
  entry: LabChildEntry,
): { inputs: string[]; outputs: string[] } {
  const manifest = manifestPortsFor(lab, entry.alias);
  return {
    inputs: unionPorts(resolvedLabPorts(entry, "inputs"), manifest.inputs),
    outputs: unionPorts(resolvedLabPorts(entry, "outputs"), manifest.outputs),
  };
}

function savedPosition(lab: LocalLab, id: string): { x: number; y: number } | null {
  const saved = lab.wiring_layout?.nodes?.find((n) => n.id === id);
  return saved ? saved.position : null;
}

function fallbackPosition(index: number): { x: number; y: number } {
  const column = index % 3;
  const row = Math.floor(index / 3);
  return { x: 360 + column * 320, y: 160 + row * 240 };
}

function parseEndpoint(value: unknown): { node: string; port?: string } | null {
  if (typeof value !== "string" || value.trim().length === 0) return null;
  const trimmed = value.trim();
  // Accept both "alias.port" and "alias:port".
  const sep = trimmed.includes(".") ? "." : trimmed.includes(":") ? ":" : null;
  if (!sep) return { node: trimmed };
  const idx = trimmed.indexOf(sep);
  const node = trimmed.slice(0, idx);
  const port = trimmed.slice(idx + 1);
  return node ? { node, port } : null;
}

function asTargetList(value: unknown): string[] {
  if (Array.isArray(value)) return value.flatMap((entry) => (typeof entry === "string" ? [entry] : []));
  if (typeof value === "string") return [value];
  return [];
}

function buildEdge(
  source: { node: string; port?: string },
  target: { node: string; port?: string },
  index: number,
  variant: "regular" | "world",
): Edge {
  const id = `wire-${index}-${source.node}.${source.port || ""}->${target.node}.${target.port || ""}`;
  const sourceHandle = source.port ? `${source.node}.${source.port}` : undefined;
  const targetHandle = target.port ? `${target.node}.${target.port}` : undefined;
  return {
    id,
    source: source.node,
    target: target.node,
    sourceHandle,
    targetHandle,
    markerEnd: { type: MarkerType.ArrowClosed },
    className: variant === "world" ? "serve-flow-edge world" : "serve-flow-edge",
    data: { variant },
  };
}

export type BuiltGraph = {
  nodes: Node[];
  edges: Edge[];
};

export function buildGraph(lab: LocalLab): BuiltGraph {
  const models = lab.manifest.models ?? [];
  const children = lab.manifest.children ?? [];
  const worldInputs: WorldIoPort[] = lab.manifest.io?.inputs ?? [];
  const worldOutputs: WorldIoPort[] = lab.manifest.io?.outputs ?? [];

  const modelNodes: Node[] = models.map((entry, index) => {
    const ports = getModelPorts(lab, entry);
    return {
      id: entry.alias,
      type: "model",
      position: savedPosition(lab, entry.alias) ?? fallbackPosition(index),
      data: {
        alias: entry.alias,
        title: titleForModel(entry),
        subtitle: entry.package || entry.path || "model",
        inputs: ports.inputs,
        outputs: ports.outputs,
        warning: entry.resolution_error || undefined,
        kind: "model",
      } satisfies ModelNodeData,
    };
  });

  const childNodes: Node[] = children.map((entry, index) => {
    const ports = getLabPorts(lab, entry);
    return {
      id: entry.alias,
      type: "lab",
      position: savedPosition(lab, entry.alias) ?? fallbackPosition(models.length + index),
      data: {
        alias: entry.alias,
        title: titleForLab(entry),
        subtitle: entry.package || entry.path || "nested lab",
        inputs: ports.inputs,
        outputs: ports.outputs,
        warning: entry.resolution_error || undefined,
        kind: "lab",
      } satisfies ModelNodeData,
    };
  });

  const realNodes = [...modelNodes, ...childNodes];

  // Position world rails relative to the model bounding box (left and right edges).
  const xs = realNodes.map((n) => n.position.x);
  const xRights = realNodes.map((n) => n.position.x + DEFAULT_NODE_WIDTH);
  const ys = realNodes.map((n) => n.position.y);
  const yBottoms = realNodes.map((n) => n.position.y + DEFAULT_NODE_HEIGHT);
  const left = xs.length ? Math.min(...xs) : 360;
  const right = xRights.length ? Math.max(...xRights) : 600;
  const top = ys.length ? Math.min(...ys) : 120;
  const bottom = yBottoms.length ? Math.max(...yBottoms) : 360;
  const verticalCenter = top + (bottom - top) / 2;

  const inputsRail: Node | null = worldInputs.length
    ? {
        id: WORLD_INPUT_RAIL_ID,
        type: "worldInputsRail",
        position: {
          x: savedPosition(lab, WORLD_INPUT_RAIL_ID)?.x ?? left - DEFAULT_RAIL_WIDTH - RAIL_HORIZONTAL_GAP,
          y: savedPosition(lab, WORLD_INPUT_RAIL_ID)?.y ?? verticalCenter - railHeight(worldInputs.length) / 2,
        },
        draggable: true,
        selectable: true,
        data: { variant: "inputs", ports: worldInputs.map((p) => p.name) } satisfies WorldRailData,
      }
    : null;

  const outputsRail: Node | null = worldOutputs.length
    ? {
        id: WORLD_OUTPUT_RAIL_ID,
        type: "worldOutputsRail",
        position: {
          x: savedPosition(lab, WORLD_OUTPUT_RAIL_ID)?.x ?? right + RAIL_HORIZONTAL_GAP,
          y: savedPosition(lab, WORLD_OUTPUT_RAIL_ID)?.y ?? verticalCenter - railHeight(worldOutputs.length) / 2,
        },
        draggable: true,
        selectable: true,
        data: { variant: "outputs", ports: worldOutputs.map((p) => p.name) } satisfies WorldRailData,
      }
    : null;

  const nodes: Node[] = [
    ...(inputsRail ? [inputsRail] : []),
    ...realNodes,
    ...(outputsRail ? [outputsRail] : []),
  ];

  const edges: Edge[] = [];
  let edgeIndex = 0;

  // Synthetic edges from world inputs to model ports (derived from io.inputs[].maps_to).
  for (const port of worldInputs) {
    const target = parseEndpoint(port.maps_to);
    if (!target) continue;
    edges.push(
      buildEdge(
        { node: WORLD_INPUT_RAIL_ID, port: port.name },
        target,
        edgeIndex++,
        "world",
      ),
    );
  }

  // Synthetic edges from model ports to world outputs.
  for (const port of worldOutputs) {
    const source = parseEndpoint(port.maps_to);
    if (!source) continue;
    edges.push(
      buildEdge(
        source,
        { node: WORLD_OUTPUT_RAIL_ID, port: port.name },
        edgeIndex++,
        "world",
      ),
    );
  }

  // Regular wires: support `from`/`to` and `source`/`target`; `to`/`target` may be string or list (fan-out).
  const wires: WiringEntry[] = lab.manifest.wiring ?? [];
  for (const wire of wires) {
    const source = parseEndpoint(wire.from ?? wire.source);
    const targets = asTargetList(wire.to ?? wire.target);
    if (!source) continue;
    for (const targetStr of targets) {
      const target = parseEndpoint(targetStr);
      if (!target) continue;
      edges.push(buildEdge(source, target, edgeIndex++, "regular"));
    }
  }

  return { nodes, edges };
}

export function tidyLayout(nodes: Node[], edges: Edge[]): Node[] {
  if (nodes.length === 0) return nodes;
  const layoutable = nodes.filter(
    (n) => n.type !== "worldInputsRail" && n.type !== "worldOutputsRail",
  );
  if (layoutable.length === 0) return nodes;

  const ids = new Set(layoutable.map((n) => n.id));
  const layoutEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));

  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", nodesep: 80, ranksep: 140 });
  graph.setDefaultEdgeLabel(() => ({}));

  for (const node of layoutable) {
    graph.setNode(node.id, { width: DEFAULT_NODE_WIDTH, height: DEFAULT_NODE_HEIGHT });
  }
  for (const edge of layoutEdges) {
    graph.setEdge(edge.source, edge.target);
  }

  dagre.layout(graph);

  return nodes.map((node) => {
    if (node.type === "worldInputsRail" || node.type === "worldOutputsRail") return node;
    const placement = graph.node(node.id);
    if (!placement) return node;
    return {
      ...node,
      position: {
        x: placement.x - DEFAULT_NODE_WIDTH / 2,
        y: placement.y - DEFAULT_NODE_HEIGHT / 2,
      },
    };
  });
}
