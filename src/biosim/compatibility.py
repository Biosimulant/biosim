"""Optional integration with the BioSimulant Model Compatibility Standard.

Legacy manifests do not need the optional dependency. Once a manifest opts in,
the pinned standard package is required so invalid claims cannot silently fall
back to structural-only behavior.
"""

from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Any, Mapping

from .modules import BioModule
from .signals import SignalSpec


class CompatibilitySupportUnavailable(RuntimeError):
    pass


def _standard():
    try:
        import biosimulant_model_compatibility_standard as standard
    except ImportError as exc:
        raise CompatibilitySupportUnavailable(
            "Compatibility support requires "
            "the pinned biosimulant-model-compatibility-standard bundle. "
            "Install biosimulant[compatibility]."
        ) from exc
    return standard


def validate_manifest(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    if "compatibility" not in manifest:
        return []
    return [finding.to_dict() for finding in _standard().validate_manifest(dict(manifest))]


def normalize_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if "compatibility" not in manifest:
        return dict(manifest)
    return _standard().normalize_manifest(dict(manifest))


def compare_contracts(source: Mapping[str, Any] | None, target: Mapping[str, Any] | None, **kwargs: Any) -> dict[str, Any]:
    return _standard().compare_contracts(
        dict(source) if source is not None else None,
        dict(target) if target is not None else None,
        **kwargs,
    )


def resolve_contracts(
    source: Mapping[str, Any] | None,
    target: Mapping[str, Any] | None,
    capabilities: list[Mapping[str, Any]] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    return _standard().resolve_contracts(
        dict(source) if source is not None else None,
        dict(target) if target is not None else None,
        [dict(item) for item in capabilities or []],
        **kwargs,
    )


def build_lock(manifest: Mapping[str, Any]) -> dict[str, Any] | None:
    if "compatibility" not in manifest:
        return None
    return _standard().build_compatibility_lock(dict(manifest))


def lock_bytes(manifest: Mapping[str, Any]) -> bytes | None:
    lock = build_lock(manifest)
    if lock is None:
        return None
    return (json.dumps(lock, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


_PORT_FIELDS = (
    "signal_type",
    "kind",
    "dtype",
    "shape",
    "schema",
    "emitted_unit",
    "interpolation",
    "max_age",
    "stale_policy",
)
_PROFILE_FIELDS = ("signal_type", "dtype", "shape", "schema", "accepted_units")


def _shape_matches(declared: Any, implemented: Any) -> bool:
    if declared is None or implemented is None:
        return declared is implemented
    if not isinstance(declared, (list, tuple)) or not isinstance(implemented, (list, tuple)):
        return declared == implemented
    if len(declared) != len(implemented):
        return False
    return all(
        expected in {"*", None} or expected == actual
        for expected, actual in zip(declared, implemented)
    )


def _field_matches(field: str, declared: Any, implemented: Any) -> bool:
    if field == "shape":
        return _shape_matches(declared, implemented)
    if field in {"schema"} and isinstance(declared, Mapping) and isinstance(implemented, Mapping):
        return dict(declared) == dict(implemented)
    if field == "accepted_units" and isinstance(declared, (list, tuple)) and isinstance(implemented, (list, tuple)):
        return tuple(declared) == tuple(implemented)
    return declared == implemented


def _ports_by_name(manifest: Mapping[str, Any], direction: str) -> dict[str, dict[str, Any]]:
    io = manifest.get("io")
    raw = io.get(direction) if isinstance(io, Mapping) else None
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError(f"io.{direction} must be a list")
    ports: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(raw):
        if not isinstance(value, Mapping):
            raise ValueError(f"io.{direction}[{index}] must be an object")
        name = value.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"io.{direction}[{index}].name must be a non-empty string")
        if name in ports:
            raise ValueError(f"io.{direction} contains duplicate port '{name}'")
        ports[name] = dict(value)
    return ports


def _check_fields(
    *,
    label: str,
    declared: Mapping[str, Any],
    implemented: Mapping[str, Any],
    fields: tuple[str, ...],
) -> None:
    for field in fields:
        if field not in declared:
            continue
        expected = declared[field]
        actual = implemented.get(field)
        if not _field_matches(field, expected, actual):
            raise ValueError(
                f"{label}.{field} contradicts Python: manifest={expected!r}, Python={actual!r}"
            )


def _bind_port(
    *,
    direction: str,
    name: str,
    declared: Mapping[str, Any],
    implemented: SignalSpec,
) -> SignalSpec:
    implemented_data = implemented.to_dict()
    label = f"io.{direction}.{name}"
    _check_fields(
        label=label,
        declared=declared,
        implemented=implemented_data,
        fields=_PORT_FIELDS,
    )

    declared_profiles = declared.get("accepted_profiles")
    if declared_profiles is not None:
        if direction != "inputs":
            raise ValueError(f"{label}.accepted_profiles is only valid on inputs")
        if not isinstance(declared_profiles, list):
            raise ValueError(f"{label}.accepted_profiles must be a list")
        implemented_profiles = implemented_data.get("accepted_profiles")
        if implemented_profiles is None:
            if declared_profiles:
                raise ValueError(
                    f"{label}.accepted_profiles contradicts Python: the manifest declares "
                    f"{len(declared_profiles)} profile(s), Python declares none"
                )
            implemented_profiles = []
        if len(declared_profiles) != len(implemented_profiles):
            raise ValueError(
                f"{label}.accepted_profiles contradicts Python: manifest has "
                f"{len(declared_profiles)}, Python has {len(implemented_profiles)}"
            )
        for index, declared_profile in enumerate(declared_profiles):
            if not isinstance(declared_profile, Mapping):
                raise ValueError(f"{label}.accepted_profiles[{index}] must be an object")
            _check_fields(
                label=f"{label}.accepted_profiles[{index}]",
                declared=declared_profile,
                implemented=implemented_profiles[index],
                fields=_PROFILE_FIELDS,
            )
            if "contract" in declared_profile:
                implemented_profiles[index]["contract"] = copy.deepcopy(
                    declared_profile["contract"]
                )
        implemented_data["accepted_profiles"] = implemented_profiles or None

    if "contract" in declared:
        implemented_data["contract"] = copy.deepcopy(declared["contract"])
    return SignalSpec.from_dict(implemented_data)


def bind_manifest_ports(
    module: BioModule, manifest: Mapping[str, Any]
) -> tuple[dict[str, SignalSpec], dict[str, SignalSpec]]:
    """Verify and bind an opted-in manifest to one instantiated BioModule.

    Structural declarations remain executable Python invariants, but the
    packaged manifest is authoritative for biological compatibility metadata.
    The bound maps are consumed by BioWorld without modifying the model class.
    """

    raw_inputs = module.inputs()
    raw_outputs = module.outputs()
    if not isinstance(raw_inputs, Mapping) or not isinstance(raw_outputs, Mapping):
        raise ValueError("Python inputs() and outputs() must return mappings")

    code_inputs = {
        name: spec if isinstance(spec, SignalSpec) else SignalSpec.from_dict(spec)
        for name, spec in raw_inputs.items()
    }
    code_outputs = {
        name: spec if isinstance(spec, SignalSpec) else SignalSpec.from_dict(spec)
        for name, spec in raw_outputs.items()
    }
    manifest_inputs = _ports_by_name(manifest, "inputs")
    manifest_outputs = _ports_by_name(manifest, "outputs")

    for label, declared, implemented in (
        ("input", manifest_inputs, code_inputs),
        ("output", manifest_outputs, code_outputs),
    ):
        missing = sorted(set(declared) - set(implemented))
        extra = sorted(set(implemented) - set(declared))
        if missing or extra:
            details: list[str] = []
            if missing:
                details.append(f"missing in Python: {', '.join(missing)}")
            if extra:
                details.append(f"missing in manifest: {', '.join(extra)}")
            raise ValueError(f"Manifest/Python {label} ports contradict ({'; '.join(details)})")

    bound_inputs = {
        name: _bind_port(
            direction="inputs",
            name=name,
            declared=manifest_inputs[name],
            implemented=spec,
        )
        for name, spec in code_inputs.items()
    }
    bound_outputs = {
        name: _bind_port(
            direction="outputs",
            name=name,
            declared=manifest_outputs[name],
            implemented=spec,
        )
        for name, spec in code_outputs.items()
    }
    setattr(module, "_biosimulant_manifest_input_specs", bound_inputs)
    setattr(module, "_biosimulant_manifest_output_specs", bound_outputs)
    return bound_inputs, bound_outputs


def load_yaml(path: str | Path) -> dict[str, Any]:
    import yaml

    value = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError("Manifest must be a mapping")
    return value
