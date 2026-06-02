# Releasing biosimulant to PyPI

This repository publishes to PyPI using GitHub Trusted Publishing.

The distribution name is `biosimulant`. The wheel still includes the `biosim`
import path and `python -m biosim` compatibility command for existing code, but
new installs should use `pip install biosimulant`.

## Release workflow

1. Confirm the PyPI Trusted Publisher is configured for the `biosimulant` project.
2. Update `src/biosim/__about__.py` with a new version (example: `0.0.14`).
3. Move the matching notes in `CHANGELOG.md` from `Unreleased` into a dated
   release section.
4. Commit and push the version/changelog bump to `main`.
5. Create and push a matching tag (`v0.0.14`).
6. Verify GitHub Actions `Publish to PyPI` finishes successfully.
7. Verify a fresh install from PyPI:

```bash
python -m venv /tmp/biosimulant-release-check
/tmp/biosimulant-release-check/bin/python -m pip install biosimulant
/tmp/biosimulant-release-check/bin/biosimulant --help
/tmp/biosimulant-release-check/bin/python -m biosim --help
```

## Command collision note

The Python package installs a `biosimulant` console script. Machines that also
install the Desktop/product CLI can have another `biosimulant` binary on `PATH`.
Use `python -m biosimulant ...` to explicitly run the Python package CLI during
release verification and debugging.

## Manual commands

```bash
git add src/biosim/__about__.py
git add CHANGELOG.md
git commit -m "Bump version to 0.0.14"
git push origin main
git tag v0.0.14
git push origin v0.0.14
```

## Automation script

Use the helper script:

```bash
bash scripts/release_pypi.sh
```

Behavior:

- Reads the version from `src/biosim/__about__.py`.
- Requires a clean git tree (including untracked files).
- Pushes `main`/`master`, then creates and pushes `v<version>`.

Options:

- Explicit version: `bash scripts/release_pypi.sh 0.0.14`
- Local tag only (no push): `bash scripts/release_pypi.sh --no-push`
