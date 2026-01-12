# Epic 08: Plugin SDK (entry points + registry)

Status: Draft
Last updated: 2026-01-12
Related: `tasks/contracts/plugin-contract.md`

## Goal

Enable third-party packages to provide modules/solvers (and optionally renderers) discovered at runtime with clear versioning and compatibility.

## Acceptance criteria

- A plugin discovery mechanism exists (Python entry points recommended).
- A registry API exists for:
  - listing available plugins,
  - resolving module/solver factories by name,
  - validating plugin compatibility (version checks).
- Wiring spec can reference registry names (preferred) instead of dotted imports.
- Docs include “how to build a plugin package”.

## Implementation plan

1. Define plugin contract (names, metadata, versions, exported objects).
2. Implement discovery (importlib.metadata entry_points).
3. Add registry module in `bsim`.
4. Integrate wiring loader with registry mode.
5. Add tests using an in-repo “fake plugin” pattern.
