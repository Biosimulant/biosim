# Overview

bsim is a modular biological simulation library. It centers around three ideas:

- BioWorld: the runtime container that orchestrates simulation steps, publishes lifecycle events, and routes directed module-to-module messages (biosignals).
- BioModule: a unit of behavior with local state that can listen to global world events (e.g., STEP) and exchange directed biosignals with specific peers.
- Solver: an execution strategy injected into the world that drives time-stepping and emits events (e.g., STEP) to listeners.

Event flow (typical)
- LOADED (once) → BEFORE_SIMULATION → STEP × N → AFTER_SIMULATION
- Errors in listeners/signal handlers are logged and do not stop the world.

Directed biosignals
- Modules publish via `world.publish_biosignal(self, topic, payload)`.
- Connections are explicit: `world.connect_biomodules(src, topic, dst)`.
- Only connected modules receive a given topic from a specific source.

Wiring and configuration
- Use `WiringBuilder` in code or load a YAML/TOML file to declare modules and connections.
- Optional port metadata on modules (`inputs()`, `outputs()`) enables connection validation.

Minimal data examples (after wiring Eye → LGN on topic "visual_stream")
- `world.describe_wiring()` → `[('Eye', 'visual_stream', 'LGN')]`
- After `world.simulate(steps=2, dt=0.1)` with `FixedStepSolver`, result → `{ 'steps': 2, 'time': 0.2 }`
