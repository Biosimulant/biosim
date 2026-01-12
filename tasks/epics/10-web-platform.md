# Epic 10: Web platform integration (future boundary spec)

Status: Draft
Last updated: 2026-01-12

## Goal

Define integration boundaries so a separate backend can run simulations and serve results/events/visuals using the same contracts.

## Acceptance criteria

- A documented boundary exists for:
  - run creation and lifecycle,
  - event streaming/polling,
  - visuals snapshots,
  - result persistence model (IDs, cursors, pagination).
- Contracts are re-usable outside SimUI (backend-agnostic).

## Implementation plan

1. Extend contracts in `tasks/contracts/` to be platform-ready.
2. Ensure SimUI uses the same contracts and versions them explicitly.
