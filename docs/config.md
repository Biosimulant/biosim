# Configuration Files

You can declare modules and connections in TOML or YAML. Load with `BioWorld.load_wiring(path)` or the helpers in `bsim.wiring`.

Keys
- `modules`: mapping of name → class path (or object with `class` and optional `args`).
- `wiring`: list of edges with `from` and `to`.
- References use `name.port` or `name.out.port` / `name.in.port`.

YAML example
```yaml
modules:
  eye: { class: examples.wiring_builder_demo.Eye }
  lgn: { class: examples.wiring_builder_demo.LGN }
  sc:  { class: examples.wiring_builder_demo.SC }
wiring:
  - { from: eye.out.visual_stream, to: [lgn.in.retina] }
  - { from: lgn.out.thalamus,      to: [sc.in.vision] }
```

TOML example
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

Validation
- If a module declares `outputs()`, its source port must appear in that set.
- If a module declares `inputs()`, its destination port must appear in that set.
- Errors include the full connection context for quick fixes.
