from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple


class Solver(ABC):
    """Abstract base class for solvers used by `BioWorld`.

    Implementations must override `simulate` with the exact keyword-only
    signature below. The `emit` callback should be used to publish events
    (e.g., STEP updates) during the simulation.
    """

    @abstractmethod
    def simulate(
        self,
        *,
        steps: int,
        dt: float,
        emit: Callable[["BioWorldEvent", Dict[str, Any]], None],
    ) -> Any:
        raise NotImplementedError

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Solver":
        """Return a solver configured with the provided run overrides.

        Default behavior is a no-op (returns self). Implementations may return
        a new solver instance (preferred) or self.
        """
        return self


class FixedStepSolver(Solver):
    """A simple ready-made solver that increments time in fixed steps.

    Emits a STEP event each iteration and returns a final state dict.
    """

    def simulate(
        self,
        *,
        steps: int,
        dt: float,
        emit: Callable[["BioWorldEvent", Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        # Local import to avoid a circular import at module load time.
        from .world import BioWorldEvent

        time = 0.0
        for i in range(steps):
            time += dt
            emit(BioWorldEvent.STEP, {"i": i, "t": time})
        return {"time": time, "steps": steps}


# --- Extensible Processes and FixedStepBioSolver ---


class Process(ABC):
    """A state update strategy applied by FixedStepBioSolver each step.

    Implementations read from the current state and propose updates for one
    or more named quantities by returning a patch mapping quantity -> new value.
    They may also expose initial state for their outputs.
    """

    # Return the initial state for quantities managed by this process.
    def init_state(self) -> Dict[str, float]:
        return {}

    # Compute a mapping of quantity -> new value for this step.
    @abstractmethod
    def update(self, state: Dict[str, Any], dt: float) -> Dict[str, float]:
        raise NotImplementedError


@dataclass
class TemperatureParams:
    initial: float = 0.0
    # Additive change per simulation step (unit-value per step)
    delta_per_step: float = 0.0
    # Rate-based change per unit time (unit-value per second)
    rate_per_time: float = 0.0
    # Optional bounds (min, max) for clamping
    bounds: Optional[Tuple[float, float]] = None


class TemperatureProcess(Process):
    def __init__(self, params: TemperatureParams) -> None:
        self.params = params

    def init_state(self) -> Dict[str, float]:
        return {"temperature": float(self.params.initial)}

    def update(self, state: Dict[str, Any], dt: float) -> Dict[str, float]:
        current = float(state.get("temperature", self.params.initial))
        next_val = current + self.params.delta_per_step + self.params.rate_per_time * dt
        if self.params.bounds is not None:
            lo, hi = self.params.bounds
            # clamp
            if next_val < lo:
                next_val = lo
            elif next_val > hi:
                next_val = hi
        return {"temperature": next_val}


@dataclass
class ScalarRateParams:
    name: str
    initial: float
    # Rate per unit time (value change per second)
    rate_per_time: float = 0.0
    # Bounds for clamping
    bounds: Optional[Tuple[float, float]] = None


class ScalarRateProcess(Process):
    """Generic first-order rate process: value += rate_per_time * dt (then clamp)."""

    def __init__(self, params: ScalarRateParams) -> None:
        self.params = params

    def init_state(self) -> Dict[str, float]:
        return {self.params.name: float(self.params.initial)}

    def update(self, state: Dict[str, Any], dt: float) -> Dict[str, float]:
        current = float(state.get(self.params.name, self.params.initial))
        next_val = current + self.params.rate_per_time * dt
        if self.params.bounds is not None:
            lo, hi = self.params.bounds
            if next_val < lo:
                next_val = lo
            elif next_val > hi:
                next_val = hi
        return {self.params.name: next_val}


class FixedStepBioSolver(Solver):
    """Extensible solver with configurable bio-quantities and processes.

    Features:
    - Retains FixedStepSolver behavior (emits STEP events, returns time/steps).
    - Adds optional built-in processes for temperature, water, oxygen.
    - Accepts custom processes implementing the `Process` interface.

    Parameters (all optional):
    - temperature: TemperatureParams
    - water: ScalarRateParams (name must be "water")
    - oxygen: ScalarRateParams (name must be "oxygen")
    - processes: additional custom processes
    """

    def __init__(
        self,
        *,
        temperature: Optional[TemperatureParams] = None,
        water: Optional[ScalarRateParams] = None,
        oxygen: Optional[ScalarRateParams] = None,
        processes: Optional[List[Process]] = None,
    ) -> None:
        self._temperature_params = temperature
        self._water_params = water
        self._oxygen_params = oxygen
        self._extra_processes = list(processes) if processes else []

        # Assemble process list in a stable order.
        procs: List[Process] = []
        if temperature is not None:
            procs.append(TemperatureProcess(temperature))
        if water is not None:
            procs.append(ScalarRateProcess(water))
        if oxygen is not None:
            procs.append(ScalarRateProcess(oxygen))
        if self._extra_processes:
            procs.extend(self._extra_processes)
        self._processes = procs

        # Initialize state from processes.
        state: Dict[str, float] = {}
        for p in self._processes:
            state.update(p.init_state())
        self._initial_state = state

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Solver":
        # Currently supports temperature override for UI integration.
        if not overrides:
            return self
        if "temperature" not in overrides:
            return self
        if self._temperature_params is None:
            return self
        try:
            temp_val = float(overrides["temperature"])
        except Exception:
            return self
        new_temp = replace(self._temperature_params, initial=temp_val)
        return FixedStepBioSolver(
            temperature=new_temp,
            water=self._water_params,
            oxygen=self._oxygen_params,
            processes=list(self._extra_processes) if self._extra_processes else None,
        )

    def simulate(
        self,
        *,
        steps: int,
        dt: float,
        emit: Callable[["BioWorldEvent", Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        from .world import BioWorldEvent

        time = 0.0
        # Make a working copy of the initial state for this run
        state: Dict[str, Any] = dict(self._initial_state)

        for i in range(steps):
            time += dt
            # Apply each process in order; later processes see earlier updates
            for p in self._processes:
                patch = p.update(state, dt)
                if patch:
                    state.update(patch)
            emit(BioWorldEvent.STEP, {"i": i, "t": time})

        # Return final state alongside standard fields
        result: Dict[str, Any] = {"time": time, "steps": steps}
        result.update(state)
        return result
