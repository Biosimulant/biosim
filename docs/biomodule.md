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

## Notes

- The world binds `_world_name` on registered modules so emitted signals can use the registered module name as their source.
- `reset()` is useful for UI-driven reruns, but `snapshot()` / `restore()` is the durability contract for branching and replay.
- Visualization remains optional and should return JSON-serializable specs.
