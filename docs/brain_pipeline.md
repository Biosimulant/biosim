# Example: Eye -> LGN -> SC

This example shows a simple visual pathway using directed biosignals.

Code
```python
import biosim
from examples.wiring_builder_demo import Eye, LGN, SC

world = biosim.BioWorld()
wb = biosim.WiringBuilder(world)
wb.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
wb.connect("eye.visual_stream", ["lgn.retina"])   # Eye -> LGN
wb.connect("lgn.thalamus", ["sc.vision"]).apply()  # LGN -> SC

world.run(duration=0.2, tick_dt=0.1)
```

Data snapshots
- TICK events payloads (with tick_dt): `{ 't': 0.1 }`, `{ 't': 0.2 }`

Notes
- Only LGN receives Eye's `visual_stream`; SC receives only LGN's `thalamus`.
- Add port metadata to modules for validation:
  - `Eye.outputs()` -> `{ 'visual_stream' }`
  - `LGN.inputs()` -> `{ 'retina' }`
