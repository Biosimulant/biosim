from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple, TYPE_CHECKING

from .modules import BioModule
from .world import BioWorld

if TYPE_CHECKING:
    from .adapters.base import SimulatorAdapter, AdapterConfig


# Registry of adapter types to their implementation classes
_ADAPTER_REGISTRY: Dict[str, str] = {
    "tellurium": "bsim.adapters.tellurium.TelluriumAdapter",
    "sbml": "bsim.adapters.tellurium.TelluriumAdapter",  # alias
    "ml": "bsim.adapters.ml.MLAdapter",
    "onnx": "bsim.adapters.ml.MLAdapter",  # alias
}


def register_adapter(name: str, cls_path: str) -> None:
    """
    Register a new adapter type.

    Args:
        name: Short name for the adapter (e.g., 'tellurium', 'neuroml')
        cls_path: Dotted path to the adapter class
    """
    _ADAPTER_REGISTRY[name.lower()] = cls_path


def get_adapter_class(adapter_type: str) -> type:
    """
    Get the adapter class for a given type.

    Args:
        adapter_type: Type name (e.g., 'tellurium', 'ml')

    Returns:
        The adapter class

    Raises:
        ValueError: If adapter type is not registered
    """
    cls_path = _ADAPTER_REGISTRY.get(adapter_type.lower())
    if not cls_path:
        available = sorted(_ADAPTER_REGISTRY.keys())
        raise ValueError(
            f"Unknown adapter type '{adapter_type}'. "
            f"Available: {available}"
        )
    return _import_from_string(cls_path)


def _parse_ref(ref: str) -> Tuple[str, Optional[str], str]:
    """Parse references like "eye.visual_stream" or "eye.out.visual_stream".

    Returns (name, direction, port). Direction is optional ("in"/"out" or None).
    """
    parts = ref.split(".")
    if len(parts) < 2:
        raise ValueError(f"Invalid reference '{ref}', expected 'name.topic' form")
    name = parts[0]
    if len(parts) >= 3 and parts[1] in {"in", "out"}:
        direction = parts[1]
        port = parts[2]
    else:
        direction = None
        port = parts[-1]
    return name, direction, port


@dataclass
class WiringBuilder:
    world: BioWorld
    registry: Dict[str, BioModule] = field(default_factory=dict)
    _pending_connections: List[Tuple[str, List[str]]] = field(default_factory=list)

    def add(self, name: str, module: BioModule) -> "WiringBuilder":
        if name in self.registry and self.registry[name] is not module:
            raise ValueError(f"Module name already registered: {name}")
        self.registry[name] = module
        self.world.add_biomodule(module)
        return self

    def connect(self, src_ref: str, dst_refs: Iterable[str]) -> "WiringBuilder":
        self._pending_connections.append((src_ref, list(dst_refs)))
        return self

    def apply(self) -> None:
        for src_ref, dst_refs in self._pending_connections:
            src_name, _src_dir, topic = _parse_ref(src_ref)
            src_mod = self.registry.get(src_name)
            if src_mod is None:
                raise KeyError(f"connect {src_ref}: unknown module name '{src_name}'")
            # Validate source port if declared
            declared_out = set(src_mod.outputs())
            if declared_out and topic not in declared_out:
                raise ValueError(
                    f"connect {src_ref}: module '{src_name}' has no output port '{topic}'. "
                    f"Declared outputs: {sorted(declared_out)}"
                )
            for dst_ref in dst_refs:
                dst_name, _dst_dir, dst_port = _parse_ref(dst_ref)
                dst_mod = self.registry.get(dst_name)
                if dst_mod is None:
                    raise KeyError(f"connect {src_ref} -> {dst_ref}: unknown module '{dst_name}'")
                declared_in = set(dst_mod.inputs())
                if declared_in and dst_port not in declared_in:
                    raise ValueError(
                        f"connect {src_ref} -> {dst_ref}: module '{dst_name}' has no input port '{dst_port}'. "
                        f"Declared inputs: {sorted(declared_in)}"
                    )
                self.world.connect_biomodules(src_mod, topic, dst_mod)
        self._pending_connections.clear()


def _import_from_string(path: str) -> Any:
    mod_name, _, attr = path.rpartition(".")
    if not mod_name or not attr:
        raise ValueError(f"Invalid import path: {path}")
    mod = import_module(mod_name)
    return getattr(mod, attr)


