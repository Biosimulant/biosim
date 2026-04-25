# Communication-Step Kernel

The communication-step kernel moves BioSim from a per-module due-time scheduler to a communication-step co-simulation model.

## What changed

- typed port contracts via `SignalSpec`
- typed runtime signals instead of schema-less `value: Any`
- `advance_window(start, end)` is the world-facing simulation hook
- atomic output commit at communication boundaries
- explicit staleness handling on consuming ports
- world snapshots and in-memory branching

## Communication-step semantics

For each window `[t, t + communication_step]`:

1. the world reads the committed signal store at `t`
2. the world delivers those inputs to every module
3. every module advances across the same window
4. the world commits all module outputs atomically at `t + communication_step`

This means closed loops are modeled as sampled-data coupling at communication boundaries. Rollback, algebraic-loop solving, and FMI negotiation are explicit non-goals for this version.

## Typed signals

The communication-step kernel defines a closed signal family:

- `ScalarSignal`
- `ArraySignal`
- `RecordSignal`
- `EventSignal`

Each signal binds a `SignalSpec` carrying:

- `signal_type`
- `kind`
- `dtype`
- `shape`
- `emitted_unit` on outputs
- `accepted_profiles` on inputs
- `interpolation`
- `max_age`
- `stale_policy`
- optional record/event schema

The kernel only validates compatibility. It does not convert units or reinterpret payload types. Outputs declare one emitted profile; inputs may declare multiple accepted profiles, each with its own `signal_type`, `dtype`, `shape`, `schema`, and accepted units.

## Snapshot and branch

`BioWorld.snapshot()` captures world time, committed signals, short signal history, connection delivery state, and module snapshots. `branch()` deep-copies the current world and restores that snapshot into a new instance so both worlds can diverge independently from the same communication boundary.
