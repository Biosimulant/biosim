# Epic 02: Core runtime reliability (world/events/stop/pause)

Status: Draft
Last updated: 2026-01-12
Related: `src/bsim/world.py`, `src/bsim/modules.py`, `src/bsim/solver.py`, `tasks/contracts/solver-contract.md`

## Goal

Make the simulation runtime robust, predictable, and well-specified: event ordering, error semantics, and cooperative controls (pause/resume/stop) behave correctly across solvers and UI runners.

## Problem statements (current gaps)

- Cooperative stop likely escapes during `AFTER_SIMULATION` emission (see `AUDIT.md`).
- Pause/resume/stop semantics are not clearly specified for different solver behaviors.
- Error handling policy (log + continue vs fail fast) is implicit.

## Acceptance criteria

- Event flow is deterministic:
  - `LOADED` emitted once per world lifetime.
  - Each `simulate(...)` emits `BEFORE_SIMULATION` then `AFTER_SIMULATION` exactly once (even on stop).
  - `ERROR` emitted on solver exception (and exception propagates unless explicitly configured).
- `request_stop()`:
  - stops the run without raising uncaught exceptions to callers,
  - results in a consistent “stopped” outcome (define: return `None` vs partial result).
- `request_pause()`:
  - blocks progress at a defined boundary (e.g., between steps),
  - does not deadlock, and `request_resume()` continues.
- These behaviors have tests.

## Implementation plan

1. Write a precise contract in `tasks/contracts/solver-contract.md` for event emission and cooperative control points.
2. Fix `BioWorld` cooperative stop/pause implementation:
   - Ensure stop is only enforced at safe points (typically on `STEP`) and does not prevent `AFTER_SIMULATION`.
   - Ensure `PAUSED` event emission does not interfere with stop.
3. Update `SimulationManager` semantics if needed to treat “stopped” as non-error.
4. Add tests in `tests/` for stop/pause/resume and for “stop during run still emits AFTER_SIMULATION”.

## Test plan

- `PYTHONPATH=src .venv/bin/python -m pytest -q`
- Add focused tests for:
  - stop triggered mid-run,
  - pause/resume with a solver that emits steps over time (may need a small sleep-y test or a deterministic manual emit loop).

## Rollout plan

- Keep behavior backward compatible where possible.
- If stop return value changes, document in `docs/bioworld.md` and add a migration note.