class AdapterModule(BioModule):
    """
    Wrapper that makes a SimulatorAdapter behave like a BioModule.

    This allows adapters to be used in the standard wiring system,
    receiving signals from other modules and emitting signals that
    can be consumed by other modules.

    Example config:
        modules:
          metabolism:
            adapter: tellurium
            model: path/to/model.xml
            expose: [glucose, ATP]
            parameters:
              k1: 0.5
    """

    def __init__(
        self,
        name: str,
        adapter: "SimulatorAdapter",
        expose: List[str] | None = None,
        input_map: Dict[str, str] | None = None,
    ):
        """
        Create an adapter wrapper.

        Args:
            name: Module name for signal emission
            adapter: The underlying simulator adapter
            expose: List of outputs to expose as signals
            input_map: Mapping of signal names to adapter input names
        """
        super().__init__()
        self._name = name
        self._adapter = adapter
        self._expose = expose or []
        self._input_map = input_map or {}
        self._pending_inputs: Dict[str, Any] = {}

    def inputs(self) -> List[str]:
        """Return declared input ports."""
        return list(self._input_map.keys()) if self._input_map else []

    def outputs(self) -> List[str]:
        """Return declared output ports."""
        return self._expose

    def on_signal(self, topic: str, payload: Any) -> None:
        """Receive a signal and queue it for the adapter."""
        # Map external signal name to internal adapter input name
        internal_name = self._input_map.get(topic, topic)
        self._pending_inputs[internal_name] = payload

    def step(self, dt: float) -> None:
        """
        Advance the adapter by dt and emit output signals.

        This is called by the world during simulation.
        """
        from .adapters.signals import BioSignal

        # Apply pending inputs to adapter
        if self._pending_inputs:
            signals = {
                name: BioSignal(
                    source=self._name,
                    name=name,
                    value=value,
                    timestamp=self._adapter.current_time,
                )
                for name, value in self._pending_inputs.items()
            }
            self._adapter.set_inputs(signals)
            self._pending_inputs.clear()

        # Advance simulation
        new_time = self._adapter.current_time + dt
        self._adapter.advance_to(new_time)

        # Emit outputs as signals
        outputs = self._adapter.get_outputs()
        for signal_name in self._expose:
            if signal_name in outputs:
                signal = outputs[signal_name]
                self.emit(signal_name, signal.value)

    def reset(self) -> None:
        """Reset the adapter to initial state."""
        self._adapter.reset()
        self._pending_inputs.clear()


def _create_adapter_module(name: str, entry: Mapping[str, Any]) -> AdapterModule:
    """
    Create an AdapterModule from a config entry.

    Args:
        name: Module name
        entry: Config dict with adapter, model, expose, parameters, etc.

    Returns:
        Configured AdapterModule
    """
    adapter_type = entry.get("adapter")
    if not isinstance(adapter_type, str):
        raise ValueError(f"Module '{name}' has invalid adapter type")

    # Get adapter class
    adapter_cls = get_adapter_class(adapter_type)

    # Build adapter config
    from .adapters.base import AdapterConfig

    config = AdapterConfig(
        adapter_type=adapter_type,
        model_path=entry.get("model") or entry.get("sbml") or entry.get("onnx"),
        expose=entry.get("expose", []),
        parameters=entry.get("parameters", {}),
        inputs=entry.get("inputs", {}),
        outputs=entry.get("outputs", {}),
        extra=entry.get("extra", {}),
    )

    # Instantiate and setup adapter
    adapter = adapter_cls(config)
    adapter.setup({})

    # Create wrapper module
    return AdapterModule(
        name=name,
        adapter=adapter,
        expose=config.expose,
        input_map=config.inputs,
    )


def build_from_spec(world: BioWorld, spec: Mapping[str, Any]) -> WiringBuilder:
    """Build modules and wiring from a spec dict.

    Spec format (keys optional):
    - modules: mapping of name -> one of:
        - dotted path string (e.g., "bsim.packs.neuro.IzhikevichPopulation")
        - {class: dotted, args: {...}} for native BioModule classes
        - {adapter: "tellurium", model: "path/to/model.xml", expose: [...]} for adapters
    - wiring: list of {from: str, to: [str, ...]}

    Example with adapter:
        modules:
          metabolism:
            adapter: tellurium
            model: models/glycolysis.xml
            expose: [glucose, ATP, pyruvate]
            parameters:
              vmax: 1.5

          predictor:
            adapter: ml
            model: models/classifier.onnx
            expose: [prediction]
            inputs:
              substrate_level: glucose
    """
    builder = WiringBuilder(world)

    modules_section = spec.get("modules") if isinstance(spec, Mapping) else None
    if isinstance(modules_section, Mapping):
        for name, entry in modules_section.items():
            if isinstance(entry, str):
                # Simple class path string
                cls = _import_from_string(entry)
                module = cls()
            elif isinstance(entry, Mapping):
                # Check if it's an adapter or native module
                if "adapter" in entry:
                    # Create adapter-wrapped module
                    module = _create_adapter_module(name, entry)
                elif "class" in entry:
                    # Native BioModule class
                    cls_path = entry.get("class")
                    if not isinstance(cls_path, str):
                        raise ValueError(f"Invalid class for module '{name}'")
                    cls = _import_from_string(cls_path)
                    kwargs = entry.get("args") or {}
                    if not isinstance(kwargs, Mapping):
                        raise ValueError(f"Invalid args for module '{name}'")
                    module = cls(**dict(kwargs))
                else:
                    raise ValueError(
                        f"Module '{name}' must have either 'class' or 'adapter' key"
                    )
            else:
                raise ValueError(f"Invalid module entry for '{name}'")
            if not isinstance(module, BioModule):
                raise TypeError(f"Module '{name}' is not a BioModule: {type(module)!r}")
            builder.add(name, module)

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
