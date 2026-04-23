# Releasing biosim to PyPI

This repository publishes to PyPI using GitHub Trusted Publishing.

## Release workflow

1. Update `src/biosim/__about__.py` with a new version (example: `0.0.4`).
2. Commit and push the version bump to `main`.
3. Create and push a matching tag (`v0.0.4`).
4. Verify GitHub Actions `Publish to PyPI` finishes successfully.

## Manual commands

```bash
git add src/biosim/__about__.py
git commit -m "Bump version to 0.0.4"
git push origin main
git tag v0.0.4
git push origin v0.0.4
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

- Explicit version: `bash scripts/release_pypi.sh 0.0.4`
- Local tag only (no push): `bash scripts/release_pypi.sh --no-push`
