"""
Examples for bsim.DefaultBioSolver with built-in and custom processes.

Run after installing the project in editable mode:
    pip install -e .
    python examples/default_bio_solver.py

Alternatively, without installing:
    PYTHONPATH=src python examples/default_bio_solver.py
"""

from __future__ import annotations

from typing import Any, Dict

try:
    import bsim
except ModuleNotFoundError:
    import sys
    sys.stderr.write(
        "Could not import 'bsim'. Did you run 'pip install -e .'?\n"
        "Alternatively, run with 'PYTHONPATH=src'.\n"
    )
    raise


def print_listener(event: bsim.BioWorldEvent, payload: Dict[str, Any]) -> None:
    if event == bsim.BioWorldEvent.STEP:
        # Keep output compact for steps
        print(f"STEP i={payload['i']} t={payload['t']}")
    else:
        print(f"EVENT {event.name}: {payload}")


def example_temperature_only() -> None:
    print("\n-- Temperature only (delta_per_step + rate_per_time) --")
    solver = bsim.DefaultBioSolver(
        temperature=bsim.TemperatureParams(
            initial=300.0,         # Kelvin
            delta_per_step=1.0,    # +1 K each step
            rate_per_time=0.5,     # +0.5 K per second
            bounds=(273.15, 315.15),
        )
    )
    world = bsim.BioWorld(solver=solver)
    world.on(print_listener)
    result = world.simulate(steps=5, dt=0.2)  # total dt = 1.0
    print("Result:", {k: result[k] for k in ("time", "steps", "temperature")})


def example_water_oxygen() -> None:
    print("\n-- Water and Oxygen with bounds --")
    water = bsim.ScalarRateParams(name="water", initial=1.0, rate_per_time=-0.6, bounds=(0.0, 1.0))
    oxygen = bsim.ScalarRateParams(name="oxygen", initial=0.3, rate_per_time=-0.2, bounds=(0.0, 1.0))
    solver = bsim.DefaultBioSolver(water=water, oxygen=oxygen)
    world = bsim.BioWorld(solver=solver)
    world.on(print_listener)
    result = world.simulate(steps=3, dt=1.0)
    print("Result:", {k: result[k] for k in ("time", "steps", "water", "oxygen")})


class GlucoseProcess(bsim.Process):
    """Custom user-defined process to demonstrate extensibility.

    - Produces glucose at a constant amount per step (production_per_step).
    - Consumes glucose at a rate per unit time (consumption_rate).
    - Simple coupling: if oxygen is low (< oxygen_threshold), reduce production.
    """

    def __init__(
        self,
        *,
        initial: float = 1.0,
        production_per_step: float = 0.5,
        consumption_rate: float = 0.1,
        oxygen_threshold: float = 0.2,
        low_oxygen_factor: float = 0.5,
        bounds: tuple[float, float] | None = (0.0, 10.0),
    ) -> None:
        self.initial = float(initial)
        self.production_per_step = float(production_per_step)
        self.consumption_rate = float(consumption_rate)
        self.oxygen_threshold = float(oxygen_threshold)
        self.low_oxygen_factor = float(low_oxygen_factor)
        self.bounds = bounds

    def init_state(self) -> Dict[str, float]:
        return {"glucose": self.initial}

    def update(self, state: Dict[str, Any], dt: float) -> Dict[str, float]:
        g = float(state.get("glucose", self.initial))
        # Oxygen coupling (if configured in the solver state)
        oxy = state.get("oxygen")
        prod = self.production_per_step
        if isinstance(oxy, (int, float)) and oxy < self.oxygen_threshold:
            prod *= self.low_oxygen_factor
        next_g = g + prod - self.consumption_rate * dt
        if self.bounds is not None:
            lo, hi = self.bounds
            if next_g < lo:
                next_g = lo
            elif next_g > hi:
                next_g = hi
        return {"glucose": next_g}


def example_custom_process() -> None:
    print("\n-- Custom Process (Glucose) with Oxygen coupling --")
    # Oxygen decays; glucose production reduced when oxygen is low
    oxygen = bsim.ScalarRateParams(name="oxygen", initial=0.25, rate_per_time=-0.1, bounds=(0.0, 1.0))
    glucose = GlucoseProcess(initial=2.0, production_per_step=0.5, consumption_rate=0.2)
    solver = bsim.DefaultBioSolver(oxygen=oxygen, processes=[glucose])
    world = bsim.BioWorld(solver=solver)
    world.on(print_listener)
    result = world.simulate(steps=4, dt=0.5)
    print(
        "Result:",
        {k: result[k] for k in ("time", "steps", "oxygen", "glucose")},
    )


def main() -> None:
    example_temperature_only()
    example_water_oxygen()
    example_custom_process()


if __name__ == "__main__":
    main()
