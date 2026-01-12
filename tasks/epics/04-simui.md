# Epic 04: SimUI (local web UI) hardened + extensible

Status: Draft
Last updated: 2026-01-12
Related: `src/bsim/simui/*`, `tasks/contracts/simui-api.md`, `tasks/contracts/visualspec.md`

## Goal

Ship a small but reliable local UI for controlling runs and visualizing module outputs using polling endpoints and a stable JSON contract.

## Key problems (current)

- Optional dependency boundary leaks: base `import bsim` can require FastAPI (must be fixed in hygiene/packaging epic).
- Event buffer is unbounded; long runs can blow memory.
- Run parameter overrides (temperature) mutate private solver state; needs a cleaner mechanism.

## Acceptance criteria

- SimUI is optional:
  - Base `import bsim` works with no UI deps.
  - `import bsim.simui` errors with a clear message when `.[ui]` extras aren’t installed.
- API contract is stable and documented (`tasks/contracts/simui-api.md`):
  - `/api/spec`, `/api/run`, `/api/status`, `/api/events`, `/api/visuals`, `/api/snapshot`, `/api/reset`, `/api/pause`, `/api/resume`
  - response shapes and error codes are defined.
- Event storage is bounded (configurable limit, default sane).
- Run overrides use an explicit interface (not private dict mutation), or solver is reconstructed per run.
- UI demos work and are documented.

## Implementation plan

1. Define SimUI API contract and versioning strategy (contract doc + tests).
2. Bound event storage:
   - enforce a max length on the deque; respect `EventLog.limit`.
3. Replace solver private state override with:
   - a `Solver.configure_run(params)` hook, or
   - `SolverFactory` pattern used by SimUI to create a fresh solver per run.
4. Improve observability:
   - include run id, started/finished timestamps, last error field, and progress estimate if possible.
5. Expand UI controls only after contracts are stable (sliders, dropdowns, etc.).

## Test plan

- `PYTHONPATH=src .venv/bin/python -m pytest -q`
- Add/extend tests around:
  - event pagination and bounded behavior,
  - API error codes and schema stability.
