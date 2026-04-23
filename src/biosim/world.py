from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
import logging
import threading
from typing import Any, Callable, Dict, List, Mapping, Optional

from .modules import BioModule
from .signals import BioSignal, SignalSpec, validate_connection_specs, validate_port_spec_direction
from .visuals import normalize_visuals

logger = logging.getLogger(__name__)


class WorldEvent(Enum):
    """Runtime events emitted by the BioWorld orchestrator."""

    STARTED = "started"
    TICK = "tick"
    FINISHED = "finished"
    ERROR = "error"
    PAUSED = "paused"
    RESUMED = "resumed"
    STOPPED = "stopped"


Listener = Callable[[WorldEvent, Dict[str, Any]], None]


class SimulationStop(Exception):
    """Internal cooperative stop signal for the run loop."""


@dataclass
class ModuleEntry:
    name: str
    module: BioModule
    input_specs: dict[str, SignalSpec]
    output_specs: dict[str, SignalSpec]


@dataclass
class Connection:
    source_module: str
    source_signal: str
    target_module: str
    target_signal: str
    last_event_time: Optional[float] = None
    last_stale_warning_time: Optional[float] = None


class BioWorld:
    """Communication-step orchestration kernel for runnable biomodules."""

    def __init__(self, *, communication_step: float, time_unit: str = "seconds") -> None:
        if communication_step <= 0:
            raise ValueError("communication_step must be positive")
        self.communication_step = float(communication_step)
        self.time_unit = time_unit
        self._modules: Dict[str, ModuleEntry] = {}
        self._connections_by_target: Dict[str, List[Connection]] = {}
        self._signal_store: Dict[str, Dict[str, BioSignal]] = {}
        self._signal_history: Dict[str, Dict[str, List[BioSignal]]] = {}
        self._current_time: float = 0.0
        self._is_setup: bool = False
        self._listeners: List[Listener] = []
        self._active_run_start: Optional[float] = None
        self._active_run_end: Optional[float] = None
        self._setup_config: Dict[str, Dict[str, Any]] = {}

        self._stop_requested: bool = False
        self._run_event = threading.Event()
        self._run_event.set()

    # --- Listener management -----------------------------------------
    def on(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def off(self, listener: Listener) -> None:
        try:
            self._listeners.remove(listener)
        except ValueError:
            pass

    def _emit(self, event: WorldEvent, payload: Optional[Dict[str, Any]] = None) -> None:
        data = payload or {}
        for listener in list(self._listeners):
            try:
                listener(event, data)
            except Exception:
                logger.exception("world listener raised during %s", event)

    def _progress_payload(self, now: Optional[float] = None) -> Dict[str, float]:
        start = self._active_run_start
        end = self._active_run_end
        if start is None or end is None:
            return {}
        sim_time = self._current_time if now is None else now
        duration = max(0.0, end - start)
        if duration <= 0.0:
            progress = 1.0 if sim_time >= end else 0.0
        else:
            progress = (sim_time - start) / duration
        progress = max(0.0, min(1.0, progress))
        return {
            "start": start,
            "end": end,
            "duration": duration,
            "progress": progress,
            "progress_pct": progress * 100.0,
            "remaining": max(0.0, end - sim_time),
        }

    # --- Module registration -----------------------------------------
    def add_biomodule(
        self,
        name: str,
        module: BioModule,
    ) -> None:
        if name in self._modules and self._modules[name].module is not module:
            raise ValueError(f"Module name already registered: {name}")

        input_specs = self._normalize_port_specs(module.inputs(), direction="input", module_name=name)
        output_specs = self._normalize_port_specs(module.outputs(), direction="output", module_name=name)

        try:
            setattr(module, "_world_name", name)
        except Exception:  # pragma: no cover - defensive: setattr may fail on frozen modules
            pass

        self._modules[name] = ModuleEntry(
            name=name,
            module=module,
            input_specs=input_specs,
            output_specs=output_specs,
        )

    def _normalize_port_specs(
        self,
        specs: Mapping[str, SignalSpec] | None,
        *,
        direction: str,
        module_name: str,
    ) -> dict[str, SignalSpec]:
        if specs is None:
            return {}
        if not isinstance(specs, Mapping):
            raise TypeError(f"Module '{module_name}' {direction}s() must return a mapping of port -> SignalSpec")
        normalized: dict[str, SignalSpec] = {}
        for port, spec in specs.items():
            if not isinstance(port, str) or not port:
                raise TypeError(f"Module '{module_name}' {direction} port names must be non-empty strings")
            if isinstance(spec, Mapping):
                spec = SignalSpec.from_dict(spec)
            if not isinstance(spec, SignalSpec):
                raise TypeError(
                    f"Module '{module_name}' {direction} port '{port}' must declare a SignalSpec, got {type(spec)!r}"
                )
            validate_port_spec_direction(spec, direction=direction)
            normalized[port] = spec
        return normalized

    # --- Wiring -------------------------------------------------------
    def connect(self, source: str, target: str) -> None:
        src_parts = source.rsplit(".", 1)
        dst_parts = target.rsplit(".", 1)
        if len(src_parts) != 2 or len(dst_parts) != 2:
            raise ValueError("Source and target must be in format 'module.signal'")
        src_mod, src_sig = src_parts
        dst_mod, dst_sig = dst_parts
        if src_mod not in self._modules:
            raise KeyError(f"Unknown source module '{src_mod}'")
        if dst_mod not in self._modules:
            raise KeyError(f"Unknown target module '{dst_mod}'")

        src_entry = self._modules[src_mod]
        dst_entry = self._modules[dst_mod]
        if src_sig not in src_entry.output_specs:
            raise KeyError(f"Unknown source signal '{src_mod}.{src_sig}'")
        if dst_sig not in dst_entry.input_specs:
            raise KeyError(f"Unknown target signal '{dst_mod}.{dst_sig}'")
        validate_connection_specs(src_entry.output_specs[src_sig], dst_entry.input_specs[dst_sig])

        conn = Connection(
            source_module=src_mod,
            source_signal=src_sig,
            target_module=dst_mod,
            target_signal=dst_sig,
        )
        self._connections_by_target.setdefault(dst_mod, []).append(conn)

    # --- Setup --------------------------------------------------------
    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        config = config or {}
        self._setup_config = {name: dict(module_cfg or {}) for name, module_cfg in config.items()}
        self._signal_store = {}
        self._signal_history = {}
        self._current_time = 0.0
        for connections in self._connections_by_target.values():
            for conn in connections:
                conn.last_event_time = None
                conn.last_stale_warning_time = None

        for entry in self._modules.values():
            entry.module.setup(self._setup_config.get(entry.name, {}))
            outputs = self._normalize_outputs(entry.name, entry.module.get_outputs() or {})
            self._commit_outputs(entry.name, outputs)

        self._is_setup = True

    def _normalize_outputs(self, module_name: str, outputs: Mapping[str, BioSignal]) -> Dict[str, BioSignal]:
        if not isinstance(outputs, Mapping):
            raise TypeError(f"Module '{module_name}' get_outputs() must return a mapping")
        declared = self._modules[module_name].output_specs
        normalized: Dict[str, BioSignal] = {}
        for port, signal in outputs.items():
            if port not in declared:
                raise KeyError(f"Module '{module_name}' produced undeclared output port '{port}'")
            if not isinstance(signal, BioSignal):
                raise TypeError(
                    f"Module '{module_name}' output '{port}' must be a typed BioSignal, got {type(signal)!r}"
                )
            bound = signal.with_spec(declared[port]) if signal.spec is None else signal.with_spec(declared[port])
            if bound.source != module_name:
                bound = bound.__class__(
                    source=module_name,
                    name=bound.name,
                    value=copy.deepcopy(bound.value),
                    emitted_at=bound.emitted_at,
                    spec=bound.spec,
                )
            if bound.name != port:
                bound = bound.retarget(name=port)
            normalized[port] = bound
        return normalized

    def _commit_outputs(self, module_name: str, outputs: Mapping[str, BioSignal]) -> None:
        if not outputs:
            return
        self._signal_store[module_name] = dict(outputs)
        history = self._signal_history.setdefault(module_name, {})
        for port, signal in outputs.items():
            samples = history.setdefault(port, [])
            samples.append(signal)
            if len(samples) > 2:
                del samples[:-2]

    def _warn_if_input_stale(self, conn: Connection, source_signal: BioSignal, target_spec: SignalSpec, now: float) -> None:
        if source_signal.kind == "event":
            return
        if target_spec.max_age is None:
            return
        age = now - source_signal.emitted_at
        if age - target_spec.max_age <= 1e-12:
            return
        if conn.last_stale_warning_time is not None and source_signal.emitted_at <= conn.last_stale_warning_time:
            return

        if target_spec.stale_policy == "ignore":
            return
        if target_spec.stale_policy == "error":
            raise ValueError(
                f"stale signal read: target '{conn.target_module}' consumed '{conn.source_module}.{conn.source_signal}' "
                f"at t={now:.6f} using source time {source_signal.emitted_at:.6f} "
                f"(age={age:.6f} > max_age={target_spec.max_age:.6f})"
            )

        conn.last_stale_warning_time = source_signal.emitted_at
        logger.warning(
            "stale signal read: target '%s' consumed '%s.%s' at t=%.6f using source time %.6f "
            "(age=%.6f > max_age=%.6f)",
            conn.target_module,
            conn.source_module,
            conn.source_signal,
            now,
            source_signal.emitted_at,
            age,
            target_spec.max_age,
        )

    def _collect_inputs(self, target_name: str, start: float, end: float) -> Dict[str, BioSignal]:
        inputs: Dict[str, BioSignal] = {}
        entry = self._modules[target_name]
        for conn in self._connections_by_target.get(target_name, []):
            source_outputs = self._signal_store.get(conn.source_module, {})
            source_signal = source_outputs.get(conn.source_signal)
            if source_signal is None:
                continue
            target_spec = entry.input_specs[conn.target_signal]
            self._warn_if_input_stale(conn, source_signal, target_spec, start)
            if source_signal.kind == "event":
                if conn.last_event_time is not None and source_signal.emitted_at <= conn.last_event_time:
                    continue
                conn.last_event_time = source_signal.emitted_at
            inputs[conn.target_signal] = source_signal.retarget(name=conn.target_signal)
        return inputs

    # --- Run loop -----------------------------------------------------
    def run(self, duration: float, *, tick_dt: Optional[float] = None) -> None:
        if not self._is_setup:
            self.setup()
        if duration <= 0:
            return

        eps = 1e-12
        end_time = self._current_time + duration
        next_tick_time = self._current_time if tick_dt is None else self._current_time + tick_dt
        self._active_run_start = self._current_time
        self._active_run_end = end_time

        self._stop_requested = False
        self._run_event.set()
        self._emit(WorldEvent.STARTED, {"t": self._current_time, **self._progress_payload(self._current_time)})

        try:
            while self._current_time < end_time - eps:
                if self._stop_requested:
                    raise SimulationStop()

                self._run_event.wait()

                if self._stop_requested:
                    raise SimulationStop()

                window_start = self._current_time
                window_end = min(window_start + self.communication_step, end_time)
                window_inputs = {
                    name: self._collect_inputs(name, window_start, window_end)
                    for name in self._modules.keys()
                }

                for name, entry in self._modules.items():
                    inputs = window_inputs.get(name) or {}
                    if inputs:
                        entry.module.set_inputs(inputs)

                for entry in self._modules.values():
                    entry.module.advance_window(window_start, window_end)

                pending_outputs: Dict[str, Dict[str, BioSignal]] = {}
                for name, entry in self._modules.items():
                    pending_outputs[name] = self._normalize_outputs(name, entry.module.get_outputs() or {})

                for name, outputs in pending_outputs.items():
                    self._commit_outputs(name, outputs)

                self._current_time = window_end

                if tick_dt is None:
                    self._emit(
                        WorldEvent.TICK,
                        {
                            "t": self._current_time,
                            "window_start": window_start,
                            "window_end": window_end,
                            **self._progress_payload(self._current_time),
                        },
                    )
                else:
                    while next_tick_time <= self._current_time + eps:
                        self._emit(WorldEvent.TICK, {"t": next_tick_time, **self._progress_payload(next_tick_time)})
                        next_tick_time += tick_dt

        except SimulationStop:
            self._emit(WorldEvent.STOPPED, {"t": self._current_time, **self._progress_payload(self._current_time)})
        except Exception as exc:
            self._emit(
                WorldEvent.ERROR,
                {"t": self._current_time, "error": exc, **self._progress_payload(self._current_time)},
            )
            raise
        finally:
            self._emit(WorldEvent.FINISHED, {"t": self._current_time, **self._progress_payload(self._current_time)})
            self._active_run_start = None
            self._active_run_end = None

    # --- Cooperative controls ----------------------------------------
    def request_stop(self) -> None:
        self._stop_requested = True
        self._run_event.set()

    def request_pause(self) -> None:
        self._run_event.clear()
        self._emit(WorldEvent.PAUSED, {"t": self._current_time, **self._progress_payload(self._current_time)})

    def request_resume(self) -> None:
        self._run_event.set()
        self._emit(WorldEvent.RESUMED, {"t": self._current_time, **self._progress_payload(self._current_time)})

    # --- Snapshot / restore ------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "time_unit": self.time_unit,
            "communication_step": self.communication_step,
            "current_time": self._current_time,
            "is_setup": self._is_setup,
            "setup_config": copy.deepcopy(self._setup_config),
            "signal_store": {
                module_name: {port: signal.to_dict() for port, signal in outputs.items()}
                for module_name, outputs in self._signal_store.items()
            },
            "signal_history": {
                module_name: {
                    port: [signal.to_dict() for signal in history]
                    for port, history in port_map.items()
                }
                for module_name, port_map in self._signal_history.items()
            },
            "connections": {
                target: [
                    {
                        "source_module": conn.source_module,
                        "source_signal": conn.source_signal,
                        "target_module": conn.target_module,
                        "target_signal": conn.target_signal,
                        "last_event_time": conn.last_event_time,
                        "last_stale_warning_time": conn.last_stale_warning_time,
                    }
                    for conn in conns
                ]
                for target, conns in self._connections_by_target.items()
            },
            "modules": {
                name: copy.deepcopy(entry.module.snapshot())
                for name, entry in self._modules.items()
            },
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        if not self._is_setup:
            setup_config = snapshot.get("setup_config")
            self.setup(copy.deepcopy(setup_config) if isinstance(setup_config, Mapping) else None)

        module_states = snapshot.get("modules")
        if not isinstance(module_states, Mapping):
            raise ValueError("snapshot is missing module state")
        for name, entry in self._modules.items():
            if name not in module_states:
                raise KeyError(f"snapshot missing module state for '{name}'")
            entry.module.restore(copy.deepcopy(module_states[name]))

        self._current_time = float(snapshot.get("current_time", 0.0))
        self._is_setup = bool(snapshot.get("is_setup", True))
        self._setup_config = copy.deepcopy(snapshot.get("setup_config", {}))

        signal_store: Dict[str, Dict[str, BioSignal]] = {}
        for module_name, outputs in snapshot.get("signal_store", {}).items():
            signal_store[module_name] = {
                port: BioSignal.from_dict(signal_dict)
                for port, signal_dict in outputs.items()
            }
        self._signal_store = signal_store

        signal_history: Dict[str, Dict[str, List[BioSignal]]] = {}
        for module_name, port_map in snapshot.get("signal_history", {}).items():
            signal_history[module_name] = {
                port: [BioSignal.from_dict(signal_dict) for signal_dict in samples]
                for port, samples in port_map.items()
            }
        self._signal_history = signal_history

        snapshot_connections = snapshot.get("connections", {})
        if not isinstance(snapshot_connections, Mapping):
            raise ValueError("snapshot connections must be a mapping")
        for target, conns in self._connections_by_target.items():
            raw_conns = snapshot_connections.get(target, [])
            if len(raw_conns) != len(conns):
                raise ValueError(f"snapshot connection count mismatch for target '{target}'")
            for conn, raw in zip(conns, raw_conns):
                conn.last_event_time = raw.get("last_event_time")
                conn.last_stale_warning_time = raw.get("last_stale_warning_time")

    def branch(self) -> "BioWorld":
        snapshot = self.snapshot()
        branched = BioWorld(communication_step=self.communication_step, time_unit=self.time_unit)
        for name, entry in self._modules.items():
            try:
                module_copy = copy.deepcopy(entry.module)
            except Exception as exc:  # pragma: no cover - depends on module implementation
                raise TypeError(
                    f"Module '{name}' could not be deep-copied for branching; implement deepcopy-safe state"
                ) from exc
            branched.add_biomodule(name, module_copy)
        for target, connections in self._connections_by_target.items():
            for conn in connections:
                branched.connect(f"{conn.source_module}.{conn.source_signal}", f"{target}.{conn.target_signal}")
        branched.restore(copy.deepcopy(snapshot))
        return branched

    # --- Introspection ------------------------------------------------
    @property
    def current_time(self) -> float:
        return self._current_time

    @property
    def module_names(self) -> List[str]:
        return list(self._modules.keys())

    def get_outputs(self, name: str) -> Dict[str, BioSignal]:
        return self._signal_store.get(name, {})

    def collect_visuals(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for entry in self._modules.values():
            module = entry.module
            try:
                visuals = module.visualize()  # type: ignore[attr-defined]
            except Exception:
                logger.exception("BioModule.visualize raised for %s", module.__class__.__name__)
                continue
            if not visuals:
                continue
            normalized = normalize_visuals(visuals)
            if normalized:
                out.append({"module": entry.name, "visuals": normalized})
        return out
