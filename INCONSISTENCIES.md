# Inconsistencies / Unfinished Areas (PRD)

Source reviewed: `product-docs/PRD.md`

## Status (this repo)

- Wiring uses `name.port` references; port validation is enforced when declared.
- BioWorld orchestration contract replaces legacy runtime layers.
- SimUI run parameters align with `duration`.

## Placeholders / unfinished

- Plugin SDK details (entry points, registry) are still draft.
- CLI spec is defined but implementation is pending.

## Underspecified requirements (hard to implement/test as written)

- Runtime semantics:
  - Event ordering and payload guarantees need a formal spec.
  - Pause/resume/stop behavior needs explicit definitions for long-running runs.
- Signal metadata:
  - Define required metadata fields and compatibility rules between modules.
- Wiring/config security:
  - Clarify schema/versioning, import resolution rules, and safe-mode behavior.
- SimUI API scope:
  - Define which endpoints and controls are mandatory vs optional.
