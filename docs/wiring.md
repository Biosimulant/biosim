# Wiring Builder and Loaders

`WiringBuilder` assembles a graph of named modules and validated port connections.

## Code builder

```python
world = biosim.BioWorld(communication_step=0.1)
builder = biosim.WiringBuilder(world)
builder.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
builder.connect("eye.visual_stream", ["lgn.retina"])
builder.connect("lgn.thalamus", ["sc.vision"]).apply()
```

## File-backed specs

```yaml
runtime:
  communication_step: 0.1
modules:
  eye: { class: examples.wiring_builder_demo.Eye }
  lgn: { class: examples.wiring_builder_demo.LGN }
  sc: { class: examples.wiring_builder_demo.SC }
wiring:
  - { from: eye.visual_stream, to: [lgn.retina] }
  - { from: lgn.thalamus, to: [sc.vision] }
```

## Validation behavior

- `from` and `to` references must use `name.port`.
- Source ports must exist in the source module’s `outputs()`.
- Destination ports must exist in the target module’s `inputs()`.
- Connection compatibility is checked via `SignalSpec`.

## Loader helpers

- `biosim.build_from_spec(world, spec)`
- `biosim.load_wiring(world, path)`
- `biosim.load_wiring_yaml(world, path)`
- `biosim.load_wiring_toml(world, path)`
