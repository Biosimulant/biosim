# API: `BioModule`

`BioModule` is the runnable unit in the communication-step kernel. Modules no longer participate in a per-module due-time scheduler. Instead, the world advances every module across the same communication window and commits outputs atomically at the boundary.

## Required runtime contract

```python
class BioModule:
    def setup(self, config: dict[str, Any] | None = None) -> None: ...
    def reset(self) -> None: ...
    def set_inputs(self, signals: dict[str, BioSignal]) -> None: ...
    def advance_window(self, start: float, end: float) -> None: ...
    def get_outputs(self) -> dict[str, BioSignal]: ...
    def inputs(self) -> Mapping[str, SignalSpec]: ...
    def outputs(self) -> Mapping[str, SignalSpec]: ...
    def snapshot(self) -> dict[str, Any]: ...
    def restore(self, snapshot: Mapping[str, Any]) -> None: ...
    def visualize(self) -> VisualSpec | list[VisualSpec] | None: ...
```

## Rules

- `advance_window(start, end)` is the world-facing simulation hook.
- `inputs()` and `outputs()` declare port contracts as `port -> SignalSpec`.
- `get_outputs()` must only emit declared ports.
- Signals should be emitted as `ScalarSignal`, `ArraySignal`, `RecordSignal`, or `EventSignal`.
- `snapshot()` / `restore()` should round-trip the full module state needed for deterministic continuation from a communication boundary.

## Minimal example

```python
import biosim


class Counter(biosim.BioModule):
    def __init__(self) -> None:
        self.count = 0
        self._outputs = {}

    def outputs(self):
        return {"count": biosim.SignalSpec.scalar(dtype="int64")}

    def advance_window(self, start: float, end: float) -> None:
        self.count += 1
        self._outputs = {
            "count": biosim.ScalarSignal(
                source="counter",
                name="count",
                value=self.count,
                emitted_at=end,
                spec=self.outputs()["count"],
            )
        }

    def get_outputs(self):
        return dict(self._outputs)

    def snapshot(self):
        return {"count": self.count}

    def restore(self, snapshot):
        self.count = int(snapshot["count"])
```

## Opt-in convenience bases

`BioModule` stays intentionally small. Use it directly when a model needs full
control over timing, solver state, or emitted signal construction.

For common adapter patterns, `biosim.modules` also provides:

- `SignalEmitterBioModule`: owns `_outputs`, resolves the emitted `source` from
  `_world_name`, wraps raw values into typed signals with `make_signal()`, and
  implements `get_outputs()`.
- `StatefulBioModule`: extends `SignalEmitterBioModule` with `_time`,
  `_input_overrides`, bounded `_history`, fixed-step `advance_window()`, and
  hooks for `apply_overrides()`, `step()`, `record_state()`, and
  `output_payload()`.

These classes are convenience layers, not a replacement contract. External
modules can continue to subclass `BioModule` directly.

```python
class Counter(biosim.StatefulBioModule):
    def __init__(self) -> None:
        super().__init__(integration_step=0.1, record_initial_state=True)
        self.count = 0

    def outputs(self):
        return {"count": biosim.SignalSpec.scalar(dtype="int64")}

    def step(self, h: float) -> None:
        self.count += 1

    def record_state(self, t: float) -> None:
        self._history.append({"t": t, "count": self.count})

    def output_payload(self, t: float):
        return {"count": self.count}
```

## Notes

- The world binds `_world_name` on registered modules so emitted signals can use the registered module name as their source.
- `reset()` is useful for UI-driven reruns, but `snapshot()` / `restore()` is the durability contract for branching and replay.
- Visualization remains optional and should return JSON-serializable specs.
