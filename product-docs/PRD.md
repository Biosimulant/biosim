# Product Requirements Document (PRD): Biosimulant Core (`B-Simulant` / `bsim`)

Status: Draft (living)
Last updated: 2026-01-12

## 1) Summary

`bsim` is a modular biological simulation engine focused on composability: users build simulations by wiring reusable `BioModule`s into a `BioWorld` that orchestrates multi-rate execution and signal routing. The project also includes SimUI: a Python-declared web UI for controlling runs and rendering module visuals via a JSON contract.

This PRD describes the end-to-end product, from core simulation primitives through configuration, UI, plugins, and a future hosted run-management platform.

## 2) Goals

### Near-term (v0.x)
- Provide a stable, minimal core API: `BioWorld`, `WorldEvent`, `BioModule`, `BioSignal`, wiring loaders/builders, and a minimal visuals contract.
- Ensure packaging is correct and optional dependencies are truly optional.
- Provide a functional "run from config" workflow for YAML/TOML wiring specs, including a minimal CLI.
- Provide SimUI that can run local simulations, stream status (SSE) with polling fallback, show events, and render visuals.
- Ship one credible domain reference pack focused on neuroscience (single neuron + small microcircuit) to prove end-to-end usability.

### Mid-term (v1.0)
- Define a plugin SDK: third-party modules and visual renderers registered via entry points.
- Standardize configuration and contracts (versioned schemas, compatibility guarantees).
- Add at least 1-2 domain module packs as reference implementations (not "complete biology", but credible end-to-end examples).
- Add basic interoperability (import/export) with at least one modeling standard or a constrained subset.
  - Preference: standards are integrated inside biomodule packages (not in core).

### Long-term
- "Hybrid execution": batch runs, parameter sweeps, distributed execution options.
- Web platform: project management, storage, collaboration, cloud execution.

## 3) Non-goals (for core repo scope)

- Implementing all biological domains (MD/CA/PKPD/etc.) as first-class built-ins immediately.
- Full SBML/CellML fidelity in early versions.
- Production-grade distributed compute orchestration in early versions.
- Replacing domain-specific simulators; `bsim` is a composition/orchestration layer first.
  - Biomodules may wrap external simulators, but the core does not re-implement them.

## 4) Personas & primary use cases

### Persona A: Researcher building a modular experiment
- Needs: quick prototyping, event hooks, module composition, reproducible configs.
- Success: can wire modules, run a simulation, and inspect results/visuals.

### Persona B: Developer building reusable module packs
- Needs: stable base interfaces, plugin discovery, validation, good docs.
- Success: can publish a module package and have `bsim` discover and validate it.

### Persona C: Educator/demonstrator
- Needs: nice UI, easy-to-run examples, good visuals.
- Success: can run demos locally with `pip install bsim[ui]` and a single command.

### Persona D: Platform team (future web platform)
- Needs: API boundaries, data contracts, run lifecycle.
- Success: can execute simulations via an API and store results/events/visuals.

## 5) Core requirements (functional)

### R1: Simulation runtime
- Must support a single `BioWorld` coordinating:
  - lifecycle events
  - multi-rate scheduling
  - directed module-to-module signals
- Must be robust to module/listener errors (log + continue; configurable later).
- Must support cooperative pause/resume/stop with predictable semantics.

### R2: Scheduling and time
- Must support `min_dt` and `next_due_time(t)` for module scheduling.
- Must support a global tick stream for UI/event consumers (`tick_dt`).
- Must define time units (`seconds` by default) consistently across modules.

### R3: Modules
- Must define module base interface and optional capabilities:
  - `setup`, `reset`, `advance_to`, `set_inputs`, `get_outputs`, `get_state`
  - port declarations for validation
  - visuals exposure

### R4: Wiring/configuration
- Must allow wiring in code and via configuration files.
- Must validate wiring against declared ports when present.
- Must support YAML and TOML (with optional deps).
- Must provide helpful error messages.
- Must provide a CLI to run wiring specs.

### R5: Visuals contract
- Must define a JSON-serializable, renderer-agnostic `VisualSpec` contract.
- Must provide server-side validation/normalization.
- Must support a small set of core types (timeseries, bar, table, image, graph placeholder, JSON fallback).

### R6: SimUI
- Must mount and serve a local web UI with:
  - controls (duration/tick_dt + extensible controls)
  - run/pause/resume/reset
  - event log and visuals panel
  - SSE streaming transport with polling fallback (no websockets required)
- Must be optional (`bsim` base should import without UI deps).

### R7: Plugin SDK (mid-term)
- Must support discovery and registration of:
  - modules
  - renderers
- Must be versioned and compatible across `bsim` versions with clear rules.

### R8: Web platform (long-term)
- Must support:
  - project/run management
  - result persistence
  - UI dashboards consuming the same contracts

## 6) Non-functional requirements

- Correct packaging and dependency boundaries (optional extras truly optional).
- Type hints and stable public exports (`__all__`).
- Test coverage for:
  - event flow and error paths
  - wiring validation and loaders
  - visuals validation
  - CLI behaviors
  - SimUI API contract
- Security posture for config-driven imports (safe mode/allowlist options).
- Reproducibility: pinned build steps for UI assets; deterministic builds.

## 7) Milestones (high-level)

See the internal platform repository for a sequenced plan and milestone gates.
