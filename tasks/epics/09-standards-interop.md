# Epic 09: Standards & interoperability (selective, practical)

Status: Draft
Last updated: 2026-01-12

## Goal

Add at least one practical interoperability path (import/export) without attempting full standard fidelity early.

## Acceptance criteria

- At least one supported format path exists with tests and docs.
- Export artifacts are deterministic and versioned.
- Clear “not supported” list is documented.

## Implementation plan

1. Pick a narrow scope:
   - SBML subset for simple reaction networks, or
   - a custom intermediate JSON schema with adapters.
2. Implement import/export + tests.
3. Document limitations.
