# Epic 05: CLI (`bsim-run`) for config-driven runs

Status: Draft
Last updated: 2026-01-12
Related: `tasks/contracts/wiring-spec.md`

## Goal

Provide a first-class CLI workflow to execute YAML/TOML wiring specs, matching docs and enabling headless execution.

## Acceptance criteria

- A console script exists: `bsim-run`.
- Supports:
  - `--wiring PATH` (yaml/toml)
  - `--steps N`, `--dt FLOAT`
  - `--safe` (default) vs `--allow-imports` for dotted imports (if supported)
  - `--print-wiring` and `--json` output mode
- Exit codes:
  - `0` success,
  - `2` usage error,
  - `1` runtime error.
- Covered by tests (at least basic “happy path” and schema validation).
- Docs updated to match exactly.

## Implementation plan

1. Implement a small `argparse` CLI under `src/bsim/cli.py` (or `src/bsim/__main__.py`).
2. Register entry point in `pyproject.toml` under `[project.scripts]`.
3. Implement output modes:
   - print final result dict,
   - optionally print collected visuals snapshot.
4. Add tests that run the CLI via `python -m bsim ...` or `subprocess`.

## Test plan

- `PYTHONPATH=src .venv/bin/python -m pytest -q`
