from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict, Union
import json


class VisualSpec(TypedDict, total=False):
    """Renderer-agnostic visual specification for browser clients.

    Required keys:
    - render: the visual type (e.g., 'timeseries', 'bar', 'graph', 'table', 'image', 'text', 'structure3d', 'custom:...')
    - data: JSON-serializable data payload interpreted by the client renderer for the given render type
    """

    render: str
    data: Dict[str, Any]
    description: str


Visuals = Union[VisualSpec, List[VisualSpec]]
VisualCapability = Literal["3d-capable", "non-3d", "no-visuals", "conditional"]


def validate_visual_spec(spec: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate that a dict conforms to the VisualSpec shape and is JSON-serializable.

    Returns (ok, error_message). When ok is False, error_message contains a brief reason.
    """
    if not isinstance(spec, dict):
        return False, "visual must be a dict"
    if "render" not in spec:
        return False, "missing 'render' key"
    if "data" not in spec:
        return False, "missing 'data' key"
    render = spec["render"]
    if not isinstance(render, str) or not render:
        return False, "'render' must be a non-empty string"
    data = spec["data"]
    if not isinstance(data, dict):
        return False, "'data' must be a dict"
    if "description" in spec and not isinstance(spec["description"], str):
        return False, "'description' must be a string"
    # Check JSON serializability (best-effort)
    try:
        # Include optional fields that the UI may rely on.
        payload: Dict[str, Any] = {"render": render, "data": data}
        if "description" in spec:
            payload["description"] = spec["description"]
        json.dumps(payload)
    except TypeError as exc:
        return False, f"data not JSON-serializable: {exc}"
    return True, None


def normalize_visuals(visuals: Visuals) -> List[VisualSpec]:
    """Normalize a single VisualSpec or list into a list of VisualSpec.

    Invalid entries are filtered out.
    """
    items: List[Dict[str, Any]]
    if isinstance(visuals, list):
        items = visuals  # type: ignore[assignment]
    else:
        items = [visuals]  # type: ignore[list-item]
    out: List[VisualSpec] = []
    for v in items:
        ok, _ = validate_visual_spec(v)
        if ok:
            normed: Dict[str, Any] = {"render": v["render"], "data": v["data"]}
            if "description" in v and isinstance(v["description"], str):
                normed["description"] = v["description"]
            out.append(normed)  # type: ignore[arg-type]
    return out


def classify_visual_capability(
    visuals: Visuals | None,
    *,
    conditional_when_empty: bool = False,
) -> VisualCapability:
    """Classify a module or lab visual payload for renderer coverage audits."""
    if not visuals:
        return "conditional" if conditional_when_empty else "no-visuals"
    normalized = normalize_visuals(visuals)
    if not normalized:
        return "no-visuals"
    if any(visual["render"].lower() == "structure3d" for visual in normalized):
        return "3d-capable"
    return "non-3d"
