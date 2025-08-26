# Example: Eye → LGN → SC

This example shows a simple visual pathway using directed biosignals.

Code
```python
import bsim
from examples.wiring_builder_demo import Eye, LGN, SC

world = bsim.BioWorld(solver=bsim.FixedStepSolver())
wb = bsim.WiringBuilder(world)
wb.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
wb.connect("eye.out.visual_stream", ["lgn.in.retina"])   # Eye → LGN
wb.connect("lgn.out.thalamus", ["sc.in.vision"]).apply()  # LGN → SC

print(world.describe_wiring())
print(world.simulate(steps=2, dt=0.1))
```

Data snapshots
- `world.describe_wiring()` → `[('Eye', 'visual_stream', 'LGN'), ('LGN', 'thalamus', 'SC')]`
- STEP events payloads (from solver): `{ 'i': 0, 't': 0.1 }`, `{ 'i': 1, 't': 0.2 }`
- Simulation result: `{ 'steps': 2, 'time': 0.2 }`

Notes
- Only LGN receives Eye’s `visual_stream`; SC receives only LGN’s `thalamus`.
- Add port metadata to modules for validation:
  - `Eye.outputs()` → `{ 'visual_stream' }`
  - `LGN.inputs()` → `{ 'retina' }`
