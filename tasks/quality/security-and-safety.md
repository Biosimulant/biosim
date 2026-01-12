# Security & safety posture

Status: Draft (living)
Last updated: 2026-01-12

## Configuration safety

Risk: wiring files can load arbitrary dotted import paths.

Mitigations (planned):
- Default “safe mode” that prevents dotted imports.
- Registry-based module/solver resolution (plugin SDK).
- Explicit `--allow-imports` opt-in for trusted local runs.

## Runtime safety

- Module errors should not crash the world loop by default (log + continue), but policy may become configurable.
- Avoid unbounded memory growth in long-running runs (bounded buffers, pagination).

## Dependency safety

- Optional deps must not be required for base import.
- Avoid executing external processes during import.
