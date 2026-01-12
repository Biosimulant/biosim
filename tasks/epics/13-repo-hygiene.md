# Epic 13: Repo hygiene + cleanups (from `AUDIT.md`)

Status: Draft
Last updated: 2026-01-12
Source: `AUDIT.md`

## Goal

Remove drift and footguns: align docs/CI with reality, fix dependency boundaries, ensure Python version support is correct, and keep dev artifacts out of git.

## Acceptance criteria (must all be true)

### Hygiene: git + artifacts
- `.gitignore` ignores common local artifacts:
  - `.venv/`, `.pytest_cache/`, `.coverage`, `dist/`, `build/`, `.mypy_cache/`, etc.
- No local venv/caches are committed.
- A short “dev environment” note exists (use `python -m pytest` preferred; avoid stale shebang issues).

### Packaging + optional deps boundaries
- `pip install bsim` (core only) allows `import bsim` without FastAPI installed.
- `pip install 'bsim[ui]'` enables `import bsim.simui` and SimUI usage.
- Any optional-dep import failures raise clear messages (actionable).

### Python version targeting
- `pyproject.toml` `requires-python` and classifiers match the actual syntax used in the codebase.
- CI tests the supported Python versions.

### Docs/CI truth alignment
- `AGENTS.md` and docs describe the actual SimUI frontend (React) and build steps.
- CI step names match the actual frontend tech (React/Vite) and scripts.
- `docs/README.md` does not reference missing scripts (either add `scripts/build_pdf.sh` or remove mention).
- `docs/quickstart.md` does not reference `bsim-run` unless implemented (or marks it planned).

### Runtime correctness footguns
- Cooperative stop semantics are correct (or tracked under Epic 02 with a clear dependency link).

## Implementation plan (concrete tasks)

1. Fix `.gitignore`
   - Add ignores for `.venv/`, `.pytest_cache/`, `.coverage`, `dist/`, `build/`, `.mypy_cache/`, `.ruff_cache/`, `.DS_Store`.
2. Fix optional dependency boundary
   - Remove or guard the top-level `from . import simui` in `src/bsim/__init__.py`.
   - Ensure `bsim.simui` imports FastAPI lazily or provides a clean ImportError message.
   - Update tests to validate base import path works without UI deps.
3. Fix Python version floor
   - Option A (recommended): bump to `>=3.10` (or `>=3.11`) and update classifiers + CI.
   - Option B: refactor typing syntax to be 3.8-compatible if 3.8 is required.
4. Sync docs and CI
   - Update `AGENTS.md` SimUI section (React not Svelte).
   - Update `.github/workflows/ci.yml` step label “Build SimUI frontend (React)” (or similar).
   - Fix `docs/README.md` PDF build mention (add script or remove).
   - Fix `docs/quickstart.md` `bsim-run` references until Epic 05 is done.
5. Track cooperative stop fix as dependency
   - Link to `tasks/epics/02-core-runtime.md` and ensure it’s executed before claiming SimUI reset semantics are “done”.

## Test plan

- Base import (no UI deps):
  - Create a minimal environment or run CI job that installs without `[ui]` and imports `bsim`.
- Full test suite:
  - `PYTHONPATH=src .venv/bin/python -m pytest -q`
