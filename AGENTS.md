# Repository Guidelines

## Shared Context
- This repo is the core `biosim` Python library used by the platform.
- The `biosim-platform` monorepo vendors this library in `biosim-platform/B-Simulant/` (git subtree). If you change public APIs here, plan to sync those changes into the platform repo.
- The `biosimulant-landing-page` repo is a separate marketing site and does not depend on this code.

## Project Structure & Module Organization
- Source code: `src/biosim/`
  - Core: `BioWorld`, `WorldEvent`, `BioModule`, `BioSignal`
- Examples: `examples/` (e.g., `world_simulation.py`, `basic_usage.py`)
- Tests: `tests/` (pytest; files named `test_*.py`)
- Packaging: `pyproject.toml` (build via Hatchling)

Tip: Import the library as `import biosim`.

## Build, Test, and Development Commands
- Create env and install (zsh-safe): `pip install -e '.[dev]'`
- Run tests: `pytest`
- Coverage: `pytest --cov=biosim --cov-report=term-missing`
- Run examples: `python examples/world_simulation.py`
- Pre-commit hooks: `pre-commit install` then `pre-commit run -a`
- Build distribution (if `build` installed): `python -m build`

## Coding Style & Naming Conventions
- Python 3.10+; 4-space indentation; PEP 8 compliant.
- Use type hints throughout (public APIs and examples).
- Naming: modules/functions `snake_case`, classes/enums `PascalCase` (e.g., `BioWorldEvent`).
- Keep public API minimal and explicit via `__all__` in `biosim`.
- Formatting/linting: basic pre-commit hooks (trailing whitespace, EOF, YAML checks).

## Testing Guidelines
- Framework: pytest with optional coverage via `pytest-cov`.
- File naming: place tests in `tests/` with `test_*.py`.
- Scope: prefer small, focused tests (API exports, event flow, error paths).
- Examples as tests: mirror minimal usage from `examples/` where helpful.

## Commit & Pull Request Guidelines
- Commit messages: imperative mood, concise subject (≤ 72 chars), body explains why.
- Branching: feature branches (`feat/…`, `fix/…`, `docs/…`) are encouraged.
- PRs should include:
  - Description and motivation; link related issues.
  - What changed and how it’s tested (`pytest` output/coverage).
  - Any docs updates (README/examples).
- CI readiness: ensure `pytest` passes locally and pre-commit hooks are clean.

## Architecture Overview (Brief)
- Orchestration: `BioWorld` schedules modules via `min_dt`/`next_due_time` and routes signals.
- Events: `WorldEvent` published by `BioWorld`; subscribe via `world.on(...)`.
- Modules: implement the runnable `BioModule` contract and add with `world.add_biomodule(...)`.

### SimUI (Dev Notes)
- Python-first UI under `biosim.simui`: declare controls/outputs, inject into a `BioWorld`, and `launch()` or `mount()`.
- Frontend is React/Vite (prebuilt) and ships as static assets; no npm required for users.
- SSE transport: the SPA connects to `/api/stream` for real-time updates. Polling endpoints (`/api/status`, `/api/events`, `/api/visuals`) available for fallback.
- VisualSpec JSON contract drives rendering (timeseries, bar, table, image; graph placeholder; JSON fallback).
