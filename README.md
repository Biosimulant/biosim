# biosimulant

[![PyPI - Version](https://img.shields.io/pypi/v/biosimulant.svg)](https://pypi.org/project/biosimulant)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/biosimulant.svg)](https://pypi.org/project/biosimulant)

Composable simulation runtime + UI layer for orchestrating runnable biomodules.

`biosimulant` is the primary package, import namespace, and CLI name. The
existing `biosim` Python import path and `python -m biosim` command remain
supported for existing model packages during the migration.

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
pip install "biosimulant @ git+https://github.com/<org>/biosim.git@<ref>"
```

Alternative (package index):

```console
pip install biosimulant
```

For the shared ONNX biomodule helpers:

```console
pip install "biosimulant[ml]"
```

### Compatibility and command ownership

Use `biosimulant` for new Python examples:

```python
import biosimulant as biosim
```

The package still ships the legacy `biosim` Python import path so existing model
packages keep working:

```python
import biosim
```

Use `biosimulant` for new CLI examples:

```bash
biosimulant --help
python -m biosimulant --help
```

`python -m biosim` remains available as a compatibility command. If a machine
also has the Desktop/product CLI installed, `PATH` decides which `biosimulant`
binary runs. Use `python -m biosimulant ...` to force the Python package CLI.
The Python package owns local open-source workflows; Desktop/product extensions
own Hub, auth, cloud, app state, and managed-service workflows.

### Shell completion

`biosimulant` supports bash and zsh completion for commands, options, and file
paths. Add the completion hook once to your shell startup file:

```bash
# ~/.zshrc or ~/.bashrc
eval "$(register-python-argcomplete biosimulant)"
```

Then restart the shell, or run `source ~/.zshrc` / `source ~/.bashrc`.

## Publishing to PyPI

See the release guide: [`docs/releasing.md`](docs/releasing.md).

## Local Labs

The open-source Python CLI can create, manage, validate, run, and serve local
lab source trees without Desktop or Hub:

```bash
biosimulant labs create ./my-lab --name "My Lab"
biosimulant labs list .
biosimulant labs get ./my-lab
biosimulant labs package ./my-lab --out dist
biosimulant labs validate ./my-lab
biosimulant labs run ./my-lab --no-install-deps
biosimulant labs serve ./my-lab
```

`labs init` creates a runnable starter lab by default. Use `--empty` when you
want only a bare `lab.yaml` scaffold.
Managed local lab identity lives in `.biosimulant/lab.json`; exported labs use
the portable `lab.yaml` source manifest.

## Packaging Models And Labs

`biosimulant` packages labs through the `labs` command group. Standalone model
package helpers remain Python APIs, but the public CLI object is the lab.

Common commands:

```bash
# Validate and build a package repository manifest
biosimulant labs release validate biosimulant-packages.yaml
biosimulant labs release build biosimulant-packages.yaml --out dist/biosimulant-packages

# Build a self-contained lab package (.bsilab)
biosimulant labs package path/to/lab --out dist

# Discover and pull public registry labs
biosimulant labs search immune
biosimulant labs info owner/lab-name@1.0.0
biosimulant labs pull owner/lab-name@1.0.0 --target ./labs/lab-name

# Validate or run a lab source tree or .bsilab
biosimulant labs validate path/to/lab
biosimulant labs run dist/local__source-lab-1.0.0.bsilab --no-install-deps
```

Notes:
- local `labs validate`, `labs run`, and `labs serve` can use source labs without `package:` or `version:`; the CLI assigns a transient `local/<lab-directory-slug>` identity for local execution.
- standalone `labs package` builds require `package:` and `version:` in `lab.yaml`, or explicit `--package` and `--version` values. Release manifests can supply identity through `biosimulant-packages.yaml`.
- model dependencies in manifests must use exact `==` pins.
- lab builds are always self-contained and preserve the full runnable source tree inside the `.bsilab`.
- nested lab dependencies must use relative `path` refs and must already exist inside the packaged lab directory.
- `validate` prints human-readable success or failure output by default; add `--json` for machine-readable output.

See [`docs/packaging.md`](docs/packaging.md) for the full package layout, recommended authoring flow, and CLI examples.

## Provisional Runtime Helpers

`biosimulant.runtime` is the provisional public home for package interpretation helpers shared by the open-source CLI and Biosimulant platform executors. It owns entrypoint loading, typed `runtime.initial_inputs` coercion, communication-step resolution, and source-neutral lab flattening. Import these helpers from `biosimulant.runtime`; the legacy `biosim.runtime` path remains available for compatibility.

## BioModule Convenience Layers

`BioModule` remains the minimal full-control runtime contract. For common model
adapters, `biosimulant` also exports opt-in helpers:

- `SignalEmitterBioModule`: output storage, source-name resolution, and raw
  value to typed `BioSignal` wrapping.
- `StatefulBioModule`: fixed-step window advancement, input override storage,
  bounded history, and output publishing hooks.

Signal helper functions are available from `biosimulant.signals` and top-level
`biosimulant`: `unwrap_payload`, `coerce_float`, `scalar_or_record_input`, and
`make_signal`.

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
import biosimulant as biosim
from biosimulant import ScalarSignal, SignalSpec


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
world.run(duration=1.0)
```

Outputs produced during a communication window are committed at the end of that
window and become visible to downstream modules on a later communication turn.
For final report, export, or visualisation modules in workflow-style graphs, call
`world.settle(steps=1)` after `world.run(...)` to propagate final outputs without
advancing simulated time.

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
world.run(duration=0.1)
print(world.collect_visuals())  # [{"module": "module", "visuals": [...]}]
```

If visuals are generated by a separate downstream module wired to another
producer's final outputs, run one or more settle turns before collecting visuals:
`world.run(duration=...); world.settle(1); world.collect_visuals()`.

See `examples/visuals_demo.py` for a minimal end-to-end example.

### ONNX Modules

`biosimulant` can host ONNX-backed modules without changing the core runtime. Install
the ML extras and wrap the ONNX model behind the standard `BioModule`
interface:

```python
from biosimulant import OnnxClassifierModule, ScalarSignal, SignalSpec

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
  - Install UI extras: `pip install 'biosimulant[ui]'`
  - Try the demo: `python examples/ui_demo.py` then open `http://127.0.0.1:7860/ui/`.
  - From your own code:

    ```python
    import biosimulant as biosim
    from biosimulant.simui import Interface, Number, Button, EventLog, VisualsPanel

    world = biosim.BioWorld(communication_step=0.1)
    ui = Interface(
        world,
        controls=[Number("duration", 10), Button("Run")],
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
  - Build via Python: `python -m biosimulant.simui.build` (requires Node/npm). This writes `src/biosim/simui/static/app.js`.
  - Alternatively: `bash scripts/build_simui_frontend.sh`.
  - Packaging includes `src/biosim/simui/static/**`, so end users never need npm.

- CI packaging (recommended): run the frontend build before `python -m build` so wheels/sdists ship the bundled assets.

Troubleshooting:
- If you see `SimUI static bundle missing at .../static/app.js`, build the frontend with `python -m biosimulant.simui.build` (requires Node/npm) before launching. End users installing a release wheel won't see this.

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

Understanding the core concepts is essential for working with Biosimulant effectively.

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
