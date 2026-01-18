# B-Simulant Audit (bsim)

This is a point-in-time audit of the current `B-Simulant` repo state, focused on:
- what exists today (code, docs, tests, examples, tooling),
- what’s left relative to `BUSINESS_CASE.md`,
- what’s suboptimal / inconsistent, and what to change next.

## Snapshot

- Core library lives in `src/bsim/` and provides a small but coherent simulation runtime (`BioWorld`), solver interface + implementations, a module abstraction (`BioModule`), wiring (code + YAML/TOML loaders), and a minimal visualization contract.
- A lightweight web UI (“SimUI”) exists under `src/bsim/simui/`, backed by FastAPI and a prebuilt frontend bundle shipped as static assets.
- Tests exist and cover most current public behaviors (events, biosignals, wiring validation, visuals normalization, FixedStepBioSolver, SimUI spec endpoints).

## Git working state (what’s staged right now)

At the time of writing, `git status` shows a large staged set including (non-exhaustive):
- new CI workflow (`.github/workflows/ci.yml`)
- SimUI package + frontend sources + static bundle (`src/bsim/simui/**`)
- SimUI demos (`examples/ui_demo.py`, `examples/multi_module_ui_demo.py`)
- Business case doc (`BUSINESS_CASE.md`)
- small updates across `README.md`, `docs/quickstart.md`, `pyproject.toml`, `src/bsim/__init__.py`, `src/bsim/world.py`

## What’s been done so far (what exists)

### Core runtime (events, modules, signals)

- `BioWorld` (`src/bsim/world.py`)
  - Lifecycle events: `LOADED`, `BEFORE_SIMULATION`, `STEP`, `AFTER_SIMULATION`, plus `ERROR` and `PAUSED` (`BioWorldEvent`).
  - Listener model: `world.on(listener)` / `world.off(listener)`.
  - `BioModule` auto-subscription via `world.add_biomodule(module)` with opt-in filtering via `module.subscriptions()`.
  - Directed module-to-module messaging (“biosignals”): explicit connections via `connect_biomodules(src, topic, dst)` and delivery via `publish_biosignal(...)`.
  - Best-effort robustness: exceptions in `BioModule.on_event` / `BioModule.on_signal` are logged and do not crash the simulation loop.

- `BioModule` base interface (`src/bsim/modules.py`)
  - `on_event(...)` + optional `on_signal(...)`.
  - Optional port metadata for validation: `inputs()` / `outputs()` (schemas present but currently unused).
  - Optional `visualize()` hook returning `VisualSpec`(s).

### Solvers

- `Solver` ABC (`src/bsim/solver.py`)
  - `simulate(*, steps, dt, emit)` keyword-only contract.
- `FixedStepSolver` (`src/bsim/solver.py`)
  - Emits a `STEP` event per iteration and returns `{time, steps}`.
- `FixedStepBioSolver` (`src/bsim/solver.py`)
  - A “process” concept (`Process.update(state, dt) -> patch`) with built-in processes:
    - temperature (`TemperatureParams`)
    - generic scalar rates (`ScalarRateParams`) used for water/oxygen and arbitrary quantities
  - Returns `{time, steps, ...state}`.

### Wiring and declarative configuration

- `WiringBuilder` (`src/bsim/wiring.py`)
  - Registers modules by name and applies pending connections.
  - Validates connections against declared `inputs()`/`outputs()` when present.
- Spec + loader support (`src/bsim/wiring.py`)
  - `build_from_spec(world, spec)` supports `modules` and `wiring` sections.
  - `load_wiring_*` supports YAML (`pyyaml`) and TOML (`tomllib` or `tomli` fallback).

### Visuals contract

- `VisualSpec` + helpers (`src/bsim/visuals.py`)
  - Simple schema: `{ "render": str, "data": dict }`
  - `validate_visual_spec(...)` and `normalize_visuals(...)` to filter bad entries.
- World collection (`src/bsim/world.py`)
  - `world.collect_visuals()` aggregates module visuals using `normalize_visuals`.

### SimUI (web UI)

