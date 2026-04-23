# Migration Guide: V1 to V1.5

V1.5 is the current prelaunch kernel upgrade.

## Required code changes

1. Replace the legacy single-time-step method with `advance_window(start, end)`.
2. Remove reliance on legacy per-module scheduling and ordering.
3. Replace set-style `inputs()` / `outputs()` with `dict[str, SignalSpec]`.
4. Replace generic `BioSignal(...)` payloads with typed signals.
5. Add `snapshot()` / `restore(snapshot)` for any module that holds state.
6. Replace single `units` strings with output `emitted_unit` or input `accepted_profiles`.

## Before

```python
class Eye(biosim.BioModule):
    def outputs(self):
        return {"visual_stream"}

    def advance_window(self, start: float, end: float) -> None:
        self._time = end

    def get_outputs(self):
        return {
            "visual_stream": biosim.BioSignal(
                source="eye",
                name="visual_stream",
                value=self._time,
                emitted_at=self._time,
            )
        }
```

## After

```python
class Eye(biosim.BioModule):
    def __init__(self):
        self._outputs = {}

    def outputs(self):
        return {"visual_stream": biosim.SignalSpec.scalar(dtype="float64")}

    def advance_window(self, start: float, end: float) -> None:
        self._outputs = {
            "visual_stream": biosim.ScalarSignal(
                source="eye",
                name="visual_stream",
                value=end,
                emitted_at=end,
                spec=self.outputs()["visual_stream"],
            )
        }

    def get_outputs(self):
        return dict(self._outputs)
```

## Config changes

- add `runtime.communication_step`
- remove legacy per-module timing and priority fields from module entries

## Semantic changes to keep in mind

- Outputs commit at communication boundaries, not immediately when one module runs.
- Tied-time ordering is not part of the public model anymore.
- Stale reads are measured from source `emitted_at`, not rewritten consumer time.
- Event delivery is once per connection per source timestamp.
