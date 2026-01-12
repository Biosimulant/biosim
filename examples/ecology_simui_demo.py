#!/usr/bin/env python3
"""
SimUI demo for the ecology pack: launch an interactive dashboard.

Demonstrates:
- Running the SimUI server with ecology modules
- Interactive visualization of population dynamics
- Predator-prey phase space plots
- Config-driven simulation via SimUI controls

Run:
    pip install -e .
    python examples/ecology_simui_demo.py

Then open http://localhost:8765 in your browser.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running without installation
try:
    import bsim
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    import bsim

from bsim.packs.ecology import (
    Environment,
    OrganismPopulation,
    PredatorPreyInteraction,
    PopulationMonitor,
    EcologyMetrics,
    PhaseSpaceMonitor,
)


def setup_predator_prey_world() -> bsim.BioWorld:
    """Set up a classic predator-prey ecosystem."""
    # Use DefaultBioSolver with temperature for UI control
    from bsim.solver import DefaultBioSolver, TemperatureParams

    solver = DefaultBioSolver(
        temperature=TemperatureParams(initial=20.0, bounds=(0.0, 50.0)),
    )
    world = bsim.BioWorld(solver=solver)

    # Environment syncs temperature from solver (enables UI slider)
    env = Environment(
        temperature=20.0,
        water=80.0,
        food_availability=1.0,
        seasonal_cycle=False,
        sync_from_solver=True,  # Read temperature from solver state
    )

    # Populations - tuned for stable predator-prey coexistence
    rabbits = OrganismPopulation(
        name="Rabbits",
        initial_count=800,
        birth_rate=0.10,
        death_rate=0.02,
        optimal_temp=20.0,
        temp_tolerance=15.0,
        carrying_capacity=2000,
        seed=42,
    )

    foxes = OrganismPopulation(
        name="Foxes",
        initial_count=100,
        birth_rate=0.04,
        death_rate=0.02,
        optimal_temp=15.0,
        temp_tolerance=20.0,
        food_efficiency=0.8,
        carrying_capacity=300,
        seed=43,
    )

    # Interactions - tuned for stable dynamics
    predation = PredatorPreyInteraction(
        predation_rate=0.005,
        conversion_efficiency=1.0,
        seed=44,
    )

    # Monitors
    pop_monitor = PopulationMonitor(max_points=10000)
    phase_space = PhaseSpaceMonitor(x_species="Rabbits", y_species="Foxes")
    metrics = EcologyMetrics()

    # Wire everything together
    wb = bsim.WiringBuilder(world)
    wb.add("environment", env)
    wb.add("rabbits", rabbits)
    wb.add("foxes", foxes)
    wb.add("predation", predation)
    wb.add("pop_monitor", pop_monitor)
    wb.add("phase_space", phase_space)
    wb.add("metrics", metrics)

    # Environment -> Populations
    wb.connect("environment.out.conditions", ["rabbits.in.conditions", "foxes.in.conditions"])

    # Population states -> Predation & Monitors
    wb.connect("rabbits.out.population_state", [
        "predation.in.prey_state",
        "pop_monitor.in.population_state",
        "phase_space.in.population_state",
        "metrics.in.population_state",
    ])
    wb.connect("foxes.out.population_state", [
        "predation.in.predator_state",
        "pop_monitor.in.population_state",
        "phase_space.in.population_state",
        "metrics.in.population_state",
    ])

    # Predation effects
    wb.connect("predation.out.predation", ["rabbits.in.predation"])
    wb.connect("predation.out.food_gained", ["foxes.in.food_gained"])

    wb.apply()
    return world


PREDATOR_PREY_DESCRIPTION = """
## Classic Predator-Prey Simulation

This simulation demonstrates **Lotka-Volterra style** population dynamics between rabbits (prey) and foxes (predators).

### Network Architecture

```
┌─────────────┐
│ Environment │──conditions──┬────────────────────┐
└─────────────┘              │                    │
                             ▼                    ▼
                      ┌──────────┐         ┌──────────┐
                      │ Rabbits  │         │  Foxes   │
                      │  (prey)  │         │(predator)│
                      └────┬─────┘         └────┬─────┘
                           │                    │
              population_state         population_state
                           │                    │
                           ▼                    ▼
                      ┌────────────────────────────┐
                      │    Predation Interaction   │
                      └─────────────┬──────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               │               ▼
              (kills prey)          │        (feeds predator)
                    │               ▼               │
                    └────────► Monitors ◄──────────┘
```

