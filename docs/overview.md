# Overview

`biosimulant` is a modular biological simulation library. It centers around four ideas:

- **BioWorld**: the runtime container that orchestrates multi-rate biomodules, routes signals, and publishes lifecycle events. Supports cooperative pause/resume/stop.
- **BioModule**: a unit of behavior with local state that implements the runnable contract (`setup/reset/advance_window/get_outputs/snapshot/restore/...`).
- **BioSignal**: typed data exchanged between modules over named ports. Each signal carries `source`, `name`, `value`, `emitted_at`, and a bound `SignalSpec`.
- **Local Lab UI**: a bundled browser UI for running, visualizing, and editing labs through `biosimulant labs serve`.

`BioModule` is the minimal full-control interface. Authors who want less adapter
boilerplate can opt into `SignalEmitterBioModule` for output wrapping or
`StatefulBioModule` for fixed-step state/history handling. Those subclasses are
helpers, not required architecture.

## Event flow (typical)
- STARTED -> STEP x N -> FINISHED
- PAUSED, RESUMED, STOPPED, and ERROR may be emitted depending on runtime control flow.

## Directed biosignals
- Modules emit outputs via `get_outputs()` (returning `dict[str, BioSignal]`).
- Modules receive inputs via `set_inputs(signals)` when connected.
- Connections are explicit: `world.connect("src.port", "dst.port")` (single target) or via `WiringBuilder.connect("src.port", ["dst1.port", "dst2.port"])` (fan-out).

## Wiring and configuration
- Use `WiringBuilder` in code or load a YAML/TOML file to declare modules and connections.
- Optional port metadata on modules (`inputs()`, `outputs()`) enables connection validation.
- `build_from_spec(world, spec)` builds a module graph from a dict spec (used by YAML/TOML loaders).

## Local Lab UI
- Start with `biosimulant labs serve ./my-lab`.
- The UI is served at `/` and opens by default.
- Lab edits persist to `lab.yaml`; canvas layout persists to `wiring-layout.json`.
- The local API is under `/api/...` and uses in-memory run history for the active server process.

## Standard-agnostic by design
- Biomodules are self-contained Python packages and may wrap external simulators internally.
- The core focuses on orchestration, wiring contracts, and visualization.
- Optional contrib bases such as `biosimulant.contrib.sbml.TelluriumSBMLBioModule`
  keep heavy simulator imports lazy and leave domain-specific visuals or
  payloads in the model wrapper.

## Beachhead domains
- **Neuroscience**: single neuron + small E/I microcircuits + Hodgkin-Huxley with strong visuals (raster, firing rate, Vm traces) and reproducible configs.
- **Ecology**: predator-prey dynamics, population monitoring, phase-space plots.
- **Brain/Vision**: Eye → LGN → Superior Colliculus sensory pipeline.

Curated model packs and composed labs live in the companion [`Biosimulant/models`](https://github.com/Biosimulant/models) repo.

## Minimal data example (after wiring Eye -> LGN on port "visual_stream")
- Run: `world.run(duration=0.2)` to advance the orchestrator and dispatch signals.
