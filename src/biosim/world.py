from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import heapq
import logging
import threading

from .modules import BioModule
from .signals import BioSignal
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
    min_dt: float
    priority: int = 0
    last_time: float = 0.0


@dataclass
class Connection:
    source_module: str
    source_signal: str
    target_module: str
    target_signal: str
    last_event_time: float = -1.0


class BioWorld:
    """Multi-rate orchestration kernel for runnable biomodules."""

    def __init__(self, *, time_unit: str = "seconds") -> None:
        self.time_unit = time_unit
        self._modules: Dict[str, ModuleEntry] = {}
        self._connections_by_target: Dict[str, List[Connection]] = {}
        self._signal_store: Dict[str, Dict[str, BioSignal]] = {}
        self._queue: List[tuple[float, int, str]] = []
        self._seq: int = 0
        self._current_time: float = 0.0
        self._is_setup: bool = False
        self._listeners: List[Listener] = []

        self._stop_requested: bool = False
        self._run_event = threading.Event()
        self._run_event.set()

    # --- Listener management -----------------------------------------
    def on(self, listener: Listener) -> None:
        """Register a listener for runtime events."""
        self._listeners.append(listener)

    def off(self, listener: Listener) -> None:
        """Unregister a listener if present."""
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

    # --- Module registration -----------------------------------------
    def add_biomodule(self, name: str, module: BioModule, *, min_dt: Optional[float] = None, priority: int = 0) -> None:
        if name in self._modules and self._modules[name].module is not module:
            raise ValueError(f"Module name already registered: {name}")
        try:
            setattr(module, "_world_name", name)
        except Exception:
            pass
        module_min_dt = min_dt if min_dt is not None else getattr(module, "min_dt", None)
        if module_min_dt is None or module_min_dt <= 0:
            raise ValueError(f"Module '{name}' must define a positive min_dt")
        self._modules[name] = ModuleEntry(name=name, module=module, min_dt=float(module_min_dt), priority=priority)

    # --- Wiring -------------------------------------------------------
    def connect(self, source: str, target: str) -> None:
        """Connect a signal from one module to another.

        Args:
            source: "module.signal" source reference.
            target: "module.signal" target reference.
        """
        src_parts = source.split(".", 1)
        dst_parts = target.split(".", 1)
        if len(src_parts) != 2 or len(dst_parts) != 2:
            raise ValueError("Source and target must be in format 'module.signal'")
        src_mod, src_sig = src_parts
        dst_mod, dst_sig = dst_parts
        if src_mod not in self._modules:
            raise KeyError(f"Unknown source module '{src_mod}'")
        if dst_mod not in self._modules:
            raise KeyError(f"Unknown target module '{dst_mod}'")

        conn = Connection(
            source_module=src_mod,
            source_signal=src_sig,
            target_module=dst_mod,
            target_signal=dst_sig,
        )
        self._connections_by_target.setdefault(dst_mod, []).append(conn)

    # --- Setup and scheduling ----------------------------------------
    def setup(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Initialize all registered modules and seed the scheduler."""
        config = config or {}
        self._signal_store = {}
        self._queue = []
        self._current_time = 0.0

        # Setup modules (priority order, higher first)
        sorted_entries = sorted(self._modules.values(), key=lambda e: -e.priority)
        for entry in sorted_entries:
            entry.module.setup(config.get(entry.name, {}))
            entry.last_time = 0.0
            outputs = entry.module.get_outputs() or {}
            if outputs:
                self._signal_store[entry.name] = outputs

        # Seed scheduler
        for entry in self._modules.values():
            next_time = entry.module.next_due_time(self._current_time)
            if next_time <= self._current_time:
                raise ValueError(
                    f"Module '{entry.name}' next_due_time({self._current_time}) must be > current time"
                )
            self._schedule(entry.name, next_time)

        self._is_setup = True

    def _schedule(self, name: str, t: float) -> None:
        self._seq += 1
        heapq.heappush(self._queue, (t, -self._modules[name].priority, self._seq, name))

    def _collect_inputs(self, target_name: str, now: float) -> Dict[str, BioSignal]:
        inputs: Dict[str, BioSignal] = {}
        for conn in self._connections_by_target.get(target_name, []):
            source_outputs = self._signal_store.get(conn.source_module, {})
            source_signal = source_outputs.get(conn.source_signal)
            if source_signal is None:
                continue
            if source_signal.metadata.kind == "event":
                if source_signal.time <= conn.last_event_time:
                    continue
                conn.last_event_time = source_signal.time
            inputs[conn.target_signal] = BioSignal(
                source=conn.source_module,
                name=conn.target_signal,
                value=source_signal.value,
                time=now,
                metadata=source_signal.metadata,
            )
        return inputs

    # --- Run loop ------------------------------------------------------
    def run(self, duration: float, *, tick_dt: Optional[float] = None) -> None:
        if not self._is_setup:
            self.setup()
        if duration <= 0:
            return

        # Floating point time accumulation can produce values like 0.30000000000000004
        # which should still be treated as "at" the requested end_time.
        eps = 1e-12

        end_time = self._current_time + duration
        next_tick_time = self._current_time if tick_dt is None else self._current_time + tick_dt

        self._stop_requested = False
        self._run_event.set()
        self._emit(WorldEvent.STARTED, {"t": self._current_time, "end": end_time})

        try:
            while self._queue:
                if self._stop_requested:
                    raise SimulationStop()

                self._run_event.wait()

                if self._stop_requested:
                    raise SimulationStop()

                due_time, _prio, _seq, name = heapq.heappop(self._queue)
                if due_time - end_time > eps:
                    # Not due in this run; requeue and finish
                    heapq.heappush(self._queue, (due_time, _prio, _seq, name))
                    self._current_time = end_time
                    break

                self._current_time = due_time
                entry = self._modules[name]

                inputs = self._collect_inputs(name, self._current_time)
                if inputs:
                    entry.module.set_inputs(inputs)

                entry.module.advance_to(self._current_time)
                entry.last_time = self._current_time

                outputs = entry.module.get_outputs() or {}
                if outputs:
                    self._signal_store[name] = outputs

                next_time = entry.module.next_due_time(self._current_time)
                if next_time <= self._current_time:
                    raise ValueError(
                        f"Module '{name}' next_due_time({self._current_time}) must be > current time"
                    )
                self._schedule(name, next_time)

                if tick_dt is None:
                    self._emit(WorldEvent.TICK, {"t": self._current_time, "module": name})
                else:
                    while next_tick_time <= self._current_time + eps:
                        self._emit(WorldEvent.TICK, {"t": next_tick_time})
                        next_tick_time += tick_dt

        except SimulationStop:
            self._emit(WorldEvent.STOPPED, {"t": self._current_time})
        except Exception as exc:
            self._emit(WorldEvent.ERROR, {"t": self._current_time, "error": exc})
            raise
        finally:
            self._emit(WorldEvent.FINISHED, {"t": self._current_time})

    # --- Cooperative controls -----------------------------------------
    def request_stop(self) -> None:
        self._stop_requested = True
        self._run_event.set()

    def request_pause(self) -> None:
        self._run_event.clear()
        self._emit(WorldEvent.PAUSED, {"t": self._current_time})

    def request_resume(self) -> None:
        self._run_event.set()
        self._emit(WorldEvent.RESUMED, {"t": self._current_time})

    # --- Introspection -------------------------------------------------
    @property
    def current_time(self) -> float:
        return self._current_time

    @property
    def module_names(self) -> List[str]:
        return list(self._modules.keys())

    def get_outputs(self, name: str) -> Dict[str, BioSignal]:
        return self._signal_store.get(name, {})

    def collect_visuals(self) -> List[Dict[str, Any]]:
        """Collect visual specs from all attached modules."""
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
            normed = normalize_visuals(visuals)
            if not normed:
                continue
            out.append(
                {
                    "module": module.__class__.__name__,
                    "visuals": normed,
                }
            )
        return out
