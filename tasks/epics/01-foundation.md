# Epic 01: Foundation (project conventions + guardrails)

Status: Draft
Last updated: 2026-01-12
Related: `tasks/quality/definition-of-done.md`, `tasks/quality/testing-strategy.md`

## Goal

Establish baseline conventions so the project can scale without “drift”: consistent API boundaries, versioning rules, docs patterns, and contributor workflow.

## Scope

- Define versioning and compatibility rules for v0.x.
- Define “public API” policy (what’s stable, what’s internal).
- Define contribution workflow (tests, formatting, CI expectations).

## Acceptance criteria

- A written “Definition of Done” exists and is referenced by epics.
- A testing strategy exists and is referenced by epics.
- Public API surface is explicitly defined and documented.

## Implementation plan

1. Create/confirm policy documents under `tasks/quality/` (DoD, testing, security).
2. Define “public API list” and enforce exports via `src/bsim/__init__.py` and `__all__`.
3. Add a short contributor section to `README.md` (or `docs/`), linking to the policies.

## Test plan

- N/A (docs/policy). Verify links resolve and instructions match repo reality.
