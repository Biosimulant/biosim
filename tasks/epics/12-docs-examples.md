# Epic 12: Docs + examples kept in sync (single source of truth)

Status: Draft
Last updated: 2026-01-12

## Goal

Ensure docs/examples reflect reality (APIs, CLI, UI tech stack, scripts), and are reliable onboarding materials.

## Acceptance criteria

- Docs do not mention non-existent commands/scripts.
- Docs accurately describe frontend tech (React vs Svelte).
- Examples are runnable with documented commands.

## Implementation plan

1. Audit docs for drift and correct:
   - SimUI frontend tech references,
   - `scripts/build_pdf.sh` mention,
   - `bsim-run` mention until CLI exists.
2. Add a docs “build” section only if actually supported.
3. Ensure examples cover:
   - core usage,
   - wiring files,
   - visuals,
   - SimUI.
