# API: `BioWorld`

`BioWorld` is the communication-step orchestrator.

## Signature

```python
class BioWorld:
    def __init__(self, *, communication_step: float) -> None: ...
```

`communication_step` is required and defines the world-wide synchronization cadence for inter-module exchange.

## Execution model

- Every run advances in windows `[t, t + communication_step]`.
- Inputs for a window are collected from the committed signal store at the start boundary.
- Every module advances independently across the same window via `advance_window(start, end)`.
- Outputs are committed atomically at the end boundary.
- Tied-time behavior is order-independent by design; the kernel has no priority scheduling contract.

## Key methods

- `on(listener)` / `off(listener)`
- `add_biomodule(name, module)`
- `connect("src.port", "dst.port")`
- `setup(config=None)`
- `run(duration)`
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
- setup config

`branch()` deep-copies modules, restores the captured snapshot into a new `BioWorld`, and allows both worlds to diverge independently from the same boundary.
