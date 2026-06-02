# Releasing biosimulant and biosim to PyPI

This repository publishes to PyPI using GitHub Trusted Publishing.

The primary distribution name is `biosimulant`. The workflow also publishes a
legacy `biosim` distribution from the same source tree so existing installers can
continue to use `pip install biosim`.

Both wheels include the `biosim` and `biosimulant` import paths. The primary
`biosimulant` distribution installs the `biosimulant` console command. The
legacy `biosim` distribution installs the `biosim` console command.

## Release workflow

1. Confirm PyPI Trusted Publishers are configured for the `biosimulant` and
   `biosim` projects.
2. Update `src/biosim/__about__.py` with a new version (example: `0.0.12`).
3. Commit and push the version bump to `main`.
4. Create and push a matching tag (`v0.0.12`).
5. Verify GitHub Actions `Publish to PyPI` finishes successfully.
6. Verify a fresh install from PyPI:

```bash
python -m venv /tmp/biosimulant-release-check
/tmp/biosimulant-release-check/bin/python -m pip install biosimulant
/tmp/biosimulant-release-check/bin/biosimulant --help
/tmp/biosimulant-release-check/bin/python -m biosim --help

python -m venv /tmp/biosim-release-check
/tmp/biosim-release-check/bin/python -m pip install biosim
/tmp/biosim-release-check/bin/biosim --help
/tmp/biosim-release-check/bin/python -m biosimulant --help
```

## Command collision note

The Python package installs a `biosimulant` console script. Machines that also
install the Desktop/product CLI can have another `biosimulant` binary on `PATH`.
Use `python -m biosimulant ...` to explicitly run the Python package CLI during
release verification and debugging.

## Final biosim archive release

Before archiving the legacy `biosim` PyPI project, publish one final `biosim`
release whose package description warns users that `biosim` is archived and
points them to `biosimulant`.

Current transition flow:

1. Configure a PyPI Trusted Publisher for the existing `biosim` project using
   owner `Biosimulant`, repository `biosim`, workflow `publish-pypi.yml`, and
   environment `pypi`.
2. Run the `Publish to PyPI` GitHub workflow on `main`.
3. Confirm `biosim==0.0.12` is visible on PyPI with the archive notice.
4. Archive the `biosim` project on PyPI.
5. Remove the temporary archive notice from this repository README so the
   project documentation focuses on `biosimulant`.

## Manual commands

```bash
git add src/biosim/__about__.py
git commit -m "Bump version to 0.0.12"
git push origin main
git tag v0.0.12
git push origin v0.0.12
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

- Explicit version: `bash scripts/release_pypi.sh 0.0.12`
- Local tag only (no push): `bash scripts/release_pypi.sh --no-push`
