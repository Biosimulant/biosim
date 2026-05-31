# Communication-Step Kernel

The communication-step kernel moves Biosimulant from a per-module due-time scheduler to a communication-step co-simulation model.

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

## Final settle turns

`BioWorld.run(duration)` stops at the requested simulation time. Outputs produced
at the final boundary are committed, but downstream modules only observe them on
a later communication turn. `BioWorld.settle(steps)` provides those turns without
advancing simulation time:

1. start from the outputs published at the last committed boundary
2. schedule only modules downstream of those outputs
3. deliver their current committed inputs
4. call `advance_window(current_time, current_time)`
5. commit any new outputs as the next propagation frontier

Use this for report, export, or visualisation modules that should consume final
producer outputs after the scientific duration has completed. The default runtime
behavior is unchanged unless a runner explicitly calls `settle()`.

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

`BioWorld.snapshot()` captures world time, committed signals, connection delivery state, module snapshots, and setup config. `branch()` deep-copies the current world and restores that snapshot into a new instance so both worlds can diverge independently from the same communication boundary.
