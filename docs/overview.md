# Overview

biosim is a modular biological simulation library. It centers around four ideas:

- **BioWorld**: the runtime container that orchestrates multi-rate biomodules, routes signals, and publishes lifecycle events. Supports cooperative pause/resume/stop.
- **BioModule**: a unit of behavior with local state that implements a runnable contract (`setup/reset/advance_to/get_outputs/visualize/...`).
- **BioSignal**: typed data exchanged between modules over named ports. Each signal carries `source`, `name`, `value`, `time`, and optional `metadata` (units, shape, kind, etc.).
- **SimUI**: a lightweight web UI layer for running, visualizing, and editing simulations from the browser, backed by FastAPI + a React SPA.

## Event flow (typical)
- STARTED -> TICK x N -> FINISHED
- PAUSED, RESUMED, STOPPED, and ERROR may be emitted depending on runtime control flow.

## Directed biosignals
- Modules emit outputs via `get_outputs()` (returning `dict[str, BioSignal]`).
- Modules receive inputs via `set_inputs(signals)` when connected.
- Connections are explicit: `world.connect("src.port", "dst.port")` (single target) or via `WiringBuilder.connect("src.port", ["dst1.port", "dst2.port"])` (fan-out).

## Wiring and configuration
- Use `WiringBuilder` in code or load a YAML/TOML file to declare modules and connections.
- Optional port metadata on modules (`inputs()`, `outputs()`) enables connection validation.
- `build_from_spec(world, spec)` builds a module graph from a dict spec (used by YAML/TOML loaders).

## SimUI (web UI)
- Python-declared interface: `Interface(world, controls=[...], outputs=[...]).launch()`.
- REST + SSE API under `/ui/api/...` for run control, real-time events, visuals, and status.
- Config editor sub-API (`/ui/api/editor/...`) for visual wiring editing, YAML import/export, and live reloading.
- Background simulation runner (`SimulationManager`) with pause/resume support.

## Standard-agnostic by design
- Biomodules are self-contained Python packages and may wrap external simulators internally.
- The core focuses on orchestration, wiring contracts, and visualization.

## Beachhead domains
- **Neuroscience**: single neuron + small E/I microcircuits + Hodgkin-Huxley with strong visuals (raster, firing rate, Vm traces) and reproducible configs.
- **Ecology**: predator-prey dynamics, population monitoring, phase-space plots.
- **Brain/Vision**: Eye → LGN → Superior Colliculus sensory pipeline.

Curated model packs and composed spaces live in the companion [`Biosimulant/models`](https://github.com/Biosimulant/models) repo.

## Minimal data example (after wiring Eye -> LGN on port "visual_stream")
- Run: `world.run(duration=0.2, tick_dt=0.1)` to advance the orchestrator and dispatch signals.
