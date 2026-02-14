# Neuro Pack: Computational Neuroscience Modules

This document describes the neuro pack (`bsim.packs.neuro`), a reference implementation for simulating spiking neural networks with `bsim`.

## Overview

The neuro pack provides a minimal but composable set of `BioModule`s for:
- Generating spike inputs (Poisson processes, current injection)
- Simulating spiking neurons (Izhikevich model)
- Converting spikes to synaptic currents
- Monitoring and visualizing network activity

## Quick Start

### Installation

The neuro pack is included with bsim. No additional installation is required.

```python
from bsim.packs.neuro import (
    PoissonInput,
    StepCurrent,
    IzhikevichPopulation,
    ExpSynapseCurrent,
    SpikeMonitor,
    RateMonitor,
    StateMonitor,
    NeuroMetrics,
    PRESET_RS,
    PRESET_FS,
)
```

### Running Examples

The heavier end-to-end demos and wiring configs live in the companion repo `models`:

- https://github.com/Biosimulant/models

Clone it and run examples from that repo:

```bash
git clone https://github.com/Biosimulant/models.git
cd models
```

**Single neuron space (local wiring-spec runner):**
```bash
python -m bsim spaces/neuro-single-neuron/wiring.yaml
```

**E/I microcircuit space (local wiring-spec runner):**
```bash
python -m bsim spaces/neuro-microcircuit/wiring.yaml
```

**Local SimUI (optional):**
```bash
python spaces/neuro-microcircuit/simui_local.py
# Then open http://localhost:8765
```

**Config-driven runs (no code changes):**
```bash
# Using YAML
python -c "
import bsim
w = bsim.BioWorld()
bsim.load_wiring(w, '<path-to-neuro_single_neuron.yaml>')
w.run(duration=0.5, tick_dt=0.0001)
print('Simulation complete')
for v in w.collect_visuals():
    print(f'  {v[\"module\"]}: {[x[\"render\"] for x in v[\"visuals\"]]}')"

# Using TOML
python -c "
import bsim
w = bsim.BioWorld()
bsim.load_wiring(w, '<path-to-neuro_microcircuit.toml>')
w.run(duration=0.3, tick_dt=0.0001)
print([v['module'] for v in w.collect_visuals()])"
```

## Module Reference

### Input Modules

#### PoissonInput

Generates spikes according to a Poisson process.

**Parameters:**
- `n: int` - Number of spike sources (default: 100)
- `rate_hz: float` - Firing rate in Hz (default: 10.0)
- `seed: int | None` - Random seed for reproducibility

**Outputs:**
- `spikes` - Payload: `{"t": float, "ids": [int, ...]}`

**Example:**
```python
poisson = PoissonInput(n=100, rate_hz=15.0, seed=42)
```

#### StepCurrent / DCInput

Injects constant or time-varying current.

**Parameters:**
- `I: float` - Current amplitude (default: 10.0)
- `schedule: list[tuple] | None` - Optional `[(start, end, I_value), ...]` for time-varying current

**Outputs:**
- `current` - Payload: `{"t": float, "I": float}`

**Example:**
```python
# Constant current
dc = StepCurrent(I=10.0)

# Time-varying current: 0 for t<0.1, then 15 for 0.1<=t<0.3, then 0 again
step = StepCurrent(I=0.0, schedule=[(0.1, 0.3, 15.0)])
```

### Population Modules

#### IzhikevichPopulation

A population of Izhikevich spiking neurons.

**Parameters:**
- `n: int` - Number of neurons (default: 100)
- `a, b, c, d: float` - Izhikevich model parameters
- `preset: str` - Preset name: "RS", "FS", "Bursting", "Chattering", "LTS"
- `v_init: float` - Initial membrane potential (default: -65.0 mV)
- `u_init: float | None` - Initial recovery variable (default: b * v_init)
- `I_bias: float` - Constant bias current (default: 0.0)
- `sample_indices: list[int] | None` - Neuron indices for state output (default: [0,1,2,3,4])

