# Neuro Pack: Computational Neuroscience Modules

This document describes the neuro model packs in the companion `models` repository, a reference implementation for simulating spiking neural networks with `biosim`.

> **Important**: The neuro modules are **not** bundled inside the `biosim` core library. They live as separate model packs in the [`Biosimulant/models`](https://github.com/Biosimulant/models) repo under `models/models/neuro-*`.

## Overview

The neuro packs provide a minimal but composable set of `BioModule`s for:
- Generating spike inputs (Poisson processes, current injection)
- Simulating spiking neurons (Izhikevich model, Hodgkin-Huxley model)
- Converting spikes to synaptic currents
- Monitoring and visualizing network activity

## Available Models

| Model Pack | Entrypoint | Description |
|------------|-----------|-------------|
| `neuro-izhikevich-population` | `src.izhikevich:IzhikevichPopulation` | Izhikevich spiking neuron population (RS/FS/Bursting/Chattering/LTS presets) |
| `neuro-hodgkin-huxley-population` | `src.hodgkin_huxley:HodgkinHuxleyPopulation` | Classic Hodgkin-Huxley conductance-based neurons (Na+/K+/leak channels) |
| `neuro-poisson-input` | `src.poisson_input:PoissonInput` | Poisson spike generator |
| `neuro-step-current` | `src.step_current:StepCurrent` | Constant/scheduled current injection (alias: `DCInput`) |
| `neuro-exp-synapse-current` | `src.exp_synapse:ExpSynapseCurrent` | Exponential-decay synaptic current |
| `neuro-spike-monitor` | `src.spike_monitor:SpikeMonitor` | Spike raster visualization (SVG) |
| `neuro-rate-monitor` | `src.rate_monitor:RateMonitor` | Population firing rate computation |
| `neuro-state-monitor` | `src.state_monitor:StateMonitor` | Neuron state tracking (Vm traces) |
| `neuro-hodgkin-huxley-state-monitor` | `src.hodgkin_huxley_monitor:HHStateMonitor` | HH-specific state monitor (Vm, gating variables m/h/n) |
| `neuro-spike-metrics` | `src.neuro_metrics:NeuroMetrics` | Summary statistics (spike count, rate, ISI CV) |

## Quick Start

### Installation

Clone the models repository alongside biosim:

```bash
git clone https://github.com/Biosimulant/models.git
cd models
pip install -e ../biosim            # Install biosim core
pip install -e ../biosim'[ui]'      # Optional: for SimUI
```

### Running Labs

Pre-composed simulation labs are in `models/spaces/`:

**Single neuron lab:**
```bash
python -m biosim spaces/neuro-single-neuron/wiring.yaml
```

**E/I microcircuit lab (50 neurons):**
```bash
python -m biosim spaces/neuro-microcircuit/wiring.yaml
```

**Hodgkin-Huxley single neuron:**
```bash
python -m biosim spaces/neuro-hodgkin-huxley-neuron/wiring.yaml
```

**Local SimUI (optional):**
```bash
python spaces/neuro-microcircuit/simui_local.py
# Then open http://localhost:7860/ui/
```

**Config-driven runs (no code changes):**
```bash
python -c "
import biosim
w = biosim.BioWorld(communication_step=0.001)
biosim.load_wiring(w, 'spaces/neuro-single-neuron/wiring.yaml')
w.run(duration=0.5, tick_dt=0.0001)
print('Simulation complete')
for v in w.collect_visuals():
    print(f'  {v[\"module\"]}: {[x[\"render\"] for x in v[\"visuals\"]]}')"
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
- `spikes` - BioSignal with value: list of spiked neuron IDs

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
- `current` - `ScalarSignal` carrying the current amplitude

**Visualizes:**
- `timeseries` VisualSpec: current injection over time

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
- `sample_indices: list[int] | None` - Neuron indices for state output (default: first 5)

**Inputs:**
- `current` - `ScalarSignal` for broadcast current or `ArraySignal` for per-neuron current

**Outputs:**
- `spikes` - `EventSignal` with `value: list[int]` for spiked neuron IDs
- `state` - `RecordSignal` with `value: {"t": float, "indices": [int, ...], "v": [float, ...], "u": [float, ...]}`

**Presets:**

| Preset | a | b | c | d | Behavior |
|--------|---|---|---|---|----------|
| RS | 0.02 | 0.2 | -65 | 8 | Regular Spiking (cortical excitatory) |
| FS | 0.1 | 0.2 | -65 | 2 | Fast Spiking (cortical inhibitory) |
| Bursting | 0.02 | 0.2 | -55 | 4 | Intrinsically Bursting |
| Chattering | 0.02 | 0.2 | -50 | 2 | Chattering |
| LTS | 0.02 | 0.25 | -65 | 2 | Low-Threshold Spiking |

**Visualizes:**
- `timeseries` VisualSpec: membrane potential of sampled neurons

**Example:**
```python
exc_pop = IzhikevichPopulation(n=80, preset="RS", I_bias=0.0)
inh_pop = IzhikevichPopulation(n=20, preset="FS")
```

#### HodgkinHuxleyPopulation

A population of Hodgkin-Huxley conductance-based spiking neurons (1952 squid giant axon model).

Uses voltage-gated Na+, K+, and leak channels with gating variables m, h, n.

**Inputs:**
- `current` - typed current input signal (`ScalarSignal` or `ArraySignal`)

**Outputs:**
- `spikes` - `EventSignal` with spiked neuron IDs
- `state` - `RecordSignal` with membrane state (Vm, gating variables)

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
- `spikes` - `EventSignal` with spiked neuron IDs

**Outputs:**
- `current` - `ArraySignal` with per-neuron synaptic current

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

#### HHStateMonitor

Hodgkin-Huxley-specific state monitor that tracks membrane voltage and gating variables (m, h, n).

**Inputs:**
- `state`

**Visualizes:**
- `timeseries` VisualSpec: Vm and gating variable traces

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

## Signal Conventions

The neuro packs use typed 1.5 signals with explicit `SignalSpec` declarations on every port.

### Spike signals (`EventSignal`)
Emitted by populations and input generators. The `value` field contains the neuron indices that spiked during the current communication window:
```python
from biosim import EventSignal, SignalSpec

spike_spec = SignalSpec.event(description="Neuron indices that spiked in this boundary")
EventSignal(
    source="neuron",
    name="spikes",
    value=[0, 5, 12, 47],
    emitted_at=0.123,
    spec=spike_spec,
)
```

### Current signals (`ScalarSignal` / `ArraySignal`)
Injected current can be broadcast as a scalar or provided per neuron as an array:
```python
from biosim import ArraySignal, ScalarSignal, SignalSpec

scalar_current_spec = SignalSpec.scalar(dtype="float64", emitted_unit="nA")
ScalarSignal(
    source="dc",
    name="current",
    value=10.0,
    emitted_at=0.123,
    spec=scalar_current_spec,
)

array_current_spec = SignalSpec.array(dtype="float64", shape=(4,), emitted_unit="nA")
ArraySignal(
    source="synapse",
    name="current",
    value=[1.2, 0.8, 1.5, 0.4],
    emitted_at=0.123,
    spec=array_current_spec,
)
```

### State signals (`RecordSignal`)
Neuron state for monitoring and visualization is carried as a schema-bound record:
```python
from biosim import RecordSignal, SignalSpec

state_spec = SignalSpec.record(
    schema={"t": "float64", "indices": "list[int]", "v": "list[float64]", "u": "list[float64]"},
)
RecordSignal(
    source="neuron",
    name="state",
    value={
        "t": 0.123,
        "indices": [0, 1, 2],
        "v": [-65.2, -60.1, -70.0],
        "u": [-13.0, -12.0, -14.0],
    },
    emitted_at=0.123,
    spec=state_spec,
)
```

## Visual Outputs

The neuro packs use the SimUI VisualSpec contract. VisualSpecs may include an optional `description` field for hover text/captions.

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
            {"name": "Neuron 0", "points": [[0.0, -65.0], ...]},
            {"name": "Neuron 1", "points": [[0.0, -65.0], ...]}
        ],
        "title": "IzhikevichPopulation (n=100) Membrane Potential"
    },
    "description": "Membrane potential of sampled Izhikevich neurons..."
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

Demonstrates how Izhikevich parameters affect spiking behavior. Uses models from the `models` repo wired together:

```yaml
# spaces/neuro-single-neuron/space.yaml (abbreviated)
models:
  - alias: current
    manifest_path: models/neuro-step-current/model.yaml
    parameters: { I: 10.0 }
  - alias: neuron
    manifest_path: models/neuro-izhikevich-population/model.yaml
    parameters: { n: 1, preset: "RS" }
  - alias: spike_mon
    manifest_path: models/neuro-spike-monitor/model.yaml
  - alias: state_mon
    manifest_path: models/neuro-state-monitor/model.yaml
wiring:
  - from: current.current
    to: [neuron.current]
  - from: neuron.spikes
    to: [spike_mon.spikes]
  - from: neuron.state
    to: [state_mon.state]
```

### Scenario B: E/I Microcircuit

Balanced excitation/inhibition with Poisson drive.

See `models/spaces/neuro-microcircuit/space.yaml` for the composed lab manifest.

Key observations:
- **Balanced E/I**: Asynchronous irregular (AI) spiking
- **Strong inhibition**: Activity suppression
- **Weak inhibition**: Synchronization/oscillations

### Scenario C: Hodgkin-Huxley Neuron

Classic conductance-based model with detailed ion channel dynamics.

See `models/spaces/neuro-hodgkin-huxley-neuron/space.yaml` for the composed lab manifest.

## Config Files

Example wiring specs are in `models/spaces/` (lab manifests):

- `spaces/neuro-single-neuron/` - Single Izhikevich neuron + step current + monitors
- `spaces/neuro-microcircuit/` - 50-neuron E/I network with Poisson drive
- `spaces/neuro-hodgkin-huxley-neuron/` - Single HH neuron + monitors

Load and run:
```python
import biosim
world = biosim.BioWorld()
biosim.load_wiring(world, "spaces/neuro-single-neuron/wiring.yaml")
world.run(duration=0.3, tick_dt=0.0001)
```

## See Also

- [biosim README](../README.md) - VisualSpec types, SimUI API reference
- [Wiring docs](wiring.md) - WiringBuilder and loader API
- [Config docs](config.md) - YAML/TOML config file format
- [models STANDARDS.md](https://github.com/Biosimulant/models/blob/main/STANDARDS.md) - Model contribution guidelines
