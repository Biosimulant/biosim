# API: WiringBuilder and Loaders

WiringBuilder lets you assemble module graphs in code; YAML/TOML loaders let you declare them in files. Both share parsing rules and validation.

Reference format
- `"name.port"` or `"name.out.port"` for sources
- `"name.port"` or `"name.in.port"` for destinations
- Direction tokens are optional, for readability only.

Validation
- If a module declares `outputs()`, the source port must exist.
- If a module declares `inputs()`, the destination port must exist.
- Errors include the full connection context, e.g.:
  - `connect eye.out.nope -> lgn.in.retina: module 'eye' has no output port 'nope'`

Code builder
```python
wb = bsim.WiringBuilder(world)
wb.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
wb.connect("eye.out.visual_stream", ["lgn.in.retina"])  # Eye → LGN
wb.connect("lgn.out.thalamus", ["sc.in.vision"]).apply()  # LGN → SC
```

YAML
```yaml
modules:
  eye: { class: examples.wiring_builder_demo.Eye }
  lgn: { class: examples.wiring_builder_demo.LGN }
  sc:  { class: examples.wiring_builder_demo.SC }
wiring:
  - { from: eye.out.visual_stream, to: [lgn.in.retina] }
  - { from: lgn.out.thalamus,      to: [sc.in.vision] }
```

TOML
```toml
[modules.eye]
class = "examples.wiring_builder_demo.Eye"
[modules.lgn]
class = "examples.wiring_builder_demo.LGN"
[modules.sc]
class = "examples.wiring_builder_demo.SC"

[[wiring]]
from = "eye.out.visual_stream"
to = ["lgn.in.retina"]
[[wiring]]
from = "lgn.out.thalamus"
to = ["sc.in.vision"]
```

Loaders
- `bsim.load_wiring(world, path)` auto-detects YAML/TOML.
- `bsim.load_wiring_yaml(world, path)` and `bsim.load_wiring_toml(world, path)`.
- Shortcut: `BioWorld.load_wiring(path)`.
