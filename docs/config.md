# Configuration Files

You can declare modules and connections in TOML or YAML. Load with helpers in `biosim.wiring`.

Keys
- `modules`: mapping of name -> class path (or object with `class`, optional `args`, optional `min_dt`, optional `priority`).
- `wiring`: list of edges with `from` and `to`.
- References use `name.port`.

YAML example
```yaml
modules:
  eye: { class: examples.wiring_builder_demo.Eye, min_dt: 0.01 }
  lgn: { class: examples.wiring_builder_demo.LGN }
  sc:  { class: examples.wiring_builder_demo.SC }
wiring:
  - { from: eye.visual_stream, to: [lgn.retina] }
  - { from: lgn.thalamus,      to: [sc.vision] }
```

TOML example
```toml
[modules.eye]
class = "examples.wiring_builder_demo.Eye"
min_dt = 0.01
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

Validation
- If a module declares `outputs()`, its source port must appear in that set.
- If a module declares `inputs()`, its destination port must appear in that set.
- Errors include the full connection context for quick fixes.