- Python interface + API (`src/bsim/simui/interface.py`)
  - FastAPI router serving:
    - `/api/spec`, `/api/run`, `/api/status`, `/api/events`, `/api/visuals`, `/api/snapshot`, `/api/reset`, `/api/pause`, `/api/resume`
    - `/api/stream` — SSE endpoint for real-time updates (snapshot, tick, event, heartbeat messages)
  - SSE transport (primary) with polling endpoints available for fallback.
  - Bundled static frontend served from `src/bsim/simui/static/`.
  - Convenience `Interface.launch()` starts uvicorn.
- Background runner (`src/bsim/simui/runner.py`)
  - Runs `world.simulate(...)` in a background thread.
  - Tracks `running/paused/step_count/error` for status queries and SSE broadcasts.
- Frontend source (maintainers) (`src/bsim/simui/_frontend/`)
  - Vite + React + TypeScript app; build copies `dist/app.js` to `src/bsim/simui/static/app.js`.
  - Build helpers:
    - `python -m bsim.simui.build` (`src/bsim/simui/build.py`)
    - `bash scripts/build_simui_frontend.sh`

### Public API surface

- `bsim` exports are centralized in `src/bsim/__init__.py` via `__all__`.

### Docs, examples, tests, CI

- Docs exist in `docs/` (overview, quickstart, wiring, solver, etc.).
- Examples exist in `examples/` (basic usage, world simulation, visuals demo, wiring builder demo, FixedStepBioSolver demo, SimUI demos).
- Tests exist in `tests/` (pytest) and cover the current primitives, including SimUI spec behavior.
- GitHub Actions CI exists in `.github/workflows/ci.yml` and runs `pip install -e '.[dev,ui]'` then `pytest`, plus a package build job.

## What was verified during this audit

- `PYTHONPATH=src .venv/bin/python -c "import bsim; ..."` works in the current checkout.
- `PYTHONPATH=src .venv/bin/python -m pytest -q` passes (25 tests).
- `PYTHONPATH=src .venv/bin/python examples/basic_usage.py` and `PYTHONPATH=src .venv/bin/python examples/world_simulation.py` run successfully.

Note: `.venv/bin/pytest` fails in this checkout due to a stale shebang (venv created in a different absolute path). Running `python -m pytest` avoids this.

## What’s left (gaps vs `BUSINESS_CASE.md`)

The current library covers the Phase 1 “core engine” shape, but many items in the business case remain conceptual/planned:

- Adaptive solver: only fixed-step exists today (`FixedStepSolver` / `FixedStepBioSolver`).
- Richer modeling primitives: no built-in domain modules yet (molecular dynamics, CA, metabolic, neural, population, PK/PD).
- Plugin SDK: no plugin discovery mechanism (e.g., entry points), versioned plugin contracts, or compatibility tooling.
- Standards compliance: no SBML/CellML import/export or interoperability layer.
- “Hybrid execution”: no distributed execution model, batching, scheduling, or persistence layer.
- Web platform (beyond SimUI): no users/projects, storage, export, collaboration, or API auth.
- SimUI component breadth: only `Number`, `Button`, `EventLog`, `VisualsPanel` are present; no sliders, sweeps, batch controls, run history, exports.
- Deeper wiring/config UX: loaders exist, but there’s no versioned schema, no module registry, no security model, and no CLI to run wiring files.

## Suboptimal or inconsistent areas (recommended changes)

### 1) Python version support is inconsistent with the code

- `pyproject.toml` advertises `requires-python = ">=3.8"` and includes 3.8/3.9 classifiers.
- The code uses Python 3.10+ syntax (`X | Y` unions, `list[str]`, etc.), which will not parse on Python 3.8/3.9.

Recommendation:
- Either raise `requires-python` and classifiers to match reality (likely `>=3.10` or `>=3.11`), or refactor typing syntax to be 3.8-compatible (replace `|` unions with `typing.Union`, avoid `list[str]`, etc.).

### 2) Optional dependency boundaries are currently leaky (high impact)

- `src/bsim/__init__.py` imports and re-exports `simui`, and `bsim.simui` imports FastAPI at import time.
- This effectively makes `fastapi` a hard dependency for `import bsim`, even though UI deps are declared as optional (`.[ui]`) and `project.dependencies` is empty.

