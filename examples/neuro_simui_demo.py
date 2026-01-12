#!/usr/bin/env python3
"""
SimUI demo for the neuro pack: launch an interactive dashboard.

Demonstrates:
- Running the SimUI server with neuro modules
- Interactive visualization of rasters, rates, and membrane voltages
- Config-driven simulation via SimUI controls

Run:
    pip install -e .
    python examples/neuro_simui_demo.py

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

from bsim.packs.neuro import (
    PoissonInput,
    StepCurrent,
    IzhikevichPopulation,
    ExpSynapseCurrent,
    SpikeMonitor,
    RateMonitor,
    StateMonitor,
    NeuroMetrics,
)


def setup_single_neuron_world() -> bsim.BioWorld:
    """Set up a simple single-neuron world for SimUI."""
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())

    # Simple single neuron setup
    current_source = StepCurrent(I=10.0)
    neuron = IzhikevichPopulation(n=1, preset="RS", sample_indices=[0])
    spike_monitor = SpikeMonitor(max_neurons=1, width=600, height=200)
    state_monitor = StateMonitor()
    metrics = NeuroMetrics(n_neurons=1)

    wb = bsim.WiringBuilder(world)
    wb.add("current", current_source)
    wb.add("neuron", neuron)
    wb.add("spike_mon", spike_monitor)
    wb.add("state_mon", state_monitor)
    wb.add("metrics", metrics)

    wb.connect("current.out.current", ["neuron.in.current"])
    wb.connect("neuron.out.spikes", ["spike_mon.in.spikes", "metrics.in.spikes"])
    wb.connect("neuron.out.state", ["state_mon.in.state"])
    wb.apply()

    return world


def setup_microcircuit_world() -> bsim.BioWorld:
    """Set up an E/I microcircuit world for SimUI."""
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())

    n_exc, n_inh = 40, 10
    n_total = n_exc + n_inh

    # Input
    poisson_input = PoissonInput(n=n_exc, rate_hz=15.0, seed=42)

    # Populations (I_bias provides baseline drive to ensure spiking activity)
    exc_pop = IzhikevichPopulation(n=n_exc, preset="RS", sample_indices=[0, 1, 2], I_bias=5.0)
    inh_pop = IzhikevichPopulation(n=n_inh, preset="FS", sample_indices=[0], I_bias=5.0)

    # Synapses
    syn_ext_e = ExpSynapseCurrent(n_pre=n_exc, n_post=n_exc, p_connect=0.1, weight=1.0, tau=0.005, seed=42)
    syn_ee = ExpSynapseCurrent(n_pre=n_exc, n_post=n_exc, p_connect=0.1, weight=0.3, tau=0.005, seed=43)
    syn_ei = ExpSynapseCurrent(n_pre=n_exc, n_post=n_inh, p_connect=0.1, weight=0.5, tau=0.005, seed=44)
    syn_ie = ExpSynapseCurrent(n_pre=n_inh, n_post=n_exc, p_connect=0.1, weight=-1.5, tau=0.010, seed=45)
    syn_ii = ExpSynapseCurrent(n_pre=n_inh, n_post=n_inh, p_connect=0.1, weight=-0.5, tau=0.010, seed=46)

    # Monitors
    spike_mon_e = SpikeMonitor(max_neurons=n_exc, width=600, height=200)
    spike_mon_i = SpikeMonitor(max_neurons=n_inh, width=600, height=100)
    rate_mon = RateMonitor(window_size=0.02, n_neurons=n_total)
    state_mon = StateMonitor()
    metrics = NeuroMetrics(n_neurons=n_total)

    # Wire
    wb = bsim.WiringBuilder(world)
    wb.add("poisson", poisson_input)
    wb.add("exc", exc_pop)
    wb.add("inh", inh_pop)
    wb.add("syn_ext_e", syn_ext_e)
    wb.add("syn_ee", syn_ee)
    wb.add("syn_ei", syn_ei)
    wb.add("syn_ie", syn_ie)
    wb.add("syn_ii", syn_ii)
    wb.add("spike_mon_e", spike_mon_e)
    wb.add("spike_mon_i", spike_mon_i)
    wb.add("rate_mon", rate_mon)
    wb.add("state_mon", state_mon)
    wb.add("metrics", metrics)

    wb.connect("poisson.out.spikes", ["syn_ext_e.in.spikes"])
    wb.connect("syn_ext_e.out.current", ["exc.in.current"])

    wb.connect("exc.out.spikes", [
        "syn_ee.in.spikes",
        "syn_ei.in.spikes",
        "spike_mon_e.in.spikes",
        "rate_mon.in.spikes",
        "metrics.in.spikes",
    ])
    wb.connect("exc.out.state", ["state_mon.in.state"])

    wb.connect("inh.out.spikes", [
        "syn_ie.in.spikes",
        "syn_ii.in.spikes",
        "spike_mon_i.in.spikes",
        "rate_mon.in.spikes",
    ])

    wb.connect("syn_ee.out.current", ["exc.in.current"])
    wb.connect("syn_ie.out.current", ["exc.in.current"])
    wb.connect("syn_ei.out.current", ["inh.in.current"])
    wb.connect("syn_ii.out.current", ["inh.in.current"])

    wb.apply()

    return world


SINGLE_NEURON_DESCRIPTION = """
## Single Neuron Simulation