**Inputs:**
- `current` - Payload: `{"t": float, "I": float}` or `{"t": float, "I": [float, ...]}`

**Outputs:**
- `spikes` - Payload: `{"t": float, "ids": [int, ...]}`
- `state` - Payload: `{"t": float, "indices": [int, ...], "v": [float, ...], "u": [float, ...]}`

**Presets:**

| Preset | a | b | c | d | Behavior |
|--------|---|---|---|---|----------|
| RS | 0.02 | 0.2 | -65 | 8 | Regular Spiking (cortical excitatory) |
| FS | 0.1 | 0.2 | -65 | 2 | Fast Spiking (cortical inhibitory) |
| Bursting | 0.02 | 0.2 | -55 | 4 | Intrinsically Bursting |
| Chattering | 0.02 | 0.2 | -50 | 2 | Chattering |
| LTS | 0.02 | 0.25 | -65 | 2 | Low-Threshold Spiking |

**Example:**
```python
exc_pop = IzhikevichPopulation(n=80, preset="RS", I_bias=0.0)
inh_pop = IzhikevichPopulation(n=20, preset="FS")
```

### Synapse Modules

#### ExpSynapseCurrent

Converts incoming spikes to exponentially decaying synaptic current.

**Parameters:**
- `n_pre: int` - Number of pre-synaptic neurons (default: 100)
- `n_post: int` - Number of post-synaptic neurons (default: 100)
- `p_connect: float` - Connection probability (default: 0.1)
- `weight: float` - Synaptic weight (default: 1.0)
- `tau: float` - Decay time constant in seconds (default: 0.01)
- `seed: int | None` - Random seed for connectivity
- `delay_steps: int` - Spike delivery delay (default: 0)

**Inputs:**
- `spikes` - Payload: `{"t": float, "ids": [int, ...]}`

**Outputs:**
- `current` - Payload: `{"t": float, "I": [float, ...]}`

**Example:**
```python
# E -> I synapse with 10% connectivity
syn_ei = ExpSynapseCurrent(
    n_pre=80,
    n_post=20,
    p_connect=0.1,
    weight=0.5,
    tau=0.005,
    seed=42,
)
```

### Monitor Modules

#### SpikeMonitor

Collects spike events and produces a raster plot (SVG).

**Parameters:**
- `max_events: int` - Maximum spike events to store (default: 10000)
- `max_neurons: int | None` - Maximum neuron index to display
- `width: int` - SVG width in pixels (default: 600)
- `height: int` - SVG height in pixels (default: 300)

**Inputs:**
- `spikes`

**Visualizes:**
- `image` VisualSpec with `data.src` as SVG data URI

#### RateMonitor

Computes population firing rate.

**Parameters:**
- `window_size: float` - Time window in seconds (default: 0.05)
- `n_neurons: int` - Total neuron count for rate normalization (default: 100)

**Inputs:**
- `spikes`

**Visualizes:**
- `timeseries` VisualSpec: Population rate in Hz

#### StateMonitor

Records membrane voltage traces.

**Parameters:**
- `max_points: int` - Maximum points per trace (default: 5000)

**Inputs:**
- `state`

**Visualizes:**
- `timeseries` VisualSpec: Vm traces for monitored neurons

#### NeuroMetrics

Computes summary statistics.

**Parameters:**
- `n_neurons: int` - Total neuron count (default: 100)

**Inputs:**
- `spikes`

**Visualizes:**
- `table` VisualSpec with columns: Metric, Value

Metrics computed:
- Total Spikes
- Active Neurons
- Duration (s)
- Mean Rate (Hz)
- ISI CV (coefficient of variation of inter-spike intervals)

## Topics and Payloads

The neuro pack uses a small set of stable topic names for inter-module communication.

### `spikes`

Discrete spike events from populations or input generators.

```json
{"t": 0.123, "ids": [0, 5, 12, 47]}
```

- `t`: Time in seconds
- `ids`: List of neuron indices that spiked

### `current`

Injected current (scalar or per-neuron).

