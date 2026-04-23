# Plugin Development (1.5)

Plugins and first-party modules should target the 1.5 kernel contract directly.

## Expectations

- implement `advance_window(start, end)`
- declare `inputs()` / `outputs()` with `SignalSpec`
- emit typed signals (`ScalarSignal`, `ArraySignal`, `RecordSignal`, `EventSignal`)
- implement `snapshot()` / `restore()` for branch-safe state

## Example

```python
import biosim


class Gain(biosim.BioModule):
    def __init__(self, gain: float = 1.0):
        self.gain = float(gain)
        self._latest = None

    def inputs(self):
        return {"x": biosim.SignalSpec.scalar(dtype="float64")}

    def outputs(self):
        return {"y": biosim.SignalSpec.scalar(dtype="float64")}

    def set_inputs(self, signals):
        self._latest = signals.get("x")

    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self):
        if self._latest is None:
            return {}
        return {
            "y": biosim.ScalarSignal(
                source="gain",
                name="y",
                value=float(self._latest.value) * self.gain,
                emitted_at=self._latest.emitted_at,
                spec=self.outputs()["y"],
            )
        }

    def snapshot(self):
        return {"gain": self.gain}

    def restore(self, snapshot):
        self.gain = float(snapshot["gain"])
```

## Design guidance

- Prefer explicit schemas plus emitted/accepted unit metadata on ports.
- Use event specs only for discrete delivery semantics.
- Keep snapshot payloads JSON-serializable where practical.
- Treat communication steps as the public coupling boundary; do not rely on scheduler ordering.
