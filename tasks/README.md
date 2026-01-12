# Tasks (PRD + Implementation Plan)

This folder is the living product + engineering plan for `B-Simulant` (`bsim`). It’s structured so each epic/task file can be updated independently as work progresses.

## How to use

- Start with `tasks/PRD.md` for goals, scope, personas, requirements, and non-goals.
- Use `tasks/ROADMAP.md` for sequencing and milestone definitions.
- Each epic lives in `tasks/epics/` and is designed to be updated over time:
  - status, current notes, decisions, acceptance criteria, implementation plan, test plan, and rollout plan.
- Shared technical contracts live in `tasks/contracts/`.
- Quality gates and repo-wide practices live in `tasks/quality/`.

## Updating task files (lightweight process)

When you work on an epic, update its file:
- Set `Status` and `Last updated`.
- Add/adjust acceptance criteria as requirements clarify.
- Record decisions in the “Decisions” section (with rationale).
- Add links to PRs, issues, and docs.

## Index

- Product
  - `tasks/PRD.md`
  - `tasks/ROADMAP.md`
- Epics
  - `tasks/epics/01-foundation.md`
  - `tasks/epics/02-core-runtime.md`
  - `tasks/epics/03-wiring-config.md`
  - `tasks/epics/04-simui.md`
  - `tasks/epics/05-cli.md`
  - `tasks/epics/06-packaging-release.md`
  - `tasks/epics/07-domain-modules.md`
  - `tasks/epics/08-plugin-sdk.md`
  - `tasks/epics/09-standards-interop.md`
  - `tasks/epics/10-web-platform.md`
  - `tasks/epics/11-observability-performance.md`
  - `tasks/epics/12-docs-examples.md`
  - `tasks/epics/13-repo-hygiene.md`
- Contracts
  - `tasks/contracts/solver-contract.md`
  - `tasks/contracts/wiring-spec.md`
  - `tasks/contracts/visualspec.md`
  - `tasks/contracts/simui-api.md`
  - `tasks/contracts/plugin-contract.md`
- Quality
  - `tasks/quality/definition-of-done.md`
  - `tasks/quality/testing-strategy.md`
  - `tasks/quality/security-and-safety.md`