```json
{"t": 0.123, "I": 10.0}
```
or
```json
{"t": 0.123, "I": [1.2, 0.8, 1.5, ...]}
```

- `t`: Time in seconds
- `I`: Current amplitude (float) or per-neuron array

### `state`

Neuron state for monitoring/visualization.

```json
{"t": 0.123, "indices": [0, 1, 2], "v": [-65.2, -60.1, -70.0], "u": [-13.0, -12.0, -14.0]}
```

- `t`: Time in seconds
- `indices`: Sampled neuron indices
- `v`: Membrane potentials (mV)
- `u`: Recovery variables

## Visual Outputs

The neuro pack uses the SimUI VisualSpec contract:

### Raster Plot (Image)

```python
{
    "render": "image",
    "data": {
        "src": "data:image/svg+xml,...",  # URL-encoded SVG
        "alt": "Raster plot (500 spikes)",
        "width": 600,
        "height": 300
    }
}
```

### Population Rate (Timeseries)

```python
{
    "render": "timeseries",
    "data": {
        "series": [
            {"name": "Population Rate (Hz)", "points": [[0.0, 10.5], [0.001, 11.2], ...]}
        ]
    }
}
```

### Vm Traces (Timeseries)

```python
{
    "render": "timeseries",
    "data": {
        "series": [
            {"name": "Neuron 0 Vm (mV)", "points": [[0.0, -65.0], ...]},
            {"name": "Neuron 1 Vm (mV)", "points": [[0.0, -65.0], ...]}
        ]
    }
}
```

### Metrics (Table)

```python
{
    "render": "table",
    "data": {
        "columns": ["Metric", "Value"],
        "rows": [
            ["Total Spikes", "1234"],
            ["Active Neurons", "95"],
            ["Duration (s)", "0.500"],
            ["Mean Rate (Hz)", "24.68"],
            ["ISI CV", "0.85"]
        ]
    }
}
```

## Example Scenarios

### Scenario A: Single Neuron Regimes

Demonstrates how Izhikevich parameters affect spiking behavior.

```python
import bsim
from bsim.packs.neuro import StepCurrent, IzhikevichPopulation, StateMonitor, SpikeMonitor

world = bsim.BioWorld()

# Regular spiking neuron with DC input
current = StepCurrent(I=10.0)
neuron = IzhikevichPopulation(n=1, preset="RS")
spike_mon = SpikeMonitor()
state_mon = StateMonitor()

wb = bsim.WiringBuilder(world)
wb.add("current", current).add("neuron", neuron)
wb.add("spike_mon", spike_mon).add("state_mon", state_mon)
wb.connect("current.current", ["neuron.current"])
wb.connect("neuron.spikes", ["spike_mon.spikes"])
wb.connect("neuron.state", ["state_mon.state"])
wb.apply()

world.run(duration=0.5, tick_dt=0.0001)  # 500ms
visuals = world.collect_visuals()
```

### Scenario B: E/I Microcircuit

Balanced excitation/inhibition with Poisson drive.

See `models/spaces/neuro-microcircuit/space.yaml` for the composed space manifest.

Key observations:
- **Balanced E/I**: Asynchronous irregular (AI) spiking
- **Strong inhibition**: Activity suppression
- **Weak inhibition**: Synchronization/oscillations

## Config Files

The neuro pack supports YAML and TOML wiring configs:

Example wiring specs are kept in `models/spaces/*/wiring.yaml`:

**neuro_single_neuron.yaml**
**neuro_single_neuron.toml**
**neuro_microcircuit.yaml**
**neuro_microcircuit.toml**

Load and run:
```python
import bsim
world = bsim.BioWorld()
bsim.load_wiring(world, "<path-to-wiring.yaml>")
world.run(duration=0.3, tick_dt=0.0001)
```

## See Also

- [VisualSpec Contract](../product-docs/contracts/visualspec.md)
- [Wiring Spec](../product-docs/contracts/wiring-spec.md)
- [SimUI API](../product-docs/contracts/simui-api.md)
