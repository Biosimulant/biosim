# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Graph model and YAML conversion utilities for config editor."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .registry import get_default_registry


@dataclass
class Position:
    """2D position for node layout."""
    x: float = 0.0
    y: float = 0.0


@dataclass
class GraphNode:
    """A node in the config graph representing a module instance."""
    id: str  # Module name (e.g., "rabbits")
    type: str  # Class path (e.g., "biosim.packs.ecology.OrganismPopulation")
    position: Position = field(default_factory=Position)
    args: Dict[str, Any] = field(default_factory=dict)
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)


@dataclass
class GraphEdge:
    """An edge in the config graph representing a wiring connection."""
    id: str
    source: str  # Source node id
    source_handle: str  # Output port name
    target: str  # Target node id
    target_handle: str  # Input port name


@dataclass
class ConfigMeta:
    """Metadata section from config."""
    title: Optional[str] = None
    description: Optional[str] = None


@dataclass
class ConfigGraph:
    """Complete graph representation of a configuration."""
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    meta: ConfigMeta = field(default_factory=ConfigMeta)


def _parse_ref(ref: str) -> Tuple[str, str]:
    """Parse references like "eye.visual_stream".

    Returns (name, port).
    """
    parts = ref.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid reference '{ref}', expected 'name.port' form")
    return parts[0], parts[1]


def yaml_to_graph(yaml_content: str) -> ConfigGraph:
    """Convert YAML config content to a ConfigGraph.

    Args:
        yaml_content: Raw YAML string

    Returns:
        ConfigGraph with nodes and edges
    """
    config = yaml.safe_load(yaml_content)
    if not isinstance(config, dict):
        raise ValueError("YAML must parse to a dictionary")

    graph = ConfigGraph()
    registry = get_default_registry()

    # Parse meta section
    meta_section = config.get("meta", {})
    if isinstance(meta_section, dict):
        graph.meta = ConfigMeta(
            title=meta_section.get("title"),
            description=meta_section.get("description"),
        )

    # Parse modules section
    modules_section = config.get("modules", {})
    if isinstance(modules_section, dict):
        for name, entry in modules_section.items():
            if isinstance(entry, str):
                class_path = entry
                args = {}
            elif isinstance(entry, dict):
                class_path = entry.get("class", "")
                args = entry.get("args", {}) or {}
            else:
                continue

            # Get port info from registry
            module_spec = registry.get(class_path)
            if module_spec:
                inputs = list(module_spec.inputs)
                outputs = list(module_spec.outputs)
            else:
                # Unknown module - try to infer from wiring later
                inputs = []
                outputs = []

            node = GraphNode(
                id=name,
                type=class_path,
                args=dict(args) if isinstance(args, dict) else {},
                inputs=inputs,
                outputs=outputs,
            )
            graph.nodes.append(node)

    # Build a map for quick node lookup
    node_map = {n.id: n for n in graph.nodes}

    # Parse wiring section
    wiring_section = config.get("wiring", [])
    edge_counter = 0
    if isinstance(wiring_section, list):
        for entry in wiring_section:
            if not isinstance(entry, dict):
                continue

            src = entry.get("from", "")
            targets = entry.get("to", [])

            if not isinstance(src, str):
                continue
            if isinstance(targets, str):
                targets = [targets]
            if not isinstance(targets, list):
                continue

            try:
                src_name, src_port = _parse_ref(src)
            except ValueError:
                continue

            # Ensure source node has this output port listed
            if src_name in node_map:
                src_node = node_map[src_name]
                if src_port not in src_node.outputs:
                    src_node.outputs.append(src_port)

            for target in targets:
                if not isinstance(target, str):
                    continue
                try:
                    tgt_name, tgt_port = _parse_ref(target)
                except ValueError:
                    continue

                # Ensure target node has this input port listed
                if tgt_name in node_map:
                    tgt_node = node_map[tgt_name]
                    if tgt_port not in tgt_node.inputs:
                        tgt_node.inputs.append(tgt_port)

                edge_counter += 1
                edge = GraphEdge(
                    id=f"e{edge_counter}",
                    source=src_name,
                    source_handle=src_port,
                    target=tgt_name,
                    target_handle=tgt_port,
                )
                graph.edges.append(edge)

    return graph


def graph_to_yaml(graph: ConfigGraph) -> str:
    """Convert a ConfigGraph back to YAML.

    Args:
        graph: ConfigGraph with nodes and edges

    Returns:
        YAML string
    """
    config: Dict[str, Any] = {}

    # Build meta section
    if graph.meta.title or graph.meta.description:
        meta: Dict[str, Any] = {}
        if graph.meta.title:
            meta["title"] = graph.meta.title
        if graph.meta.description:
            meta["description"] = graph.meta.description
        config["meta"] = meta

    # Build modules section
    if graph.nodes:
        modules: Dict[str, Any] = {}
        for node in graph.nodes:
            if node.args:
                modules[node.id] = {
                    "class": node.type,
                    "args": node.args,
                }
            else:
                modules[node.id] = {
                    "class": node.type,
                }
        config["modules"] = modules

    # Build wiring section - group by source for cleaner output
    if graph.edges:
        wiring_map: Dict[str, List[str]] = defaultdict(list)
        for edge in graph.edges:
            src_ref = f"{edge.source}.{edge.source_handle}"
            tgt_ref = f"{edge.target}.{edge.target_handle}"
            wiring_map[src_ref].append(tgt_ref)

        wiring: List[Dict[str, Any]] = []
        for src_ref, targets in wiring_map.items():
            wiring.append({"from": src_ref, "to": targets})
        config["wiring"] = wiring

    # Custom YAML representer for cleaner output
    class CleanDumper(yaml.SafeDumper):
        pass

    def str_representer(dumper: yaml.Dumper, data: str) -> yaml.Node:
        if "\n" in data:
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    CleanDumper.add_representer(str, str_representer)

    return yaml.dump(config, Dumper=CleanDumper, sort_keys=False, default_flow_style=False)


