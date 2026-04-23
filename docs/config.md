# Configuration Files

BioSim wiring configs are YAML or TOML mappings with three top-level sections:

- `runtime`
- `modules`
- `wiring`

## Required runtime block

```yaml
runtime:
  communication_step: 0.1
```

## Module declarations

Each module is either:

- a dotted class path string
- or an object with `class` and optional `args`

```yaml
modules:
  eye:
    class: examples.wiring_builder_demo.Eye
  lgn:
    class: examples.wiring_builder_demo.LGN
    args:
      gain: 2.0
```

## Wiring declarations

```yaml
wiring:
  - from: eye.visual_stream
    to: [lgn.retina]
  - from: lgn.thalamus
    to: [sc.vision]
```

References use `name.port`.

## Validation

- Source and destination ports must be declared by the participating modules.
- Port compatibility is checked from `SignalSpec`.
- Invalid configs fail fast at build/load time.