This simulation demonstrates a single **Izhikevich neuron** receiving constant current injection.

### Components

| Module | Description |
|--------|-------------|
| **StepCurrent** | Injects 10 pA of constant current |
| **IzhikevichPopulation** | Single RS (Regular Spiking) neuron |
| **SpikeMonitor** | Records spike times as a raster plot |
| **StateMonitor** | Tracks membrane potential over time |

### Izhikevich Model

The neuron follows the Izhikevich model equations:

```
dv/dt = 0.04v² + 5v + 140 - u + I
du/dt = a(bv - u)
```

When `v >= 30 mV`, the neuron fires and resets:
- `v → c`
- `u → u + d`

### What to Observe

- **Membrane Potential**: Watch the characteristic RS firing pattern with adaptation
- **Spike Raster**: Each vertical line represents a spike event
- **Firing Rate**: Note how the neuron settles into a regular rhythm
"""

MICROCIRCUIT_DESCRIPTION = """
## E/I Balanced Microcircuit

This simulation models a small cortical microcircuit with **excitatory (E)** and **inhibitory (I)** neuron populations, demonstrating emergent network dynamics.

### Network Architecture

```
┌─────────────┐     ┌─────────────┐
│   Poisson   │────▶│  Excitatory │◀───┐
│   Input     │     │   (40 RS)   │────┼───┐
└─────────────┘     └──────┬──────┘    │   │
                           │           │   │
                    E→I    │    E→E    │   │
                           ▼           │   │
                    ┌─────────────┐    │   │
                    │ Inhibitory  │────┘   │
                    │  (10 FS)    │◀───────┘
                    └─────────────┘   I→E, I→I
```

### Populations

| Population | Count | Type | Description |
|------------|-------|------|-------------|
| Excitatory | 40 | RS (Regular Spiking) | Pyramidal-like neurons |
| Inhibitory | 10 | FS (Fast Spiking) | Interneuron-like cells |

### Synaptic Connections

| Connection | Probability | Weight | Time Constant |
|------------|-------------|--------|---------------|
| External→E | 10% | +1.0 | 5 ms |
| E→E | 10% | +0.3 | 5 ms |
| E→I | 10% | +0.5 | 5 ms |
| I→E | 10% | -1.5 | 10 ms |
| I→I | 10% | -0.5 | 10 ms |

### What to Observe

- **E/I Balance**: Inhibition regulates excitatory activity
- **Population Dynamics**: Correlated activity patterns emerge
- **Firing Rates**: Compare E vs I population statistics
- **Membrane Traces**: Sample neurons show voltage dynamics

### Parameters to Explore

Try adjusting:
- **Steps**: More steps = longer simulation time
- **dt**: Smaller dt = more accurate but slower
"""


def main() -> None:
    """Launch SimUI with the neuro microcircuit demo."""
    import argparse

    parser = argparse.ArgumentParser(description="Neuro SimUI Demo")
    parser.add_argument(
        "--mode",
        choices=["single", "circuit"],
        default="circuit",
        help="Demo mode: 'single' for single neuron, 'circuit' for E/I microcircuit",
    )
    parser.add_argument("--port", type=int, default=8765, help="SimUI server port")
    parser.add_argument("--steps", type=int, default=3000, help="Simulation steps")
    parser.add_argument("--dt", type=float, default=0.0001, help="Time step (seconds)")
    args = parser.parse_args()

    print("Neuro Pack - SimUI Demo")
    print("=" * 60)

    if args.mode == "single":
        print("Mode: Single Neuron (RS with DC current)")
        world = setup_single_neuron_world()
        description = SINGLE_NEURON_DESCRIPTION
        title = "Single Neuron Simulation"
    else:
        print("Mode: E/I Microcircuit (40E + 10I with Poisson input)")
        world = setup_microcircuit_world()
        description = MICROCIRCUIT_DESCRIPTION
        title = "E/I Microcircuit Simulation"

    print(f"Modules: {len(world._biomodule_listeners)}")
    print(f"Connections: {len(world.describe_wiring())}")
    print(f"\nStarting SimUI server on port {args.port}...")
    print(f"Open http://localhost:{args.port}/ui/ in your browser.")
    print("Press Ctrl+C to stop.\n")

    # Import and run SimUI
    try:
        from bsim.simui import Interface, Number, Button, EventLog, VisualsPanel

        # Create UI interface with neuro-appropriate defaults
        ui = Interface(
            world,
            title=title,
            description=description,
            controls=[
                Number("steps", args.steps, label="Steps", minimum=100, maximum=50000, step=100),
                Number("dt", args.dt, label="dt (s)", minimum=0.00001, maximum=0.01, step=0.00001),
                Button("Run"),
            ],
            outputs=[
                EventLog(limit=100),
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
