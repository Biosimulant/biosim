# biosim

[![PyPI - Version](https://img.shields.io/pypi/v/biosim.svg)](https://pypi.org/project/biosim)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/biosim.svg)](https://pypi.org/project/biosim)

Composable simulation runtime + UI layer for orchestrating runnable biomodules.

---

## Executive Summary & System Goals

### Vision

Provide a small, stable composition layer for simulations: wire reusable components ("biomodules") into a `BioWorld`, run them with a single orchestration contract, and visualize/debug runs via a lightweight web UI (SimUI). Biomodules are self-contained Python packages that can wrap external simulators internally (SBML/NeuroML/CellML/etc.) without a separate adapter layer.

### Core Mission

- Compose simulations from reusable, interoperable biomodules.
- Make "run + visualize + share a config" the default workflow (local-first; hosted later).
- Keep the runtime small and predictable while letting biomodules embed their own simulator/tooling.

### Primary Users

- Developers and researchers who need composable simulation workflows and fast iteration.
- Near-term beachhead: neuroscience demos (single neuron + small E/I microcircuits) with strong visuals and reproducible configs.

---

## Installation

Preferred (pinned GitHub ref):

```console
pip install "biosim @ git+https://github.com/<org>/biosim.git@<ref>"
```

Alternative (package index):

```console
pip install biosim
```

## Examples

- See `examples/` for quick-start scripts. Try:

```bash
pip install -e .
python examples/basic_usage.py
```

For advanced curated demos (neuro/ecology), wiring configs, and model-pack templates, see the companion repo:

- https://github.com/Biosimulant/models

### Quick Start: BioWorld

Minimal usage:

```python
import biosim
from biosim import BioSignal, SignalMetadata

class Counter(biosim.BioModule):
    min_dt = 0.1

    def __init__(self):
        self.value = 0

    def reset(self) -> None:
        self.value = 0

    def advance_to(self, t: float) -> None:
        self.value += 1

    def get_outputs(self):
        source = getattr(self, "_world_name", "counter")
        return {
            "count": BioSignal(
                source=source,
                name="count",
                value=self.value,
                time=0.0,
                metadata=SignalMetadata(units="1", description="tick counter"),
            )
        }

world = biosim.BioWorld()
world.add_biomodule("counter", Counter())
world.run(duration=1.0, tick_dt=0.1)
```

### Visuals from Modules

Modules may optionally expose web-native visuals via `visualize()`, returning a dict or list of dicts with keys `render` and `data`. The world can collect them without any transport layer:

```python
class MyModule(biosim.BioModule):
    min_dt = 0.1

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        return {}

    def visualize(self):
        return {
            "render": "timeseries",
            "data": {"series": [{"name": "s", "points": [[0.0, 1.0]]}]},
        }

world = biosim.BioWorld()
world.add_biomodule("module", MyModule())
world.run(duration=0.1, tick_dt=0.1)
print(world.collect_visuals())  # [{"module": "module", "visuals": [...]}]
```

See `examples/visuals_demo.py` for a minimal end-to-end example.

## SimUI (Python-Declared UI)

SimUI lets you build and launch a small web UI entirely from Python (similar to Gradio's ergonomics), backed by FastAPI and a prebuilt React SPA that renders visuals from JSON. The frontend uses Server-Sent Events (SSE) for real-time updates.

- User usage (no Node/npm required):
  - Install UI extras: `pip install -e '.[ui]'`
  - Try the demo: `python examples/ui_demo.py` then open `http://127.0.0.1:7860/ui/`.
  - From your own code:

    ```python
    from biosim.simui import Interface, Number, Button, EventLog, VisualsPanel
    world = biosim.BioWorld()
    ui = Interface(
        world,
        controls=[Number("duration", 10), Number("tick_dt", 0.1), Button("Run")],
        outputs=[EventLog(), VisualsPanel()],
    )
    ui.launch()
    ```

  - The UI provides endpoints under `/ui/api/...`:
    - `GET /api/spec` – UI layout (controls, outputs, modules)
    - `POST /api/run` – Start a simulation run
    - `GET /api/status` – Runner status (running/paused/error)
    - `GET /api/state` – Full state (status + last step + modules)
    - `GET /api/events` – Buffered world events (`?since_id=&limit=`)
    - `GET /api/visuals` – Collected module visuals
    - `GET /api/snapshot` – Full snapshot (status + visuals + events)
    - `GET /api/stream` – SSE endpoint for real-time event streaming
    - `POST /api/pause` – Pause running simulation
    - `POST /api/resume` – Resume paused simulation
    - `POST /api/reset` – Stop, reset, and clear buffers
    - **Editor sub-API** (`/api/editor/...`): visual config editor for loading, saving, validating, and applying YAML wiring configs as node graphs. Endpoints include `modules`, `current`, `config`, `apply`, `validate`, `layout`, `to-yaml`, `from-yaml`, and `files`.

Per-run resets for clean visuals
- On each `Run`, the backend clears its event buffer and calls `reset()` on modules if they implement it.
- The frontend clears visuals/events before posting `/api/run`.
- To avoid overlapping charts across runs, add `reset()` to modules that accumulate history (e.g., time series points).

- Maintainer flow (building the frontend SPA):
  - Edit the React/Vite app under `src/biosim/simui/_frontend/`.
  - Build via Python: `python -m biosim.simui.build` (requires Node/npm). This writes `src/biosim/simui/static/app.js`.
  - Alternatively: `bash scripts/build_simui_frontend.sh`.
  - Packaging includes `src/biosim/simui/static/**`, so end users never need npm.

- CI packaging (recommended): run the frontend build before `python -m build` so wheels/sdists ship the bundled assets.

Troubleshooting:
- If you see `SimUI static bundle missing at .../static/app.js`, build the frontend with `python -m biosim.simui.build` (requires Node/npm) before launching. End users installing a release wheel won't see this.

### SimUI Design Notes
- Transport: SSE (Server-Sent Events). The SPA connects to `/api/stream` for real-time updates. Polling endpoints (`/api/status`, `/api/visuals`, `/api/events`) remain available for fallback/debugging.
- Events API: `/api/events?since_id=<int>&limit=<int>` returns `{ events, next_since_id }` where `events` are appended world events and `next_since_id` is the cursor for subsequent calls.
- VisualSpec types supported now:
  - `timeseries`: `data = { "series": [{ "name": str, "points": [[x, y], ...] }, ...] }`
  - `bar`: `data = { "items": [{ "label": str, "value": number }, ...] }`
  - `table`: `data = { "columns": [..], "rows": [[..], ...] }` or `data = { "items": [{...}, ...] }`
  - `image`: `data = { "src": str, "alt"?: str, "width"?: number, "height"?: number }`
  - `scatter`: scatter plot data
  - `heatmap`: matrix/heatmap data
  - `graph`: placeholder renderer shows counts + JSON; richer graph lib can be added later
  - `custom:<type>`: custom renderer namespace for user-defined types
  - unknown types: rendered as JSON fallback
- VisualSpec may also include an optional `description` (string) for hover text or captions.

## Terminology

Understanding the core concepts is essential for working with biosim effectively.

| Term | Description |
|------|-------------|
| **BioWorld** | Runtime container that orchestrates multi-rate biomodules, routes signals, and publishes lifecycle events. |
| **BioModule** | Pluggable unit of behavior with local state. Implements the runnable contract (`setup/reset/advance_to/...`). |
| **BioSignal** | Typed, versioned data payload exchanged between modules via named ports. |
| **WorldEvent** | Runtime events emitted by the BioWorld (`STARTED`, `TICK`, `FINISHED`, etc.). |
| **Wiring** | Module connection graph. Defined programmatically, via `WiringBuilder`, or loaded from YAML/TOML configs. |
| **VisualSpec** | JSON structure returned by `module.visualize()` with `render` type and `data` payload. |

### Event Lifecycle

Every simulation follows this sequence:
```
STARTED -> TICK (xN) -> FINISHED
```

`PAUSED`, `RESUMED`, `STOPPED`, and `ERROR` may also be emitted depending on runtime control flow.

## License

MIT. See `LICENSE.txt`.
