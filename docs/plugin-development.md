# Plugin Development

Plugins and first-party modules use one `BioModule` contract. New modules use the
canonical execute hook; existing temporal plugins may retain their supported
compatibility hook.

## Expectations

- implement `execute(inputs, *, context)` for new finite or temporal computation
- explicitly select `ONCE_BEFORE_RUN`, `EACH_WINDOW`, or `ONCE_AFTER_RUN`; existing
  temporal modules may keep `advance_window()` and the default `EACH_WINDOW`
- declare `inputs()` / `outputs()` with `SignalSpec`
- emit typed signals (`ScalarSignal`, `ArraySignal`, `RecordSignal`, `EventSignal`)
- implement `snapshot()` / `restore()` for branch-safe state

## Example

```python
import biosimulant as biosim


class Gain(biosim.BioModule):
    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def __init__(self, gain: float = 1.0):
        self.gain = float(gain)

    def inputs(self):
        return {"x": biosim.SignalSpec.scalar(dtype="float64")}

    def outputs(self):
        return {"y": biosim.SignalSpec.scalar(dtype="float64")}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        latest = inputs.get("x")
        if latest is None:
            return {}
        return {"y": float(latest.value) * self.gain}

    def snapshot(self):
        return {"gain": self.gain}

    def restore(self, snapshot):
        self.gain = float(snapshot["gain"])
```

## Design guidance

- Use `ONCE_BEFORE_RUN` for finite preprocessing and inference, and
  `ONCE_AFTER_RUN` for final analysis or export.
- Use canonical `EACH_WINDOW` for temporal advancement or finite computation that
  consumes evolving state at every positive communication window.
- Canonical modules do not participate in zero-time settle in 0.0.26; retain the
  compatibility hook when settle is a requirement.
- Do not override both `execute()` and `advance_window()`.
- Prefer explicit schemas plus emitted/accepted unit metadata on ports.
- Use event specs only for discrete delivery semantics.
- Keep snapshot payloads JSON-serializable where practical.
- Treat communication steps as the public coupling boundary; do not rely on scheduler ordering.
