# Packaging

`biosim` supports a single-file package format, `.bsimpkg`, for both models and spaces.

Package unit:
- one model package wraps one `model.yaml`
- one space package wraps one `space.yaml`

Typical use cases:
- move a runnable model or space without shipping a whole repository
- validate package structure before upload
- cache and fetch package-backed models locally
- export a self-contained space with bundled model packages

## CLI

Build a package from a model or space directory:

```bash
python -m biosim pack build path/to/model-or-space
```

Validate a package file:

```bash
python -m biosim pack validate path/to/package.bsimpkg
```

Fetch a package from the configured local registry into cache:

```bash
python -m biosim pack fetch owner/model-name@1.0.0
```

Run a package locally:

```bash
python -m biosim pack run path/to/package.bsimpkg
```

Export a bundled space package:

```bash
python -m biosim pack export-space path/to/space
```

Use `--json` with any `biosim pack` command when you need machine-readable output.

## Source Layout

Model package source:

```text
my-model/
├── model.yaml
├── src/
├── artifacts/
├── data/
├── tests/
└── README.md
```

Space package source:

```text
my-space/
├── space.yaml
├── wiring.yaml
├── run_local.py
├── tests/
└── README.md
```

## Package Contents

Each `.bsimpkg` is a ZIP archive with:
- `package.yaml`
- `payload/`
- `integrity/sha256sums.txt`

Model package payload usually includes:
- `payload/model.yaml`
- `payload/src/**`
- `payload/artifacts/**`
- `payload/data/**`

Space package payload usually includes:
- `payload/space.yaml`
- optional local helper files such as `payload/wiring.yaml`
- optional `bundled-models/*.bsimpkg` for bundled exports

## Package Identity

If `model.yaml` or `space.yaml` declares:

```yaml
package: biosimulant/example-counter
version: 1.2.0
```

then `biosim pack build` uses those values by default.

If they are not declared, `biosim` falls back to:
- package: `local/<directory-name>`
- version: `0.1.0`

You can also override both at the CLI:

```bash
python -m biosim pack build path/to/model --package biosimulant/example-counter --version 1.2.0
```

## Validation Rules

`biosim pack validate` checks:
- required archive files exist
- no invalid archive paths
- checksums match
- `package.yaml` points to a real manifest
- model manifests contain `biosim.entrypoint`
- space manifests contain valid `models`, `wiring`, and `runtime`
- model dependencies use exact `==` pins only
- bundled space exports include all declared bundled model packages

The command is meant to be operator-friendly:
- success prints a concise summary with package name, version, and type
- failure prints a concise error list and exits non-zero

## Registries And Cache

`biosim` supports a simple local package registry and cache through environment variables:

- `BIOSIM_PACKAGE_REGISTRY_DIR`
- `BIOSIM_PACKAGE_CACHE_DIR`

Example:

```bash
export BIOSIM_PACKAGE_REGISTRY_DIR=/tmp/biosim-registry
export BIOSIM_PACKAGE_CACHE_DIR=/tmp/biosim-cache
```

Then publish or fetch packages programmatically through the Python API, and use:

```bash
python -m biosim pack fetch owner/model-name@1.0.0
```

## Spaces

Reference-based spaces should prefer package references:

```yaml
models:
  - package: biosimulant/example-counter
    version: 1.2.0
    alias: counter
```

Use `export-space` when you need a single handoff file that embeds the referenced model packages.
