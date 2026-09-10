# API: `BioWorld`

`BioWorld` is the communication-step orchestrator.

## Signature

```python
class BioWorld:
    def __init__(self, *, communication_step: float) -> None: ...
```

`communication_step` is required and defines the world-wide synchronization cadence for inter-module exchange.

## Execution model

- Before the first positive window, BioWorld drains ready canonical
  `ONCE_BEFORE_RUN` modules in deterministic dependency layers.
- Every run advances in windows `[t, t + communication_step]`.
- Inputs for a window are collected from the committed signal store at the start boundary.
- Every `EACH_WINDOW` module advances independently across the same window via
  canonical execute or the supported temporal compatibility hook.
- Outputs are committed atomically at the end boundary.
- After the final window commit, BioWorld drains ready canonical
  `ONCE_AFTER_RUN` modules.
- Tied-time behavior is order-independent by design; the kernel has no execution-order scheduling contract.

Outputs produced during a window become visible to downstream modules at the next
communication boundary. For workflow-style graphs that end immediately after a
producer emits final outputs, call `settle(steps)` after `run(duration)` to give
downstream temporal modules explicit zero-time communication turns. Settling is
opt-in and does not advance simulation time. Canonical modules are excluded
from settling; once-policy dependency chains are drained automatically.

## Key methods

- `on(listener)` / `off(listener)`
- `add_biomodule(name, module)`
- `connect("src.port", "dst.port")`
- `setup(config=None)`
- `run(duration)`
- `settle(steps=1)`
- `request_pause()` / `request_resume()` / `request_stop()`
- `snapshot()` / `restore(snapshot)` / `branch()`
- `get_outputs(name)`
- `collect_visuals()`

## Signal semantics

- Source timestamps are preserved as `emitted_at`.
- State signals are held until overwritten by a non-empty output mapping from the same module.
- Event signals persist in the store but are delivered once per connection per source timestamp.
- Staleness is checked against the consuming port’s `SignalSpec.max_age` and `stale_policy`.

## Runtime events

- Always emitted: `STARTED`, `STEP`, `FINISHED`
- May also emit: `PAUSED`, `RESUMED`, `STOPPED`, `ERROR`

Step payloads include progress fields during active runs: `start`, `end`, `duration`, `progress`, `progress_pct`, and `remaining`.

## Snapshot guarantees

A world snapshot captures:

- current simulation time
- committed signal store
- per-connection event/staleness delivery state
- per-module snapshot payloads
- per-run once-policy completion state
- latest committed canonical module outputs
- setup config

`branch()` deep-copies modules, restores the captured snapshot into a new `BioWorld`, and allows both worlds to diverge independently from the same boundary.
