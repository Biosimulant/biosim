# bsim

[![PyPI - Version](https://img.shields.io/pypi/v/bsim.svg)](https://pypi.org/project/bsim)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bsim.svg)](https://pypi.org/project/bsim)

Composable simulation runtime + UI layer for orchestrating simulation components (including adapters to external simulators).

---

## Executive Summary & System Goals

### Vision

Provide a small, stable composition layer for simulations: wire reusable components (“modules”) into a `BioWorld`, run them with an injected `Solver`, and visualize/debug runs via a lightweight web UI (SimUI). Rather than re-implement every domain standard, `bsim` is designed to host adapters that wrap existing simulators and expose them as modules.

### Core Mission

- Compose simulations from reusable, interoperable modules.
- Make “run + visualize + share a config” the default workflow (local-first; hosted later).
- Embrace adapters to existing simulators/standards (SBML/NeuroML/CellML/etc.) via plugins.

### Primary Users

- Developers and researchers who need composable simulation workflows and fast iteration.
- Near-term beachhead: neuroscience demos (single neuron + small E/I microcircuits) with strong visuals and reproducible configs.

---

## Installation

```console
pip install bsim
```

## Examples

- See `examples/` for quick-start scripts. Try:

```bash
pip install -e .
python examples/basic_usage.py
```

### Quick Start: FixedStepBioSolver

`FixedStepBioSolver` extends the fixed-step behavior with configurable bio-quantities and processes (temperature, water, oxygen, etc.). It preserves the same event flow via `BioWorld` (`LOADED → BEFORE_SIMULATION → STEP* → AFTER_SIMULATION`).

Minimal usage:

```python
import bsim

solver = bsim.FixedStepBioSolver(
    temperature=bsim.TemperatureParams(
        initial=300.0,          # Kelvin
        delta_per_step=1.0,     # +1 K per step
        rate_per_time=0.5,      # +0.5 K per second
        bounds=(273.15, 315.15)
    ),
    water=bsim.ScalarRateParams(name="water", initial=1.0, rate_per_time=-0.6, bounds=(0.0, 1.0)),
    oxygen=bsim.ScalarRateParams(name="oxygen", initial=0.3, rate_per_time=-0.2, bounds=(0.0, 1.0)),
)

world = bsim.BioWorld(solver=solver)
result = world.simulate(steps=3, dt=1.0)
print(result)  # {'time': 3.0, 'steps': 3, 'temperature': ..., 'water': ..., 'oxygen': ...}
```

See a fuller demonstration (including a custom process) in:

- `examples/fixed_step_bio_solver.py`

### Visuals from Modules

Modules may optionally expose web-native visuals via `visualize()`, returning a dict or list of dicts with keys `render` and `data`. The world can collect them without any transport layer:

```python
class MyModule(bsim.BioModule):
    def visualize(self):
        return {"render": "timeseries", "data": {"series": [{"name": "s", "points": [[0.0, 1.0]]}]}}

world = bsim.BioWorld(solver=bsim.FixedStepSolver())
world.add_biomodule(MyModule())
world.simulate(steps=1, dt=0.1)
print(world.collect_visuals())  # [{"module": "MyModule", "visuals": [...]}]
```

See `examples/visuals_demo.py` for a minimal end-to-end example.

## SimUI (Python-Declared UI)

SimUI lets you build and launch a small web UI entirely from Python (similar to Gradio's ergonomics), backed by FastAPI and a prebuilt React SPA that renders visuals from JSON. The frontend uses Server-Sent Events (SSE) for real-time updates.

- User usage (no Node/npm required):
  - Install UI extras: `pip install -e '.[ui]'`
  - Try the demo: `python examples/ui_demo.py` then open `http://127.0.0.1:7861/ui/`.
  - From your own code:

    ```python
    from bsim.simui import Interface, Number, Button, EventLog, VisualsPanel
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    ui = Interface(world, controls=[Number("steps", 100), Number("dt", 0.1), Button("Run")], outputs=[EventLog(), VisualsPanel()])
    ui.launch()
    ```

  - The UI provides endpoints under `/ui/api/...`: `spec`, `run`, `status`, `events`, `visuals`.

Per-run resets for clean visuals
- On each `Run`, the backend clears its event buffer and calls `reset()` on modules if they implement it.
- The solver starts from its initial state each run.
- The frontend clears visuals/events before posting `/api/run`.
- To avoid overlapping charts across runs, add `reset()` to modules that accumulate history (e.g., time series points).

- Maintainer flow (building the frontend SPA):
  - Edit the React/Vite app under `src/bsim/simui/_frontend/`.
  - Build via Python: `python -m bsim.simui.build` (requires Node/npm). This writes `src/bsim/simui/static/app.js`.
  - Alternatively: `bash scripts/build_simui_frontend.sh`.
  - Packaging includes `src/bsim/simui/static/**`, so end users never need npm.

- CI packaging (recommended): run the frontend build before `python -m build` so wheels/sdists ship the bundled assets.

Troubleshooting:
- If you see `SimUI static bundle missing at .../static/app.js`, build the frontend with `python -m bsim.simui.build` (requires Node/npm) before launching. End users installing a release wheel won’t see this.

### SimUI Design Notes
- Transport: SSE (Server-Sent Events). The SPA connects to `/api/stream` for real-time updates. Polling endpoints (`/api/status`, `/api/visuals`, `/api/events`) remain available for fallback/debugging.
- Events API: `/api/events?since_id=<int>&limit=<int>` returns `{ events, next_since_id }` where `events` are appended world events and `next_since_id` is the cursor for subsequent calls.
- VisualSpec types supported now:
  - `timeseries`: `data = { "series": [{ "name": str, "points": [[x, y], ...] }, ...] }` (rendered with Plotly lines)
  - `bar`: `data = { "items": [{ "label": str, "value": number }, ...] }`
  - `table`: `data = { "columns": [..], "rows": [[..], ...] }` or `data = { "items": [{...}, ...] }`
  - `image`: `data = { "src": str, "alt"?: str, "width"?: number, "height"?: number }` (use a URL or `data:` URI)
  - `graph`: placeholder renderer shows counts + JSON; richer graph lib can be added later
  - unknown types: rendered as JSON fallback

## Terminology

Understanding the core concepts is essential for working with bsim effectively.

| Term | Description |
|------|-------------|
| **BioWorld** | Runtime container that orchestrates simulation steps, publishes lifecycle events, and routes module-to-module messages (biosignals). |
| **BioModule** | Pluggable unit of behavior with local state. Modules listen to world events, exchange biosignals with peers, and optionally provide visualizations. |
| **Solver** | Execution strategy that drives time-stepping. Calls `emit(event, payload)` to publish events and returns a summary dict when complete. |
| **Process** | State-update strategy used by `FixedStepBioSolver`. Defines `init_state()` and `update(state, dt)` to evolve quantities over time. |
| **Biosignal** | Directed message from one module to another via a named topic. Unlike global events, biosignals are point-to-point between connected modules. |
| **Wiring** | Module connection graph. Defined programmatically, via `WiringBuilder`, or loaded from YAML/TOML configs. |
| **VisualSpec** | JSON structure returned by `module.visualize()` with `render` type and `data` payload. SimUI renders these as charts, tables, images, or graphs. |

### Event Lifecycle

Every simulation follows this sequence:
```
LOADED → BEFORE_SIMULATION → STEP (×N) → AFTER_SIMULATION
```

---

## Solver Types

### FixedStepSolver

The simplest solver—increments time in fixed steps and emits a `STEP` event each iteration.

```python
solver = bsim.FixedStepSolver()
world = bsim.BioWorld(solver=solver)
result = world.simulate(steps=100, dt=0.1)
# result = {'time': 10.0, 'steps': 100}
```

**Use when**: You need basic time-stepping and handle all state in your modules.

### FixedStepBioSolver

Extensible solver with built-in support for biological quantities and custom processes.

```python
solver = bsim.FixedStepBioSolver(
    temperature=bsim.TemperatureParams(initial=300.0, delta_per_step=1.0, rate_per_time=0.5, bounds=(273.15, 315.15)),
    water=bsim.ScalarRateParams(name="water", initial=1.0, rate_per_time=-0.6, bounds=(0.0, 1.0)),
    oxygen=bsim.ScalarRateParams(name="oxygen", initial=0.3, rate_per_time=-0.2, bounds=(0.0, 1.0)),
)
```

**Use when**: You need solver-managed state for common biological quantities.

### Custom Solver

Subclass `bsim.Solver` for custom execution strategies:

```python
class MySolver(bsim.Solver):
    def simulate(self, *, steps: int, dt: float, emit) -> dict:
        t = 0.0
        for i in range(steps):
            t += dt
            emit(bsim.BioWorldEvent.STEP, {"i": i, "t": t})
        return {"time": t, "steps": steps}
```

### Custom Process

Extend `FixedStepBioSolver` with domain-specific state evolution:

```python
from bsim.solver import Process

class GlucoseProcess(Process):
    def __init__(self, initial=5.0, rate=0.05):
        self.initial = initial
        self.rate = rate

    def init_state(self):
        return {"glucose": self.initial}

    def update(self, state, dt):
        current = state.get("glucose", self.initial)
        return {"glucose": current - self.rate * dt}

solver = bsim.FixedStepBioSolver(processes=[GlucoseProcess()])
```

---

## Real-Time Streaming (SSE)

SimUI supports Server-Sent Events for real-time updates alongside the polling API.

### SSE Endpoint

Connect to `/api/stream` for a persistent event stream:

```javascript
const eventSource = new EventSource('/api/stream');
eventSource.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    // msg.type: 'snapshot' | 'tick' | 'event' | 'heartbeat'
    console.log(msg.type, msg.data);
};
```

### Message Types

| Type | Payload | Description |
|------|---------|-------------|
| `snapshot` | `{ status, visuals, events[] }` | Initial full state on connection |
| `tick` | `{ status, visuals, event }` | Sent on each simulation step |
| `event` | `{ id, ts, event, payload }` | World event record |
| `heartbeat` | `{ status }` | Keepalive signal (2s idle timeout) |

### SSE vs Polling

| Aspect | SSE (`/api/stream`) | Polling (`/api/status`) |
|--------|---------------------|-------------------------|
| Latency | Real-time (~50ms) | Polling interval |
| Connection | Persistent | Request/response |
| Use case | Live dashboards | Simple integrations |

---

## Using bsim in Custom Simulations

### Creating a Custom Module

```python
class SensorModule(bsim.BioModule):
    def __init__(self):
        self.readings = []

    def subscriptions(self):
        return {bsim.BioWorldEvent.STEP}

    def outputs(self):
        return {"reading"}

    def on_event(self, event, payload, world):
        if event == bsim.BioWorldEvent.STEP:
            value = payload.get("t", 0) * 0.1
            self.readings.append(value)
            world.publish_biosignal(self, "reading", {"value": value})

    def visualize(self):
        return {"render": "timeseries", "data": {"series": [{"name": "sensor", "points": [[i, v] for i, v in enumerate(self.readings)]}]}}

    def reset(self):
        self.readings = []
```

### Wiring Modules

**Programmatic**:
```python
world.add_biomodule(sensor)
world.add_biomodule(processor)
world.connect_biomodules(sensor, "reading", processor)
```

**Declarative (WiringBuilder)**:
```python
from bsim import WiringBuilder
wb = WiringBuilder(world)
wb.add("sensor", SensorModule())
wb.add("processor", ProcessorModule())
wb.connect("sensor.reading", ["processor"])
wb.apply()
```

**YAML config**:
```yaml
modules:
  sensor:
    class: mypackage.SensorModule
  processor:
    class: mypackage.ProcessorModule
wiring:
  - from: sensor.out.reading
    to: [processor]
```

### Domain Packs

**Neuroscience** (`bsim.packs.neuro`): `PoissonInput`, `StepCurrent`, `IzhikevichPopulation`, `SpikeMonitor`, `RateMonitor`

**Ecology** (`bsim.packs.ecology`): `Environment`, `OrganismPopulation`, `PredatorPreyInteraction`, `PopulationMonitor`

See `examples/neuro_simui_demo.py` and `examples/ecology_simui_demo.py` for demos.

---

## API Reference

### TemperatureParams

- initial: float — starting temperature value.
- delta_per_step: float — additive change applied each simulation step.
- rate_per_time: float — rate-based change per unit time (multiplied by `dt`).
- bounds: tuple[float, float] | None — optional `(min, max)` clamp.

Example:

```python
bsim.TemperatureParams(initial=300.0, delta_per_step=1.0, rate_per_time=0.5, bounds=(273.15, 315.15))
```

### ScalarRateParams

- name: str — quantity name (e.g., "water", "oxygen").
- initial: float — starting value for the quantity.
- rate_per_time: float — change per unit time (value += rate_per_time * dt).
- bounds: tuple[float, float] | None — optional `(min, max)` clamp.

Example:

```python
bsim.ScalarRateParams(name="water", initial=1.0, rate_per_time=-0.6, bounds=(0.0, 1.0))
```

## License

`bsim` is distributed under the terms of the [MIT](https://spdx.org/licenses/MIT.html) license.
