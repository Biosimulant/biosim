# Testing strategy

Status: Draft (living)
Last updated: 2026-01-12

## Goals

- Catch regressions in event flow, wiring validation, and data contracts early.
- Keep tests fast and deterministic.

## Layers

1. Unit tests (default)
   - Core: world events, solver behavior, wiring parsing/validation, visuals normalization.
2. Contract tests
   - SimUI API response shapes and version fields.
3. CLI tests
   - Run wiring configs and verify exit codes and output.

## Guidelines

- Prefer small, focused tests with clear failure messages.
- Avoid brittle time-based tests; if concurrency must be tested, keep timeouts generous and deterministic.
- Ensure optional dependency tests skip cleanly when extras aren’t installed.

## Commands

- `PYTHONPATH=src .venv/bin/python -m pytest -q`
- (optional) coverage: `PYTHONPATH=src .venv/bin/python -m pytest --cov=bsim --cov-report=term-missing`
