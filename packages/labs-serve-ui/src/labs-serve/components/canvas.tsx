import * as React from "react";
import {
  Background,
  Controls,
  Handle,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { FlaskConical, GitBranch, Globe2, Plus, WandSparkles } from "lucide-react";
import "@xyflow/react/dist/style.css";
import { WORLD_INPUT_RAIL_ID, WORLD_OUTPUT_RAIL_ID, type LocalLab, type Selection } from "../types";
import {
  RAIL_HEADER_HEIGHT,
  RAIL_PILL_GAP,
  RAIL_PILL_HEIGHT,
  RAIL_VERTICAL_PADDING,
  buildGraph,
  railHeight,
  tidyLayout,
  type ModelNodeData,
  type WorldRailData,
} from "../lib/graph";

type HoverHandlers = {
  show: (kind: "Input" | "Output", text: string, event: React.MouseEvent) => void;
  move: (event: React.MouseEvent) => void;
  hide: () => void;
};

const HoverToastContext = React.createContext<HoverHandlers | null>(null);

function usePortHoverProps(kind: "Input" | "Output", text: string) {
  const ctx = React.useContext(HoverToastContext);
  if (!ctx) return {};
  return {
    onMouseEnter: (event: React.MouseEvent) => ctx.show(kind, text, event),
    onMouseMove: (event: React.MouseEvent) => ctx.move(event),
    onMouseLeave: () => ctx.hide(),
  };
}

function PortLabel({ kind, text }: { kind: "Input" | "Output"; text: string }) {
  const hoverProps = usePortHoverProps(kind, text);
  return (
    <span className="flow-port-name" {...hoverProps}>
      {text}
    </span>
  );
}

function ModuleNode({ data, id, selected }: NodeProps<Node<ModelNodeData>>) {
  const Icon = data.kind === "lab" ? GitBranch : FlaskConical;
  return (
    <div className={`flow-node ${selected ? "selected" : ""}`} data-node-id={id}>
      <div className="flow-node-top">
        <Icon size={14} />
        <span className="flow-node-title">{data.title}</span>
      </div>
      <div className="flow-node-subtitle">{data.subtitle}</div>
      <div className="flow-node-ports">
        <div className="flow-port-column">
          <div className="flow-port-column-label">INPUTS</div>
          {data.inputs.length === 0 ? (
            <div className="flow-port-empty">none</div>
          ) : (
            data.inputs.map((port) => (
              <div key={port} className="flow-port input">
                <Handle
                  type="target"
                  position={Position.Left}
                  id={`${data.alias}.${port}`}
                  className="flow-port-handle"
                />
                <PortLabel kind="Input" text={port} />
              </div>
            ))
          )}
        </div>
        <div className="flow-port-column">
          <div className="flow-port-column-label">OUTPUTS</div>
          {data.outputs.length === 0 ? (
            <div className="flow-port-empty">none</div>
          ) : (
            data.outputs.map((port) => (
              <div key={port} className="flow-port output">
                <Handle
                  type="source"
                  position={Position.Right}
                  id={`${data.alias}.${port}`}
                  className="flow-port-handle"
                />
                <PortLabel kind="Output" text={port} />
              </div>
            ))
          )}
        </div>
      </div>
      {data.warning ? <div className="flow-warning">{data.warning}</div> : null}
    </div>
  );
}

function WorldRailNode({
  data,
  selected,
  variant,
}: NodeProps<Node<WorldRailData>> & { variant: "inputs" | "outputs" }) {
  const isInputs = variant === "inputs";
  const handleType: "source" | "target" = isInputs ? "source" : "target";
  const handlePosition = isInputs ? Position.Right : Position.Left;
  const railPrefix = isInputs ? WORLD_INPUT_RAIL_ID : WORLD_OUTPUT_RAIL_ID;
  return (
    <div
      className={`world-rail ${variant} ${selected ? "selected" : ""}`}
      style={{
        width: 220,
        minHeight: railHeight(data.ports.length),
      }}
    >
      <div
        className="world-rail-header"
        style={{ height: RAIL_HEADER_HEIGHT }}
      >
        <Globe2 size={13} />
        <span>{isInputs ? "WORLD INPUTS" : "WORLD OUTPUTS"}</span>
      </div>
      <div
        className="world-rail-body"
        style={{ gap: RAIL_PILL_GAP, padding: `${RAIL_VERTICAL_PADDING}px 12px` }}
      >
        {data.ports.length === 0 ? (
          <div className="world-rail-empty">No {variant} defined</div>
        ) : (
          data.ports.map((port) => (
            <div
              key={port}
              className="world-rail-pill"
              style={{ height: RAIL_PILL_HEIGHT }}
            >
              <Handle
                type={handleType}
                position={handlePosition}
                id={`${railPrefix}.${port}`}
                className="world-rail-handle"
              />
              <RailPortLabel variant={variant} text={port} />
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function RailPortLabel({ variant, text }: { variant: "inputs" | "outputs"; text: string }) {
  const hoverProps = usePortHoverProps(variant === "inputs" ? "Input" : "Output", text);
  const className = variant === "inputs" ? "rail-label-right" : "rail-label-left";
  return (
    <span className={className} {...hoverProps}>
      {text}
    </span>
  );
}

const nodeTypes = {
  model: ModuleNode,
  lab: ModuleNode,
  worldInputsRail: (props: NodeProps<Node<WorldRailData>>) => (
    <WorldRailNode {...props} variant="inputs" />
  ),
  worldOutputsRail: (props: NodeProps<Node<WorldRailData>>) => (
    <WorldRailNode {...props} variant="outputs" />
  ),
};

export type CanvasProps = {
  lab: LocalLab | null;
  selection: Selection;
  onSelect: (sel: Selection) => void;
  onAddClick?: () => void;
  onLayoutChange?: (nodes: Array<{ id: string; position: { x: number; y: number } }>) => void;
  readOnly?: boolean;
};

function CanvasInner({ lab, selection, onSelect, onAddClick, onLayoutChange, readOnly }: CanvasProps) {
  const initial = React.useMemo(
    () => (lab ? buildGraph(lab) : { nodes: [] as Node[], edges: [] as Edge[] }),
    [lab],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initial.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initial.edges);

  // Re-sync both nodes and edges when the lab payload changes — useEdgesState/useNodesState
  // captures only the initial value, so without these effects the canvas stays empty when the
  // lab loads after first render (which is always the case since the fetch is async).
  React.useEffect(() => {
    setNodes(initial.nodes);
  }, [initial.nodes, setNodes]);
  React.useEffect(() => {
    setEdges(initial.edges);
  }, [initial.edges, setEdges]);

  const handleTidy = React.useCallback(() => {
    setNodes((current) => tidyLayout(current, edges));
  }, [edges, setNodes]);

  const handleNodeDragStop = React.useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (!onLayoutChange || readOnly) return;
      // Pull the latest snapshot from state.
      setNodes((current) => {
        const positions = current.map((n) => ({ id: n.id, position: n.position }));
        // Ensure the just-dragged node's position is included even if state hasn't flushed.
        const overridden = positions.map((p) =>
          p.id === node.id ? { id: p.id, position: node.position } : p,
        );
        onLayoutChange(overridden);
        return current;
      });
    },
    [onLayoutChange, readOnly, setNodes],
  );

  const handleNodeClick = React.useCallback(
    (_event: React.MouseEvent, node: Node) => {
      if (node.type === "worldInputsRail" || node.type === "worldOutputsRail") {
        onSelect({ kind: "world" });
        return;
      }
      const data = node.data as ModelNodeData | undefined;
      if (data?.kind === "lab") {
        onSelect({ kind: "lab", id: node.id });
      } else {
        onSelect({ kind: "model", id: node.id });
      }
    },
    [onSelect],
  );

  const selectedIds = React.useMemo(() => {
    if (selection.kind === "world") return new Set([WORLD_INPUT_RAIL_ID, WORLD_OUTPUT_RAIL_ID]);
    if (selection.kind === "model" || selection.kind === "lab") return new Set([selection.id]);
    return new Set<string>();
  }, [selection]);

  const decoratedNodes = React.useMemo(
    () => nodes.map((n) => ({ ...n, selected: selectedIds.has(n.id) })),
    [nodes, selectedIds],
  );

  const [hoverToast, setHoverToast] = React.useState<{
    kind: "Input" | "Output";
    text: string;
    x: number;
    y: number;
  } | null>(null);

  const hoverHandlers = React.useMemo<HoverHandlers>(
    () => ({
      show: (kind, text, event) => setHoverToast({ kind, text, x: event.clientX, y: event.clientY }),
      move: (event) =>
        setHoverToast((current) => (current ? { ...current, x: event.clientX, y: event.clientY } : current)),
      hide: () => setHoverToast(null),
    }),
    [],
  );

  return (
    <HoverToastContext.Provider value={hoverHandlers}>
    <div className="serve-canvas">
      <div className="canvas-toolbar">
        <button className="toolbar-button" onClick={handleTidy} title="Auto-arrange nodes">
          <WandSparkles size={14} />
          <span>Tidy Layout</span>
        </button>
        <div className="canvas-toolbar-spacer" />
        <span className="canvas-toolbar-stat">{lab?.manifest.models?.length ?? 0} models</span>
        <span className="canvas-toolbar-stat">{lab?.manifest.children?.length ?? 0} nested labs</span>
        <span className="canvas-toolbar-stat">{lab?.manifest.wiring?.length ?? 0} wires</span>
      </div>
      {decoratedNodes.length === 0 ? (
        <div className="empty-state">
          <FlaskConical size={28} />
          <h2>No modules in this lab</h2>
          <p>This local lab has no model or nested lab entries to draw.</p>
        </div>
      ) : (
        <ReactFlow
          nodes={decoratedNodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.2}
          maxZoom={1.6}
          nodesDraggable={!readOnly}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={handleNodeClick}
          onNodeDragStop={handleNodeDragStop}
          onPaneClick={() => onSelect({ kind: "world" })}
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
          {onAddClick ? (
            <Panel position="bottom-right" className="canvas-add-panel">
              <button
                type="button"
                className="canvas-add-button"
                onClick={onAddClick}
                title="Add model or nested lab"
              >
                <Plus size={16} />
                <span>Add</span>
              </button>
            </Panel>
          ) : null}
        </ReactFlow>
      )}
      {onAddClick && decoratedNodes.length === 0 ? (
        <button
          type="button"
          className="canvas-add-button canvas-add-button-empty"
          onClick={onAddClick}
          title="Add model or nested lab"
        >
          <Plus size={16} />
          <span>Add</span>
        </button>
      ) : null}
      {hoverToast ? <PortHoverToast toast={hoverToast} /> : null}
    </div>
    </HoverToastContext.Provider>
  );
}

function PortHoverToast({
  toast,
}: {
  toast: { kind: "Input" | "Output"; text: string; x: number; y: number };
}) {
  // Position near the cursor but clamped to the viewport so the toast never gets clipped.
  const offset = 14;
  const width = 320;
  const margin = 12;
  const viewportWidth = typeof window === "undefined" ? 1024 : window.innerWidth || 1024;
  const left = Math.min(toast.x + offset, Math.max(margin, viewportWidth - width - margin));
  const top = Math.max(margin, toast.y + offset);
  return (
    <div className="port-hover-toast" style={{ left, top, maxWidth: width }}>
      <div className="port-hover-toast-kind">{toast.kind}</div>
      <div className="port-hover-toast-text">{toast.text}</div>
    </div>
  );
}

export function Canvas(props: CanvasProps) {
  return (
    <ReactFlowProvider>
      <CanvasInner {...props} />
    </ReactFlowProvider>
  );
}
