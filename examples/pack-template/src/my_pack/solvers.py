"""Custom Solver implementations.

These solvers can be referenced in YAML configs:
    meta:
      solver:
        class: my_pack.VariableStepSolver
        args:
          max_dt: 0.05
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, TYPE_CHECKING

if TYPE_CHECKING:
    from bsim import BioWorldEvent

from bsim import Solver


class VariableStepSolver(Solver):
    """Solver with configurable time step bounds.

    This solver allows setting minimum and maximum dt values,
    and can be controlled via UI overrides.

    Parameters:
        min_dt: Minimum time step (default: 0.001)
        max_dt: Maximum time step (default: 0.1)
    """

    def __init__(
        self,
        min_dt: float = 0.001,
        max_dt: float = 0.1,
    ) -> None:
        self.min_dt = min_dt
        self.max_dt = max_dt

    def simulate(
        self,
        *,
        steps: int,
        dt: float,
        emit: Callable[["BioWorldEvent", Dict[str, Any]], None],
    ) -> Dict[str, Any]:
        from bsim import BioWorldEvent

        time = 0.0
        # Clamp dt to configured bounds
        actual_dt = max(self.min_dt, min(self.max_dt, dt))

        for i in range(steps):
            time += actual_dt
            emit(BioWorldEvent.STEP, {
                "i": i,
                "t": time,
                "dt": actual_dt,
            })

        return {
            "time": time,
            "steps": steps,
            "actual_dt": actual_dt,
        }

    def with_overrides(self, overrides: Mapping[str, Any]) -> "Solver":
        """Support overriding max_dt from UI."""
        new_min = self.min_dt
        new_max = self.max_dt

        if "min_dt" in overrides:
            try:
                new_min = float(overrides["min_dt"])
            except (ValueError, TypeError):
                pass

        if "max_dt" in overrides:
            try:
                new_max = float(overrides["max_dt"])
            except (ValueError, TypeError):
                pass

        if new_min != self.min_dt or new_max != self.max_dt:
            return VariableStepSolver(min_dt=new_min, max_dt=new_max)

        return self
