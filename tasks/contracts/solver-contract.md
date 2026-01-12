# Contract: Solver + event emission

Status: Draft (living)
Last updated: 2026-01-12

## Purpose

Define the stable contract between `BioWorld` and any `Solver` implementation.

## Solver interface

`Solver.simulate` signature:
- keyword-only parameters:
  - `steps: int` (must be > 0)
  - `dt: float` (must be > 0)
  - `emit: Callable[[BioWorldEvent, dict], None]`
- return value:
  - any (but recommended: dict summary)

## Event emission rules

### BioWorld-level events
The world is responsible for these:
- `LOADED`:
  - emitted once per `BioWorld` instance lifetime, on the first `simulate(...)` call.
- `BEFORE_SIMULATION`:
  - emitted exactly once at the start of each `simulate(...)` call.
- `AFTER_SIMULATION`:
  - emitted exactly once at the end of each `simulate(...)` call, regardless of stop, solver return, or solver exception (unless process crash).
- `ERROR`:
  - emitted when the solver raises an exception.

### Solver-emitted events
The solver may emit:
- `STEP` events with payload containing:
  - `i` (step index)
  - `t` (time)

The world forwards solver events to listeners/modules via the `emit` callback.

## Cooperative control points

### Pause/resume
- Pause is enforced at step boundaries.
- The system must not deadlock:
  - `request_pause()` may be called from another thread (SimUI runner).
  - `request_resume()` unblocks progress.

### Stop
- Stop is cooperative and enforced at safe boundaries.
- A stop request must not result in uncaught exceptions from `BioWorld.simulate(...)`.
- After stop, `AFTER_SIMULATION` is still emitted once.

## Compatibility notes

This contract is intended to remain stable within v0.x with documented changes only.