### Population Parameters

| Species | Initial | Birth Rate | Death Rate | Carrying Capacity |
|---------|---------|------------|------------|-------------------|
| Rabbits | 800 | 0.10 | 0.02 | 2000 |
| Foxes | 100 | 0.04 | 0.02 | 300 |

### What to Observe

- **Population Oscillations**: Classic predator-prey cycles
- **Phase Space Plot**: Trajectory shows limit cycles or equilibrium
- **Coexistence**: Both species should survive long-term
- **Environmental Effects**: Temperature affects birth/death rates

### Parameters to Explore

- **Steps**: More steps = longer simulation time
- **dt**: Time step size (0.1 = 1/10 time unit per step)
"""

THREE_SPECIES_DESCRIPTION = """
## Three-Species Food Chain

This simulation models a more complex ecosystem with **wolves** preying on both **rabbits** and **deer**, with seasonal environmental variation.

### Network Architecture

```
┌─────────────────┐
│   Environment   │──conditions──┬──────────────┬──────────────┐
│ (seasonal temp) │              │              │              │
└─────────────────┘              ▼              ▼              ▼
                          ┌──────────┐   ┌──────────┐   ┌──────────┐
                          │ Rabbits  │   │   Deer   │   │  Wolves  │
                          └────┬─────┘   └────┬─────┘   └────┬─────┘
                               │              │              │
                               ▼              ▼              ▼
                          ┌─────────────────────────────────────┐
                          │       Predation Interactions        │
                          │   wolf→rabbit    wolf→deer          │
                          └─────────────────────────────────────┘
```

### Species Parameters

| Species | Initial | Preset | Role |
|---------|---------|--------|------|
| Rabbits | 800 | rabbit | Primary prey |
| Deer | 200 | deer | Secondary prey |
| Wolves | 30 | custom | Apex predator |

### Predation Dynamics

| Interaction | Rate | Conversion |
|-------------|------|------------|
| Wolf → Rabbit | 0.0005 | 10% |
| Wolf → Deer | 0.0008 | 20% |

### What to Observe

- **Seasonal Effects**: Temperature oscillates, affecting all species
- **Prey Competition**: Rabbits and deer compete for plant resources
- **Predator Flexibility**: Wolves switch between prey sources
- **Complex Dynamics**: More unpredictable than 2-species system

### Parameters to Explore

