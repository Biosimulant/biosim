# Quickstart

## Install

```bash
pip install -e '.[dev]'
```

## Minimal 1.5 example

```python
import biosim


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


class LGN(biosim.BioModule):
    def __init__(self):
        self._inputs = {}

    def inputs(self):
        return {"retina": biosim.SignalSpec.scalar(dtype="float64", max_age=0.2)}

    def outputs(self):
        return {"thalamus": biosim.SignalSpec.scalar(dtype="float64")}

    def set_inputs(self, signals):
        self._inputs = dict(signals)

    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self):
        signal = self._inputs.get("retina")
        if signal is None:
            return {}
        return {
            "thalamus": biosim.ScalarSignal(
                source="lgn",
                name="thalamus",
                value=signal.value,
                emitted_at=signal.emitted_at,
                spec=self.outputs()["thalamus"],
            )
        }


world = biosim.BioWorld(communication_step=0.1)
builder = biosim.WiringBuilder(world)
builder.add("eye", Eye()).add("lgn", LGN())
builder.connect("eye.visual_stream", ["lgn.retina"]).apply()
world.run(duration=0.3)
```

## Run the built-in examples

- `python examples/world_simulation.py`
- `python examples/wiring_builder_demo.py`
- `python examples/visuals_demo.py`
- `python examples/ui_demo.py`

## Next reading

- `docs/biomodule.md`
- `docs/bioworld.md`
- `docs/wiring.md`
- `docs/migration-1-5.md`
