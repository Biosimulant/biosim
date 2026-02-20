# Audit: biosim core runtime (updated)

Status: Draft
Last updated: 2026-01-12

## Snapshot

- Core library lives in `src/biosim/` and provides a BioWorld orchestration kernel, a BioModule contract, wiring loaders (code + YAML/TOML), and a minimal visualization contract.
- Tests cover runtime events, biosignals, wiring validation, visuals normalization, and SimUI spec endpoints.
- Docs exist in `docs/` (overview, quickstart, wiring, etc.).
- Examples exist in `examples/` (basic usage, world simulation, wiring builder demo, visuals demo, SimUI demos).

## Core components

- `src/biosim/world.py`: BioWorld orchestration loop, event emission, signal routing.
- `src/biosim/modules.py`: BioModule base contract (setup/reset/advance_to/etc.).
- `src/biosim/signals.py`: BioSignal data model and metadata.
- `src/biosim/wiring.py`: Wiring builder + YAML/TOML loaders.
- `src/biosim/simui/*`: Local UI runner + endpoints.

## Known gaps / follow-ups

- Formalize run parameter overrides and how modules consume them.
- Expand validation around signal metadata compatibility.
- Harden pause/resume/stop semantics with additional tests.

## Recommendations

- Keep the module contract minimal and strict.
- Document time unit semantics and scheduling guarantees.
- Add integration tests for multi-rate scheduling and event signals.
