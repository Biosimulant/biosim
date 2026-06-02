# Changelog

All notable changes to `biosimulant` are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.0.14] - 2026-06-02

### Changed

- Move SimUI runtime dependencies into the default package install so
  `pipx install biosimulant` supports `biosimulant labs serve` without requiring
  the `biosimulant[ui]` extra.
- Keep `biosimulant[ui]` as a backwards-compatible install extra while updating
  docs and stale-environment error messages to lead with the default install.
- Update backend, desktop, sandbox, and web surfaces to target the next
  `biosimulant` runtime release (`0.0.14`).

## [0.0.13] - 2026-06-02

### Added

- Add shell completion support for the `biosimulant` CLI.
- Add local lab identity handling improvements for source-tree lab workflows.

### Changed

- Focus release instructions and packaging language on the `biosimulant`
  distribution and CLI.
- Split PyPI publishing workflows for clearer release automation.
- Add archive messaging for the legacy `biosim` package.

## [0.0.12] - 2026-06-02

### Added

- Add product extension contracts and command routing for product-owned CLI
  surfaces.
- Add broader registry, workspace, and package-management test coverage.

### Changed

- Rename public package and documentation language from BioSim/Biosim toward
  Biosimulant while preserving compatibility imports and commands.
- Improve package validation and lab manifest package formatting.
- Tighten the coverage gate and tidy wiring builder demo coverage.

## [0.0.11] - 2026-05-30

### Added

- Add the lab-scoped CLI surface for local lab initialization, validation,
  running, serving, packaging, registry lookup, and package repository release
  workflows.
- Add package repository manifest validation/build support under
  `biosimulant labs release`.
- Add input value type handling for `SignalSpec`.

### Changed

- Move public CLI guidance toward lab-scoped commands such as
  `biosimulant labs package`, `biosimulant labs run`, and
  `biosimulant labs serve`.

## [0.0.10] - 2026-05-30

### Changed

- Rename the Python distribution and primary CLI entrypoint to `biosimulant`.
- Preserve the legacy `biosim` import path and `python -m biosim` compatibility
  command for existing model packages.

[Unreleased]: https://github.com/Biosimulant/biosim/compare/v0.0.14...HEAD
[0.0.14]: https://github.com/Biosimulant/biosim/compare/v0.0.13...v0.0.14
[0.0.13]: https://github.com/Biosimulant/biosim/compare/v0.0.12...v0.0.13
[0.0.12]: https://github.com/Biosimulant/biosim/compare/v0.0.11...v0.0.12
[0.0.11]: https://github.com/Biosimulant/biosim/compare/v0.0.10...v0.0.11
[0.0.10]: https://github.com/Biosimulant/biosim/releases/tag/v0.0.10
