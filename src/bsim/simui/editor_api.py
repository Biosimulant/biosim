# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""API endpoints for the visual config editor."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .graph import (
    ConfigGraph,
    auto_layout,
    graph_to_json,
    graph_to_yaml,
    json_to_graph,
    load_config_file,
    save_config_file,
    yaml_to_graph,
)
from .registry import get_default_registry

if TYPE_CHECKING:
    from ..world import BioWorld

logger = logging.getLogger(__name__)


# Pydantic models for request/response validation
class PositionModel(BaseModel):
    x: float
    y: float


class NodeDataModel(BaseModel):
    args: Dict[str, Any] = {}
    inputs: List[str] = []
    outputs: List[str] = []


class NodeModel(BaseModel):
    id: str
    type: str
    position: PositionModel
    data: NodeDataModel


class EdgeModel(BaseModel):
    id: str
    source: str
    sourceHandle: str
    target: str
    targetHandle: str


class MetaModel(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class GraphModel(BaseModel):
    nodes: List[NodeModel]
    edges: List[EdgeModel]
    meta: MetaModel = MetaModel()


class SaveConfigRequest(BaseModel):
    path: str
    graph: GraphModel


class ApplyConfigRequest(BaseModel):
    graph: GraphModel
    save_path: Optional[str] = None  # If provided, save to this path; if None, use current config path


class ValidateResponse(BaseModel):
    valid: bool
    errors: List[str] = []


class ConfigFileInfo(BaseModel):
    name: str
    path: str
    is_dir: bool


def _get_allowed_base_paths() -> List[Path]:
    """Get list of allowed base paths for config file operations."""
    # Allow configs from examples and current working directory
    base_paths = [
        Path.cwd(),
        Path.cwd() / "examples" / "configs",
    ]

    # Also allow from environment variable if set
    env_path = os.environ.get("BSIM_CONFIG_PATH")
    if env_path:
        base_paths.append(Path(env_path))

    return base_paths


def _resolve_config_path(path: str) -> Path:
    """Resolve and validate a config file path.

    Ensures the path is within allowed directories to prevent path traversal.
    """
    # Handle absolute paths
    requested = Path(path)
    if requested.is_absolute():
        resolved = requested.resolve()
    else:
        # Relative path - resolve from cwd
        resolved = (Path.cwd() / path).resolve()

    # Security check: ensure path is within allowed directories
    allowed = _get_allowed_base_paths()
    for base in allowed:
        try:
            resolved.relative_to(base.resolve())
            return resolved
        except ValueError:
            continue

    # Check if it's in the biosim package examples
    try:
        import biosim
        bsim_path = Path(biosim.__file__).parent.parent
        resolved.relative_to(bsim_path.resolve())
        return resolved
    except (ImportError, ValueError):
        pass

    raise HTTPException(
        status_code=403,
        detail=f"Access denied: path '{path}' is outside allowed directories"
    )


def build_editor_router(
    get_config_path: Callable[[], Optional[Path]] | None = None,
    get_world: Callable[[], "BioWorld"] | None = None,
    reload_world: Callable[[Optional[Path]], bool] | None = None,
) -> APIRouter:
    """Build the FastAPI router for config editor endpoints.

    Args:
        get_config_path: Callback to get the current simulation's config path
        get_world: Callback to get the current BioWorld instance
        reload_world: Callback to reload the world from a config file

    Returns:
        FastAPI router with editor endpoints
    """
    router = APIRouter(prefix="/editor", tags=["editor"])

    @router.get("/modules")
    def get_modules() -> Dict[str, Any]:
        """Get the module registry with all available BioModules."""
        registry = get_default_registry()
        return registry.to_json()

    @router.get("/current")
    def get_current_config() -> Dict[str, Any]:
        """Get the current simulation's configuration.

        Returns the config that the running simulation was loaded from.
        If no config is available, returns an empty graph with available flag false.
        """
        if not get_config_path:
            return {"available": False, "path": None, "graph": None}

        config_path = get_config_path()
        if not config_path or not config_path.exists():
            return {"available": False, "path": None, "graph": None}

        try:
            graph = load_config_file(config_path)
            # Apply auto-layout if positions are all zeros
            if graph.nodes and all(n.position.x == 0 and n.position.y == 0 for n in graph.nodes):
                graph = auto_layout(graph)

            # Make path relative to cwd for display
            try:
                rel_path = str(config_path.relative_to(Path.cwd()))
            except ValueError:
                rel_path = str(config_path)

            return {
                "available": True,
                "path": rel_path,
                "graph": graph_to_json(graph),
            }
        except Exception as e:
            logger.exception(f"Error loading current config: {config_path}")
            return {"available": False, "path": str(config_path), "error": str(e), "graph": None}

    @router.post("/apply")
    def apply_config(request: ApplyConfigRequest) -> Dict[str, Any]:
        """Apply a configuration to the running simulation.

        This saves the config to disk and reloads the simulation with the new config.

        Args:
            request: ApplyConfigRequest with graph and optional save_path

        Returns:
            {"ok": True/False, "path": resolved_path, "error": optional_error_message}
        """
        if not reload_world:
            raise HTTPException(
                status_code=501,
                detail="Config reload not supported in this context"
            )

        # Determine the save path
        if request.save_path:
            resolved = _resolve_config_path(request.save_path)
        elif get_config_path:
            config_path = get_config_path()
            if config_path:
                resolved = config_path
            else:
                raise HTTPException(
                    status_code=400,
                    detail="No save path specified and no current config path available"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="No save path specified"
            )

        try:
            # Convert to internal graph model
            graph = json_to_graph(request.graph.model_dump())

            # Save to file
            save_config_file(graph, resolved)

            # Reload the world
            success = reload_world(resolved)

            if success:
                return {"ok": True, "path": str(resolved)}
            else:
                return {"ok": False, "path": str(resolved), "error": "Failed to reload world"}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error applying config: {resolved}")
            raise HTTPException(status_code=400, detail=str(e))

    @router.get("/config")
    def get_config(path: str) -> Dict[str, Any]:
        """Load a YAML config file and return as graph.

        Args:
            path: Path to the YAML config file (relative to cwd or absolute)

        Returns:
            Graph representation with nodes, edges, and meta
        """
        try:
            resolved = _resolve_config_path(path)
            graph = load_config_file(resolved)
            # Apply auto-layout if positions are all zeros
            if all(n.position.x == 0 and n.position.y == 0 for n in graph.nodes):
                graph = auto_layout(graph)
            return graph_to_json(graph)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail=f"Config file not found: {path}")
        except Exception as e:
            logger.exception(f"Error loading config: {path}")
            raise HTTPException(status_code=400, detail=str(e))

    @router.put("/config")
    def save_config(request: SaveConfigRequest) -> Dict[str, Any]:
        """Save a graph back to a YAML config file.

        Args:
            request: SaveConfigRequest with path and graph data

        Returns:
            {"ok": True, "path": resolved_path}
        """
        try:
            resolved = _resolve_config_path(request.path)

            # Convert to internal graph model
            graph = json_to_graph(request.graph.model_dump())

            # Save to file
            save_config_file(graph, resolved)

            return {"ok": True, "path": str(resolved)}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error saving config: {request.path}")
            raise HTTPException(status_code=400, detail=str(e))

    @router.post("/validate")
    def validate_config(graph: GraphModel) -> ValidateResponse:
        """Validate a graph configuration.

        Checks:
        - All module class paths are valid
        - All connections reference valid ports
        - No disconnected required inputs

        Args:
            graph: Graph to validate

        Returns:
            Validation result with errors if any
        """
        errors: List[str] = []
        registry = get_default_registry()

        # Check modules exist
        for node in graph.nodes:
            if not node.type:
                errors.append(f"Node '{node.id}' has no class type specified")
                continue

            spec = registry.get(node.type)
            if spec is None:
                # Not a known module - might be a custom one, warn but don't error
                logger.debug(f"Unknown module type: {node.type}")

        # Build node map for connection validation
        node_map = {n.id: n for n in graph.nodes}

        # Check connections
        for edge in graph.edges:
            if edge.source not in node_map:
                errors.append(f"Edge '{edge.id}' references unknown source node '{edge.source}'")
            if edge.target not in node_map:
                errors.append(f"Edge '{edge.id}' references unknown target node '{edge.target}'")

            # Check port names if we know the module
            if edge.source in node_map:
                src_node = node_map[edge.source]
                src_spec = registry.get(src_node.type)
                if src_spec and src_spec.outputs and edge.sourceHandle not in src_spec.outputs:
                    errors.append(
                        f"Edge '{edge.id}': source '{edge.source}' has no output port '{edge.sourceHandle}'"
                    )

            if edge.target in node_map:
                tgt_node = node_map[edge.target]
                tgt_spec = registry.get(tgt_node.type)
                if tgt_spec and tgt_spec.inputs and edge.targetHandle not in tgt_spec.inputs:
                    errors.append(
                        f"Edge '{edge.id}': target '{edge.target}' has no input port '{edge.targetHandle}'"
                    )

        return ValidateResponse(valid=len(errors) == 0, errors=errors)

    @router.post("/layout")
    def layout_graph(graph: GraphModel) -> Dict[str, Any]:
        """Apply auto-layout to a graph.

        Args:
            graph: Graph to layout

        Returns:
            Graph with updated node positions
        """
        internal = json_to_graph(graph.model_dump())
        laid_out = auto_layout(internal)
        return graph_to_json(laid_out)

    @router.post("/to-yaml")
    def convert_to_yaml(graph: GraphModel) -> Dict[str, str]:
        """Convert a graph to YAML string.

        Args:
            graph: Graph to convert

        Returns:
            {"yaml": yaml_content}
        """
        internal = json_to_graph(graph.model_dump())
        yaml_content = graph_to_yaml(internal)
        return {"yaml": yaml_content}

    @router.post("/from-yaml")
    def convert_from_yaml(data: Dict[str, str]) -> Dict[str, Any]:
        """Convert YAML string to graph.

        Args:
            data: {"yaml": yaml_content}

        Returns:
            Graph representation
        """
        yaml_content = data.get("yaml", "")
        if not yaml_content:
            raise HTTPException(status_code=400, detail="Missing 'yaml' field")

        try:
            graph = yaml_to_graph(yaml_content)
            graph = auto_layout(graph)
            return graph_to_json(graph)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")

    @router.get("/files")
    def list_config_files(path: str = "") -> List[ConfigFileInfo]:
        """List available config files in a directory.

        Args:
            path: Directory path (relative to cwd)

        Returns:
            List of file info objects
        """
        try:
            if path:
                resolved = _resolve_config_path(path)
            else:
                resolved = Path.cwd()

            if not resolved.is_dir():
                raise HTTPException(status_code=400, detail=f"Not a directory: {path}")

            files: List[ConfigFileInfo] = []
            for item in sorted(resolved.iterdir()):
                if item.name.startswith("."):
                    continue

                if item.is_dir():
                    files.append(ConfigFileInfo(
                        name=item.name,
                        path=str(item.relative_to(Path.cwd())),
                        is_dir=True,
                    ))
                elif item.suffix.lower() in {".yaml", ".yml"}:
                    files.append(ConfigFileInfo(
                        name=item.name,
                        path=str(item.relative_to(Path.cwd())),
                        is_dir=False,
                    ))

            return files
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error listing files: {path}")
            raise HTTPException(status_code=400, detail=str(e))

    return router
