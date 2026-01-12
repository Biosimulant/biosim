# Contract: Wiring spec (YAML/TOML)

Status: Draft (living)
Last updated: 2026-01-12

## Purpose

Define a versioned, backend-agnostic wiring schema for configuring modules and their directed connections.

## Schema v1 (proposed)

Top-level keys:
- `version: "1"`
- `modules: { <name>: <moduleSpec>, ... }`
- `wiring: [ <connectionSpec>, ... ]`

### moduleSpec

Either:
- string: dotted import path (unsafe for untrusted configs)
  - example: `"my_pkg.my_mod.Eye"`

Or object:
- `class: str` dotted import path OR registry name
- `args: dict` keyword args for constructor (optional)

Example (YAML):
```yaml
version: "1"
modules:
  eye: { class: "examples.wiring_builder_demo.Eye" }
  lgn: { class: "examples.wiring_builder_demo.LGN" }
wiring:
  - { from: "eye.out.visual_stream", to: ["lgn.in.retina"] }
```

### connectionSpec

Keys:
- `from: str` source reference: `"name.port"` or `"name.out.port"`
- `to: list[str]` destination references: `"name.port"` or `"name.in.port"`

Parsing rules:
- `in`/`out` tokens are optional and ignored semantically; they are for readability.

## Validation rules

- Every referenced module name must exist in `modules`.
- If `outputs()` is non-empty on a source module, the source port must be declared.
- If `inputs()` is non-empty on a destination module, the destination port must be declared.
- Error messages must include the full connection context.

## Security modes

Default (safe) mode:
- Disallow dotted imports from config unless explicitly enabled.
- Prefer registry-based resolution (plugin SDK) or a local allowlist.

Allow-imports mode:
- Enable dotted import resolution for trusted local configs.
