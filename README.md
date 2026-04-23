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

For the shared ONNX biomodule helpers:

```console
pip install "biosim[ml]"
```

## Publishing to PyPI

See the release guide: [`docs/releasing.md`](docs/releasing.md).

## Packaging Models And Spaces

`biosim` can package one model or one space into a single archive for portability, upload, caching, and validation.

Common commands:

```bash
# Build a package from a directory that contains model.yaml or space.yaml
python -m biosim pack build path/to/model-or-space

# Validate an existing package file
python -m biosim pack validate dist/local__counter-1.0.0.bsimpkg

# Build a self-contained space package (.bsispace)
python -m biosim pack build path/to/space
```

Notes:
- `build` prefers `package:` and `version:` from `model.yaml` or `space.yaml` when present.
- model dependencies in manifests must use exact `==` pins.
- space builds are always self-contained and preserve the full runnable source tree inside the `.bsispace`.
- nested space dependencies must use relative `path` refs and must already exist inside the packaged space directory.
- `validate` prints human-readable success or failure output by default; add `--json` for machine-readable output.

See [`docs/packaging.md`](docs/packaging.md) for the full package layout, recommended authoring flow, and CLI examples.

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
from biosim import ScalarSignal, SignalSpec


class Counter(biosim.BioModule):
    def __init__(self):
        self.value = 0
        self._t = 0.0

    def outputs(self):
        return {"count": SignalSpec.scalar(dtype="int64", emitted_unit="1")}

    def advance_window(self, start: float, end: float) -> None:
        _ = start
        self.value += 1
        self._t = end

    def get_outputs(self):
        return {
            "count": ScalarSignal(
                source="counter",
                name="count",
                value=self.value,
                emitted_at=self._t,
                spec=self.outputs()["count"],
            )
        }

    def snapshot(self) -> dict:
        return {"value": self.value, "t": self._t}

    def restore(self, snapshot: dict) -> None:
        self.value = int(snapshot.get("value", 0))
        self._t = float(snapshot.get("t", 0.0))


world = biosim.BioWorld(communication_step=0.1)
world.add_biomodule("counter", Counter())
world.run(duration=1.0, tick_dt=0.1)
```

### Visuals from Modules

Modules may optionally expose visuals via `visualize()`, returning a dict or list of dicts with keys `render` and `data`. The world can collect them without any transport layer:

```python
class MyModule(biosim.BioModule):
    def advance_window(self, start: float, end: float) -> None:
        _ = start, end

    def get_outputs(self):
        return {}

    def snapshot(self) -> dict:
        return {}

    def restore(self, snapshot: dict) -> None:
        _ = snapshot

    def visualize(self):
        return {
            "render": "timeseries",
            "data": {"series": [{"name": "s", "points": [[0.0, 1.0]]}]},
        }

world = biosim.BioWorld(communication_step=0.1)
world.add_biomodule("module", MyModule())
world.run(duration=0.1, tick_dt=0.1)
print(world.collect_visuals())  # [{"module": "module", "visuals": [...]}]
```

See `examples/visuals_demo.py` for a minimal end-to-end example.

### ONNX Modules

`biosim` can host ONNX-backed modules without changing the core runtime. Install
the ML extras and wrap the ONNX model behind the standard `BioModule`
interface:

```python
from biosim import OnnxClassifierModule, ScalarSignal, SignalSpec

classifier = OnnxClassifierModule(
    model_path="artifacts/model.onnx",
    class_labels=["quiescent", "subthreshold", "spiking"],
    input_port="state_vector",
    probabilities_port="state_probabilities",
    predicted_port="predicted_state",
    input_vector_length=4,
)

classifier.set_inputs(
    {
        "state_vector": ScalarSignal(
            source="adapter",
            name="state_vector",
            value=-64.0,
            emitted_at=0.0,
            spec=SignalSpec.scalar(dtype="float64"),
        )
    }
)
classifier.advance_window(0.0, 0.001)
print(classifier.get_outputs()["predicted_state"].value)
```

Model packs can subclass `OnnxClassifierModule` to set model-relative
`model_path`, port names, and label sets while keeping the inference logic in
the shared library.

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
    - `GET /api/status` – Runner status (running/paused/error + optional progress fields)
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
- Objective progress fields are based on simulation-time progress (`(sim_time - sim_start) / duration`), not wall-clock time.
- `/api/status` may include: `sim_time`, `sim_start`, `sim_end`, `sim_remaining`, `progress`, `progress_pct` (all optional/additive).
- Events API: `/api/events?since_id=<int>&limit=<int>` returns `{ events, next_since_id }` where `events` are appended world events and `next_since_id` is the cursor for subsequent calls.
- VisualSpec types supported now:
  - `timeseries`: `data = { "series": [{ "name": str, "points": [[x, y], ...] }, ...] }`
  - `bar`: `data = { "items": [{ "label": str, "value": number }, ...] }`
  - `scatter`: `data = { "points": [{ "x": number, "y": number, "label"?: str, "series"?: str }, ...] }`
  - `heatmap`: `data = { "values": [[number, ...], ...], "x_labels"?: [str, ...], "y_labels"?: [str, ...] }`
  - `table`: `data = { "columns": [..], "rows": [[..], ...] }` or `data = { "items": [{...}, ...] }`
  - `image`: `data = { "src": str, "alt"?: str, "width"?: number, "height"?: number }`
  - `graph`: simple node-edge graph renderer
  - `structure3d`: `data = { "title"?: str, "source": { "kind": "url", "url": str } | { "kind": "artifact", "artifact_id": str }, "format": "mmcif" | "pdb", "annotations"?: [{ "label": str, "value": str|number|bool }], "initial_view"?: {...} }`
- VisualSpec may also include an optional `description` (string) for hover text or captions.
- SimUI serves artifact-backed `structure3d` files through `/api/artifacts/{artifact_id}` so browser clients do not receive raw local filesystem paths.

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
