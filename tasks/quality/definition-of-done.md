# Definition of Done (DoD)

Status: Draft (living)
Last updated: 2026-01-12

This is the checklist used to declare a task/epic “done”.

## Functional correctness

- Acceptance criteria for the task are met.
- Edge cases and error paths are handled as specified.

## Tests

- Added/updated tests for the change (unless docs-only).
- `PYTHONPATH=src .venv/bin/python -m pytest -q` passes.

## API + docs

- Public APIs are documented (README/docs) and exported intentionally via `src/bsim/__init__.py` + `__all__`.
- Breaking changes are documented with a migration note (or avoided).

## Packaging

- Optional dependencies remain optional (base import works without extras).
- Any static assets required at runtime are included in the build.

## Repo hygiene

- No local artifacts committed (`.venv/`, `.pytest_cache/`, etc.).
- CI remains green or updated accordingly.