- **Season Period**: 100 time units per full cycle
- Adjust steps to see multiple seasonal cycles
"""


def setup_three_species_world() -> bsim.BioWorld:
    """Set up a three-species food chain: grass -> rabbits -> foxes."""
    # Use DefaultBioSolver with temperature for UI control
    from bsim.solver import DefaultBioSolver, TemperatureParams

    solver = DefaultBioSolver(
        temperature=TemperatureParams(initial=20.0, bounds=(-10.0, 50.0)),
    )
    world = bsim.BioWorld(solver=solver)

    # Environment with seasonal variation (syncs base temp from solver)
    env = Environment(
        temperature=20.0,
        water=80.0,
        food_availability=1.2,
        seasonal_cycle=True,
        season_period=100.0,  # Faster seasons for demo
        sync_from_solver=True,  # Base temperature from solver, seasonal on top
    )

    # Populations
    rabbits = OrganismPopulation(
        name="Rabbits",
        initial_count=800,
        preset="rabbit",
        carrying_capacity=3000,
        seed=42,
    )

    deer = OrganismPopulation(
        name="Deer",
        initial_count=200,
        preset="deer",
        carrying_capacity=1000,
        seed=45,
    )

    wolves = OrganismPopulation(
        name="Wolves",
        initial_count=30,
        birth_rate=0.02,
        death_rate=0.025,
        optimal_temp=10.0,
        temp_tolerance=25.0,
        food_efficiency=0.8,
        carrying_capacity=200,
        seed=43,
    )

    # Interactions
    wolf_rabbit = PredatorPreyInteraction(
        predation_rate=0.0005,
        conversion_efficiency=0.10,
        seed=44,
    )

    wolf_deer = PredatorPreyInteraction(
        predation_rate=0.0008,
        conversion_efficiency=0.20,
        seed=46,
    )

    # Monitors
    pop_monitor = PopulationMonitor(max_points=10000)
    phase_space = PhaseSpaceMonitor(x_species="Rabbits", y_species="Wolves")
    metrics = EcologyMetrics()

    # Wire
    wb = bsim.WiringBuilder(world)
    wb.add("environment", env)
    wb.add("rabbits", rabbits)
    wb.add("deer", deer)
    wb.add("wolves", wolves)
    wb.add("wolf_rabbit", wolf_rabbit)
    wb.add("wolf_deer", wolf_deer)
    wb.add("pop_monitor", pop_monitor)
    wb.add("phase_space", phase_space)
    wb.add("metrics", metrics)

    # Environment -> All populations
    wb.connect("environment.out.conditions", [
        "rabbits.in.conditions",
        "deer.in.conditions",
        "wolves.in.conditions",
    ])

    # Prey states -> Interactions & Monitors
    wb.connect("rabbits.out.population_state", [
        "wolf_rabbit.in.prey_state",
        "pop_monitor.in.population_state",
        "phase_space.in.population_state",
        "metrics.in.population_state",
    ])
    wb.connect("deer.out.population_state", [
        "wolf_deer.in.prey_state",
        "pop_monitor.in.population_state",
        "metrics.in.population_state",
    ])
    wb.connect("wolves.out.population_state", [
        "wolf_rabbit.in.predator_state",
        "wolf_deer.in.predator_state",
        "pop_monitor.in.population_state",
        "phase_space.in.population_state",
        "metrics.in.population_state",
    ])

    # Predation effects
    wb.connect("wolf_rabbit.out.predation", ["rabbits.in.predation"])
    wb.connect("wolf_deer.out.predation", ["deer.in.predation"])
    wb.connect("wolf_rabbit.out.food_gained", ["wolves.in.food_gained"])
    wb.connect("wolf_deer.out.food_gained", ["wolves.in.food_gained"])

    wb.apply()
    return world


def main() -> None:
    """Launch SimUI with the ecology demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Ecology SimUI Demo")
    parser.add_argument(
        "--mode",
        choices=["predator-prey", "three-species"],
        default="predator-prey",
        help="Demo mode: 'predator-prey' for classic 2-species, 'three-species' for food chain",
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Optional YAML config file to load instead of built-in modes",
    )
    parser.add_argument("--port", type=int, default=8765, help="SimUI server port")
    parser.add_argument("--steps", type=int, default=2000, help="Simulation steps")
    parser.add_argument("--dt", type=float, default=0.1, help="Time step (time units)")
    args = parser.parse_args()

    print("Ecology Pack - SimUI Demo")
    print("=" * 60)

    if args.config:
        print(f"Loading config: {args.config}")
        world = bsim.BioWorld(solver=bsim.FixedStepSolver())
        world.load_wiring(args.config)
        description = "Custom configuration loaded from YAML file."
        title = "Ecology Simulation"
    elif args.mode == "predator-prey":
        print("Mode: Classic Predator-Prey (Rabbits & Foxes)")
        world = setup_predator_prey_world()
        description = PREDATOR_PREY_DESCRIPTION
        title = "Predator-Prey Simulation"
    else:
        print("Mode: Three-Species Food Chain (Rabbits, Deer & Wolves)")
        world = setup_three_species_world()
        description = THREE_SPECIES_DESCRIPTION
        title = "Three-Species Food Chain"

    print(f"Modules: {len(world._biomodule_listeners)}")
    print(f"Connections: {len(world.describe_wiring())}")
    print(f"\nStarting SimUI server on port {args.port}...")
    print(f"Open http://localhost:{args.port}/ui/ in your browser.")
    print("Press Ctrl+C to stop.\n")

    # Import and run SimUI
    try:
        from bsim.simui import Interface, Number, Button, EventLog, VisualsPanel

        # Create UI interface with ecology-appropriate defaults
        ui = Interface(
            world,
            title=title,
            description=description,
            controls=[
                Number("steps", args.steps, label="Steps", minimum=100, maximum=50000, step=100),
                Number("dt", args.dt, label="dt (time)", minimum=0.01, maximum=1.0, step=0.01),
                Button("Run"),
            ],
            outputs=[
                EventLog(limit=50),
                VisualsPanel(refresh="auto", interval_ms=500),
            ],
        )

        # Launch the server (blocking)
        ui.launch(host="127.0.0.1", port=args.port, open_browser=True)
    except ImportError as e:
        print(f"Error: Could not import SimUI: {e}")
        print("Make sure dependencies are installed: pip install fastapi uvicorn")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