Recommendation:
- Make `bsim.simui` import lazy/optional from the top-level `bsim` namespace:
  - avoid importing `simui` in `bsim/__init__.py`, or
  - wrap it in `try/except ImportError` and expose a clear error message when accessed without UI extras.
- Adjust tests so the base package can be imported without `fastapi` installed.

### 3) Cooperative stop looks broken (and likely breaks SimUI reset semantics)

- `BioWorld._emit(...)` raises `SimulationStop` whenever `_stop_requested` is set.
- `BioWorld.simulate(...)` catches `SimulationStop` around `solver.simulate(...)`, but the `finally` block always calls `_emit(AFTER_SIMULATION, ...)`, which will also raise `SimulationStop` and escape.

Why this matters:
- A stop request during a run likely turns into an exception after the solver exits, which can surface as an “error” in `SimulationManager` instead of a clean stop/reset.

Recommendation:
- Rework stop semantics so a stop request cleanly ends a run while still allowing `AFTER_SIMULATION` emission (e.g., only raise `SimulationStop` on `STEP`, or catch `SimulationStop` around the `AFTER_SIMULATION` emission).

### 4) Docs and repo “truth” are out of sync in a few places

- Historical drift note: the SimUI frontend is React/Vite (`src/bsim/simui/_frontend/`), and docs/CI should reflect that consistently.
- `docs/README.md` references `scripts/build_pdf.sh`, but that script does not exist.
- `docs/quickstart.md` references a `bsim-run` CLI, but no such console script exists in `pyproject.toml`.

Recommendation:
- Choose the source of truth (React vs Svelte; CLI vs no CLI) and align `AGENTS.md`, docs, and CI job text accordingly.
- Either implement `bsim-run` (preferred if declarative wiring is meant to be first-class) or remove it from the docs.
- Remove or add `scripts/build_pdf.sh` to match `docs/README.md`.

### 5) Dependency declaration could be clearer

- `project.dependencies = []`, but features rely on optional packages:
  - YAML wiring needs `pyyaml`
  - TOML wiring needs `tomli` on Python <3.11
  - SimUI needs `fastapi`, `uvicorn`
- UI extra currently includes `jinja2`, but the current SimUI implementation doesn’t use it.

Recommendation:
- Consider dedicated extras: `config` (pyyaml/tomli), `ui` (fastapi/uvicorn), `dev` (pytest, etc.).
- Drop unused extras (`jinja2`) unless you plan to use templates.

### 6) Wiring loader import model (security/operability)

- Wiring files can specify arbitrary dotted import paths (`class = "module.Class"`). This is powerful but unsafe for untrusted configs.

Recommendation:
- If wiring files are meant to be shareable artifacts, add a safer registry/allowlist model (entry points or explicit module registry) and a versioned schema.

### 7) SimUI ergonomics and runtime concerns

- Event buffer in `Interface` is unbounded (can grow forever for long-running sims).
- “Temperature override” currently mutates a private solver dict (`_initial_state`), which couples UI to implementation details.

Recommendation:
- Enforce a max event buffer size (use `EventLog.limit` consistently).
- Introduce a small “run configuration / overrides” interface on solvers, or rebuild the solver per run.

### 8) Repo hygiene (dev artifacts)

- Ensure `.gitignore` ignores common local artifacts (`.venv/`, `.pytest_cache/`, etc.) and avoid committing local environments/caches.

Recommendation:
- Keep `.gitignore` aligned with local workflow and tooling used in CI.

## Suggested next steps (pragmatic order)

1. Fix Python version targeting in `pyproject.toml` (or refactor typing syntax to truly support 3.8+).
2. Fix optional dependency boundaries so `import bsim` works without UI deps.
3. Fix cooperative stop semantics so SimUI reset/stop is reliable.
4. Decide on and implement (or remove) the `bsim-run` CLI for wiring file execution.
5. Sync docs/CI/AGENTS wording (React vs Svelte, missing scripts).
6. Add a small “plugin story” incrementally (entry points + basic plugin loader) if plugin-first is a near-term goal.
