"""Canonical lab-tree flattening for Biosimulant runtimes."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Mapping

from .types import (
    FlattenedLab,
    LabTree,
    LabTreeChild,
    LabTreeIO,
    LabTreeModel,
    LabTreePort,
    LabTreeWire,
)


def _raise(error_cls: type[Exception], message: str) -> None:
    raise error_cls(message)


def _scoped_ref(prefix: str, ref: str) -> str:
    return f"{prefix}{ref}" if prefix else ref


def _model_entry(model: LabTreeModel, alias: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"alias": alias}
    if isinstance(model.ref, Mapping):
        entry.update(dict(model.ref))
    elif model.ref is not None:
        entry["ref"] = model.ref
    if model.parameters:
        entry["parameters"] = dict(model.parameters)
    if model.module_config:
        entry["module_config"] = dict(model.module_config)
    return entry


def _port_remap_for_child(prefix: str, child: LabTreeChild) -> dict[str, str]:
    remap: dict[str, str] = {}
    if child.tree is None:
        return remap
    child_io = child.io or child.tree.io or LabTreeIO()
    external_prefix = _scoped_ref(prefix, f"{child.alias}.")
    child_prefix = _scoped_ref(prefix, f"{child.alias}.")
    for port in [*list(child_io.inputs), *list(child_io.outputs)]:
        if not isinstance(port.name, str) or not isinstance(port.maps_to, str):
            continue
        remap[f"{external_prefix}{port.name}"] = f"{child_prefix}{port.maps_to}"
    return remap


def flatten_lab_tree(
    tree: LabTree,
    *,
    max_depth: int = 5,
    error_cls: type[Exception] = RuntimeError,
) -> FlattenedLab:
    """Flatten a source-neutral lab tree into scoped models and wiring."""

    def _flatten(
        current: LabTree, *, prefix: str, depth: int, seen: set[int]
    ) -> FlattenedLab:
        if depth > max_depth:
            _raise(error_cls, f"Lab nesting exceeds maximum depth of {max_depth}")
        current_key = id(current)
        if current_key in seen:
            _raise(error_cls, "Circular child lab reference detected")
        next_seen = {*seen, current_key}

        flat_models: list[dict[str, Any]] = []
        flat_wiring: list[dict[str, Any]] = []
        port_remap: dict[str, str] = {}

        for model in current.models:
            if not isinstance(model.alias, str) or not model.alias.strip():
                _raise(error_cls, "Lab model entries require a non-empty alias")
            flat_models.append(_model_entry(model, _scoped_ref(prefix, model.alias)))

        for child in current.children:
            if not isinstance(child.alias, str) or not child.alias.strip():
                _raise(error_cls, "Lab child entries require a non-empty alias")
            if child.tree is None:
                _raise(error_cls, f"Child lab '{child.alias}' is unresolved")
            child_prefix = _scoped_ref(prefix, f"{child.alias}.")
            child_flat = _flatten(
                child.tree, prefix=child_prefix, depth=depth + 1, seen=next_seen
            )
            flat_models.extend(child_flat.models)
            flat_wiring.extend(child_flat.wiring)
            port_remap.update(_port_remap_for_child(prefix, child))

        for wire in current.wiring:
            if not isinstance(wire.from_ref, str) or not wire.from_ref.strip():
                _raise(error_cls, "Wiring entries require a non-empty from ref")
            scoped_from = _scoped_ref(prefix, wire.from_ref)
            normalized_targets: list[str] = []
            for target in wire.to_refs:
                if not isinstance(target, str) or not target.strip():
                    _raise(error_cls, "Wiring targets must be non-empty strings")
                scoped_to = _scoped_ref(prefix, target)
                normalized_targets.append(port_remap.get(scoped_to, scoped_to))
            flat_wiring.append(
                {
                    "from": port_remap.get(scoped_from, scoped_from),
                    "to": normalized_targets,
                }
            )

        return FlattenedLab(models=flat_models, wiring=flat_wiring)

    return _flatten(tree, prefix="", depth=0, seen=set())


def lab_io_from_mapping(value: Any) -> LabTreeIO:
    if not isinstance(value, Mapping):
        return LabTreeIO()

    def _ports(items: Any) -> list[LabTreePort]:
        ports: list[LabTreePort] = []
        if not isinstance(items, list):
            return ports
        for item in items:
            if is_dataclass(item):
                item = asdict(item)
            if not isinstance(item, Mapping):
                continue
            name = item.get("name")
            maps_to = item.get("maps_to")
            if isinstance(name, str) and isinstance(maps_to, str):
                ports.append(LabTreePort(name=name, maps_to=maps_to))
        return ports

    return LabTreeIO(
        inputs=_ports(value.get("inputs")), outputs=_ports(value.get("outputs"))
    )