def load_config_file(path: str | Path) -> ConfigGraph:
    """Load a YAML config file and convert to graph.

    Args:
        path: Path to the YAML file

    Returns:
        ConfigGraph
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with p.open("r", encoding="utf-8") as f:
        content = f.read()

    return yaml_to_graph(content)


def save_config_file(graph: ConfigGraph, path: str | Path) -> None:
    """Save a ConfigGraph to a YAML file.

    Args:
        graph: ConfigGraph to save
        path: Path to save to
    """
    p = Path(path)
    content = graph_to_yaml(graph)

    # Ensure parent directory exists
    p.parent.mkdir(parents=True, exist_ok=True)

    with p.open("w", encoding="utf-8") as f:
        f.write(content)


def graph_to_json(graph: ConfigGraph) -> Dict[str, Any]:
    """Convert a ConfigGraph to JSON-serializable format for the frontend.

    Args:
        graph: ConfigGraph

    Returns:
        JSON-serializable dict with nodes, edges, and meta
    """
    nodes = [
        {
            "id": node.id,
            "type": node.type,
            "position": {"x": node.position.x, "y": node.position.y},
            "data": {
                "args": node.args,
                "inputs": node.inputs,
                "outputs": node.outputs,
            },
        }
        for node in graph.nodes
    ]

    edges = [
        {
            "id": edge.id,
            "source": edge.source,
            "sourceHandle": edge.source_handle,
            "target": edge.target,
            "targetHandle": edge.target_handle,
        }
        for edge in graph.edges
    ]

    meta = {
        "title": graph.meta.title,
        "description": graph.meta.description,
    }

    return {"nodes": nodes, "edges": edges, "meta": meta}


def json_to_graph(data: Dict[str, Any]) -> ConfigGraph:
    """Convert JSON data from frontend to a ConfigGraph.

    Args:
        data: JSON dict with nodes, edges, and meta

    Returns:
        ConfigGraph
    """
    graph = ConfigGraph()

    # Parse meta
    meta = data.get("meta", {})
    if isinstance(meta, dict):
        graph.meta = ConfigMeta(
            title=meta.get("title"),
            description=meta.get("description"),
        )

    # Parse nodes
    nodes_data = data.get("nodes", [])
    for node_data in nodes_data:
        if not isinstance(node_data, dict):
            continue

        pos_data = node_data.get("position", {})
        data_section = node_data.get("data", {})

        node = GraphNode(
            id=node_data.get("id", ""),
            type=node_data.get("type", ""),
            position=Position(
                x=float(pos_data.get("x", 0)),
                y=float(pos_data.get("y", 0)),
            ),
            args=data_section.get("args", {}),
            inputs=data_section.get("inputs", []),
            outputs=data_section.get("outputs", []),
        )
        graph.nodes.append(node)

    # Parse edges
    edges_data = data.get("edges", [])
    for edge_data in edges_data:
        if not isinstance(edge_data, dict):
            continue

        edge = GraphEdge(
            id=edge_data.get("id", ""),
            source=edge_data.get("source", ""),
            source_handle=edge_data.get("sourceHandle", ""),
            target=edge_data.get("target", ""),
            target_handle=edge_data.get("targetHandle", ""),
        )
        graph.edges.append(edge)

    return graph


def auto_layout(graph: ConfigGraph, node_width: float = 200, node_height: float = 100) -> ConfigGraph:
    """Apply automatic layout to graph nodes using a simple layered algorithm.

    This is a basic left-to-right layout. For better results, use dagre on the frontend.

    Args:
        graph: ConfigGraph to layout
        node_width: Width of each node
        node_height: Height of each node

    Returns:
        Graph with updated positions
    """
    if not graph.nodes:
        return graph

    # Build dependency graph
    node_ids = {n.id for n in graph.nodes}
    incoming: Dict[str, set] = {n.id: set() for n in graph.nodes}
    outgoing: Dict[str, set] = {n.id: set() for n in graph.nodes}

    for edge in graph.edges:
        if edge.source in node_ids and edge.target in node_ids:
            outgoing[edge.source].add(edge.target)
            incoming[edge.target].add(edge.source)

    # Topological sort to determine layers
    layers: List[List[str]] = []
    remaining = set(node_ids)

    while remaining:
        # Find nodes with no incoming edges from remaining nodes
        layer = []
        for node_id in remaining:
            deps = incoming[node_id] & remaining
            if not deps:
                layer.append(node_id)

        if not layer:
            # Cycle detected - just add remaining nodes
            layer = list(remaining)

        layers.append(layer)
        remaining -= set(layer)

    # Assign positions
    x_spacing = node_width + 80
    y_spacing = node_height + 40
    node_map = {n.id: n for n in graph.nodes}

    for layer_idx, layer in enumerate(layers):
        x = layer_idx * x_spacing + 50
        for row_idx, node_id in enumerate(layer):
            y = row_idx * y_spacing + 50
            if node_id in node_map:
                node_map[node_id].position = Position(x=x, y=y)

    return graph
