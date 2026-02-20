from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from .modules import BioModule
from .world import BioWorld


def _parse_ref(ref: str) -> Tuple[str, str]:
    """Parse references like "eye.visual_stream".

    Returns (name, port).
    """
    parts = ref.split(".", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid reference '{ref}', expected 'name.port' form")
    return parts[0], parts[1]


@dataclass
class WiringBuilder:
    world: BioWorld
    registry: Dict[str, BioModule] = field(default_factory=dict)
    _pending_connections: List[Tuple[str, List[str]]] = field(default_factory=list)

    def add(self, name: str, module: BioModule, *, min_dt: Optional[float] = None, priority: int = 0) -> "WiringBuilder":
        if name in self.registry and self.registry[name] is not module:
            raise ValueError(f"Module name already registered: {name}")
        self.registry[name] = module
        self.world.add_biomodule(name, module, min_dt=min_dt, priority=priority)
        return self

    def connect(self, src_ref: str, dst_refs: Iterable[str]) -> "WiringBuilder":
        self._pending_connections.append((src_ref, list(dst_refs)))
        return self

    def apply(self) -> None:
        for src_ref, dst_refs in self._pending_connections:
            src_name, src_port = _parse_ref(src_ref)
            src_mod = self.registry.get(src_name)
            if src_mod is None:
                raise KeyError(f"connect {src_ref}: unknown module name '{src_name}'")
            # Validate source port if declared
            declared_out = set(src_mod.outputs())
            if declared_out and src_port not in declared_out:
                raise ValueError(
                    f"connect {src_ref}: module '{src_name}' has no output port '{src_port}'. "
                    f"Declared outputs: {sorted(declared_out)}"
                )
            for dst_ref in dst_refs:
                dst_name, dst_port = _parse_ref(dst_ref)
                dst_mod = self.registry.get(dst_name)
                if dst_mod is None:
                    raise KeyError(f"connect {src_ref} -> {dst_ref}: unknown module '{dst_name}'")
                declared_in = set(dst_mod.inputs())
                if declared_in and dst_port not in declared_in:
                    raise ValueError(
                        f"connect {src_ref} -> {dst_ref}: module '{dst_name}' has no input port '{dst_port}'. "
                        f"Declared inputs: {sorted(declared_in)}"
                    )
                self.world.connect(f"{src_name}.{src_port}", f"{dst_name}.{dst_port}")
        self._pending_connections.clear()


def _import_from_string(path: str) -> Any:
    mod_name, _, attr = path.rpartition(".")
    if not mod_name or not attr:
        raise ValueError(f"Invalid import path: {path}")
    mod = import_module(mod_name)
    return getattr(mod, attr)


def build_from_spec(world: BioWorld, spec: Mapping[str, Any]) -> WiringBuilder:
    """Build modules and wiring from a spec dict.

    Spec format (keys optional):
    - modules: mapping of name -> one of:
        - dotted path string (e.g., "biosim.packs.neuro.IzhikevichPopulation")
        - {class: dotted, args: {...}, min_dt: float, priority: int}
    - wiring: list of {from: str, to: [str, ...]}
    """
    builder = WiringBuilder(world)

    modules_section = spec.get("modules") if isinstance(spec, Mapping) else None
    if isinstance(modules_section, Mapping):
        for name, entry in modules_section.items():
            min_dt = None
            priority = 0
            if isinstance(entry, str):
                cls = _import_from_string(entry)
                module = cls()
            elif isinstance(entry, Mapping):
                cls_path = entry.get("class")
                if not isinstance(cls_path, str):
                    raise ValueError(f"Invalid class for module '{name}'")
                cls = _import_from_string(cls_path)
                kwargs = entry.get("args") or {}
                if not isinstance(kwargs, Mapping):
                    raise ValueError(f"Invalid args for module '{name}'")
                module = cls(**dict(kwargs))
                if "min_dt" in entry:
                    min_dt = float(entry["min_dt"])
                if "priority" in entry:
                    priority = int(entry["priority"])
            else:
                raise ValueError(f"Invalid module entry for '{name}'")
            if not isinstance(module, BioModule):
                raise TypeError(f"Module '{name}' is not a BioModule: {type(module)!r}")
            builder.add(name, module, min_dt=min_dt, priority=priority)

    wiring_section = spec.get("wiring") if isinstance(spec, Mapping) else None
    if isinstance(wiring_section, list):
        for entry in wiring_section:
            if not isinstance(entry, Mapping):
                raise ValueError("Invalid wiring entry")
            src = entry.get("from")
            to = entry.get("to")
            if not isinstance(src, str) or not isinstance(to, list):
                raise ValueError("Wiring entries require 'from' (str) and 'to' (list[str])")
            builder.connect(src, to)

    builder.apply()
    return builder


def load_wiring(world: BioWorld, path: str | Path) -> WiringBuilder:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix in {".toml", ".tml"}:
        return load_wiring_toml(world, p)
    if suffix in {".yaml", ".yml"}:
        return load_wiring_yaml(world, p)
    raise ValueError(f"Unsupported wiring file type: {suffix}")


def load_wiring_toml(world: BioWorld, path: str | Path) -> WiringBuilder:
    p = Path(path)
    data: Dict[str, Any]
    try:
        import tomllib  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - fallback for <3.11
        try:
            import tomli as tomllib  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise ImportError("TOML support requires Python 3.11+ or 'tomli' installed") from exc
    with p.open("rb") as f:
        data = tomllib.load(f)
    return build_from_spec(world, data)


def load_wiring_yaml(world: BioWorld, path: str | Path) -> WiringBuilder:
    p = Path(path)
    try:
        import yaml  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise ImportError("YAML support requires 'pyyaml' installed") from exc
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, Mapping):
        raise ValueError("YAML wiring must load to a mapping/dict")
    return build_from_spec(world, data)
