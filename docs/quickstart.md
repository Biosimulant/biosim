# Quickstart

Install
- Create a virtualenv and install dev tools (zsh-safe):
  - `pip install -e '.[dev]'`

Run an example
- Version check: `python examples/basic_usage.py`
- World, events, and biosignals: `python examples/world_simulation.py`
- Declarative wiring (code): `python examples/wiring_builder_demo.py`
- Declarative wiring (files):
  - TOML: `bsim-run --wiring examples/configs/brain.toml --steps 5 --dt 0.1`
  - YAML: `bsim-run --wiring examples/configs/brain.yaml --steps 5 --dt 0.1`

Minimal code
```python
import bsim

class Eye(bsim.BioModule):
    def subscriptions(self):
        return {bsim.BioWorldEvent.STEP}
    def on_event(self, event, payload, world):
        world.publish_biosignal(self, topic="visual_stream", payload={"t": payload.get("t")})

class LGN(bsim.BioModule):
    def on_signal(self, topic, payload, source, world):
        if topic == "visual_stream":
            world.publish_biosignal(self, topic="thalamus", payload=payload)

world = bsim.BioWorld(solver=bsim.FixedStepSolver())
wb = bsim.WiringBuilder(world)
wb.add("eye", Eye()).add("lgn", LGN())
wb.connect("eye.out.visual_stream", ["lgn.in.retina"]).apply()
print(world.describe_wiring())  # [('Eye', 'visual_stream', 'LGN')]
print(world.simulate(steps=2, dt=0.1))  # {'steps': 2, 'time': 0.2}
```
