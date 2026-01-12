# Epic 03: Wiring + config (versioned schema + safe mode)

Status: Draft
Last updated: 2026-01-12
Related: `src/bsim/wiring.py`, `tasks/contracts/wiring-spec.md`

## Goal

Provide a stable, versioned wiring/config schema that supports real projects: clear validation, safe import behavior, and good diagnostics.

## Acceptance criteria

- A documented, versioned wiring schema exists (`tasks/contracts/wiring-spec.md`) with:
  - module declarations,
  - wiring connections,
  - optional args,
  - schema version field.
- YAML and TOML loaders:
  - validate schema version,
  - produce actionable error messages,
  - support optional dependency installation paths cleanly.
- A “safe mode” exists that prevents arbitrary dotted imports unless explicitly allowed.

## Implementation plan

1. Add a `version` field to the wiring spec contract.
2. Extend `build_from_spec(...)` to validate spec structure and version.
3. Add safe import strategy:
   - Option A: registry-only imports (recommended for untrusted configs).
   - Option B: allow dotted imports only with an explicit `--allow-import` flag (CLI) or `allow_imports=True` parameter.
4. Add tests for:
   - invalid version,
   - unknown module references,
   - port validation messages,
   - safe mode behavior.

## Test plan

- `PYTHONPATH=src .venv/bin/python -m pytest -q`
