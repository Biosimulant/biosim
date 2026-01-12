# Epic 11: Observability + performance (practical)

Status: Draft
Last updated: 2026-01-12

## Goal

Provide sufficient introspection for debugging and avoid obvious performance/memory pitfalls.

## Acceptance criteria

- Logging is consistent and configurable.
- Long runs do not leak memory via unbounded buffers.
- Basic metrics are available (step count, elapsed time, etc.).

## Implementation plan

1. Bounded buffers (SimUI events).
2. Optional “trace” mode to record events to disk.
3. Add a simple profiling example/guide if needed.
