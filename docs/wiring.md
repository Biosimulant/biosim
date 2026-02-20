# API: WiringBuilder and Loaders

WiringBuilder lets you assemble module graphs in code; YAML/TOML loaders let you declare them in files. Both share parsing rules and validation.

Reference format
- `"name.port"` for sources and destinations.

Validation
- If a module declares `outputs()`, the source port must exist.
- If a module declares `inputs()`, the destination port must exist.
- Errors include the full connection context, e.g.:
  - `connect eye.nope -> lgn.retina: module 'eye' has no output port 'nope'`

Code builder
```python
wb = biosim.WiringBuilder(world)
wb.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
wb.connect("eye.visual_stream", ["lgn.retina"])  # Eye -> LGN
wb.connect("lgn.thalamus", ["sc.vision"]).apply()  # LGN -> SC
```

YAML
```yaml
modules:
  eye: { class: examples.wiring_builder_demo.Eye }
  lgn: { class: examples.wiring_builder_demo.LGN }
  sc:  { class: examples.wiring_builder_demo.SC }
wiring:
  - { from: eye.visual_stream, to: [lgn.retina] }
  - { from: lgn.thalamus,      to: [sc.vision] }
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
from = "eye.visual_stream"
to = ["lgn.retina"]
[[wiring]]
from = "lgn.thalamus"
to = ["sc.vision"]
```

Spec builder
- `biosim.build_from_spec(world, spec)` builds modules and wiring from a dict spec directly (used internally by the loaders).
  - `spec["modules"]`: mapping of name -> dotted class path or `{class, args, min_dt, priority}`.
  - `spec["wiring"]`: list of `{from: str, to: [str, ...]}`.

Loaders
- `biosim.load_wiring(world, path)` auto-detects YAML/TOML by file extension.
- `biosim.load_wiring_yaml(world, path)` and `biosim.load_wiring_toml(world, path)` for explicit formats.
- TOML support requires Python 3.11+ or `tomli` installed.
