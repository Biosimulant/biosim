# Quickstart

Install
- Create a virtualenv and install dev tools (zsh-safe):
  - `pip install -e '.[dev]'`

Run an example
- Version check: `python examples/basic_usage.py`
- World, events, and biosignals: `python examples/world_simulation.py`
- Declarative wiring (code): `python examples/wiring_builder_demo.py`
- Declarative wiring (files):
  - Load a YAML/TOML wiring spec and run (bring your own file, or use one from `models`):
    - https://github.com/Biosimulant/models/tree/main/spaces
    - `python -c "import bsim; w=bsim.BioWorld(); bsim.load_wiring(w, '<path-to-wiring.yaml>'); w.run(duration=0.5, tick_dt=0.1)"`

Minimal code
```python
import bsim
from bsim import BioSignal, SignalMetadata

class Eye(bsim.BioModule):
    min_dt = 0.1

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        return {
            "visual_stream": BioSignal(
                value={"t": t},
                metadata=SignalMetadata(units="s"),
            )
        }

class LGN(bsim.BioModule):
    min_dt = 0.1

    def set_inputs(self, inputs):
        self._inputs = inputs

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        if "retina" not in self._inputs:
            return {}
        return {"thalamus": self._inputs["retina"]}

world = bsim.BioWorld()
wb = bsim.WiringBuilder(world)
wb.add("eye", Eye()).add("lgn", LGN())
wb.connect("eye.visual_stream", ["lgn.retina"]).apply()
world.run(duration=0.2, tick_dt=0.1)
```

## SimUI: Per-run resets for clean visuals

When using the SimUI, each new Run starts with a clean slate:

- The backend clears its event buffer and last-step snapshot.
- The frontend clears visuals and events before posting `/api/run`.
- If your modules keep their own history (e.g., points for a chart), implement an optional `reset()` method on the module. The world will call `reset()` on each module before every run.

Example:

```python
class SineWave(bsim.BioModule):
    min_dt = 0.1

    def __init__(self):
        self.points = []

    def advance_to(self, t: float) -> None:
        self.points.append([t, math.sin(t)])

    def reset(self):
        # Clear history between runs so charts do not overlap
        self.points = []
```
