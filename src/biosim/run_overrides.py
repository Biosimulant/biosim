# SPDX-FileCopyrightText: 2026-present Biosimulant Team
#
# SPDX-License-Identifier: MIT
"""Shared parameter and runtime overlays for local lab runs."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _initial_input_ref_parts(
    ref: str,
    aliases: set[str] | None = None,
) -> tuple[str, str] | None:
    if aliases:
        matching_aliases = [
            alias
            for alias in aliases
            if ref.startswith(f"{alias}.") and len(ref) > len(alias) + 1
        ]
        if matching_aliases:
            alias = max(matching_aliases, key=len)
            return alias, ref[len(alias) + 1 :]
    if ref.count(".") != 1:
        return None
    alias, port = ref.split(".", 1)
    if not alias or not port:
        return None
    return alias, port


def _merge_nested_input(
    output: dict[str, Any],
    alias: str,
    values: Mapping[str, Any],
) -> None:
    current = output.get(alias)
    if isinstance(current, dict):
        current.update(dict(values))
    else:
        output[alias] = dict(values)


def map_initial_inputs(
    manifest: Mapping[str, Any],
    value: Any,
) -> dict[str, Any]:
    """Map public or dotted input names to their model-local input structure."""

    if not isinstance(value, Mapping):
        return {}
    name_to_ref: dict[str, str] = {}
    model_aliases: set[str] = set()
    models = manifest.get("models")
    if isinstance(models, list):
        for entry in models:
            if isinstance(entry, Mapping) and isinstance(entry.get("alias"), str):
                model_aliases.add(str(entry["alias"]))
    io = manifest.get("io")
    if isinstance(io, Mapping):
        inputs = io.get("inputs")
        if isinstance(inputs, list):
            for port in inputs:
                if not isinstance(port, Mapping):
                    continue
                name = port.get("name")
                maps_to = port.get("maps_to")
                if isinstance(name, str) and isinstance(maps_to, str):
                    name_to_ref[name] = maps_to
    output: dict[str, Any] = {}
    for key, raw in value.items():
        text_key = str(key)
        mapped_ref = name_to_ref.get(text_key)
        if mapped_ref:
            parts = _initial_input_ref_parts(mapped_ref, model_aliases)
            if parts:
                alias, port = parts
                _merge_nested_input(output, alias, {port: raw})
            else:
                output[mapped_ref] = raw
            continue
        if text_key in model_aliases and isinstance(raw, Mapping):
            _merge_nested_input(output, text_key, raw)
            continue
        parts = _initial_input_ref_parts(text_key, model_aliases)
        if parts:
            alias, port = parts
            _merge_nested_input(output, alias, {port: raw})
            continue
        output[text_key] = raw
    return output


def _merge_initial_inputs(
    current: dict[str, Any],
    overlay: Mapping[str, Any],
) -> None:
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(current.get(key), dict):
            current[key].update(dict(value))
        elif isinstance(value, Mapping):
            current[key] = dict(value)
        else:
            current[key] = value


def apply_run_overrides(
    manifest: dict[str, Any],
    *,
    parameters: Any,
    simulation_config: Any,
) -> None:
    """Apply Desktop/Studio run inputs without mutating the saved lab."""

    runtime = manifest.setdefault("runtime", {})
    if not isinstance(runtime, dict):
        runtime = {}
        manifest["runtime"] = runtime
    if isinstance(simulation_config, Mapping):
        for key in ("duration", "communication_step", "settle_steps"):
            if key in simulation_config and simulation_config[key] is not None:
                runtime[key] = simulation_config[key]
    if isinstance(parameters, Mapping):
        initial_overlay = map_initial_inputs(
            manifest,
            parameters.get("initial_inputs"),
        )
        if initial_overlay:
            current = runtime.get("initial_inputs")
            if not isinstance(current, dict):
                current = {}
                runtime["initial_inputs"] = current
            _merge_initial_inputs(current, initial_overlay)
        per_model = parameters.get("per_model")
        models = manifest.get("models")
        if isinstance(per_model, Mapping) and isinstance(models, list):
            for entry in models:
                if not isinstance(entry, dict):
                    continue
                alias = entry.get("alias")
                overlay = per_model.get(alias) if isinstance(alias, str) else None
                if isinstance(overlay, Mapping):
                    entry["parameters"] = dict(overlay)
