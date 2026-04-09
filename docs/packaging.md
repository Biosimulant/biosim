# Packaging

`biosim` supports single-file package archives for both models and spaces.

Package unit:
- one model package wraps one `model.yaml` into a `.bsimodel`
- one space package wraps one `space.yaml` into a self-contained `.bsispace`

Typical use cases:
- move a runnable model or space without shipping a whole repository
- validate package structure before upload
- cache and fetch package-backed models locally
- export a self-contained space whose full source tree is embedded in the archive

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
├── models/
├── spaces/
├── space.yaml
├── tests/
└── README.md
```

## Package Contents

Each package archive is a ZIP with:
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
- embedded model folders such as `payload/models/**`
- embedded child-space folders such as `payload/spaces/**`
- any additional helper files required by the space

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
- space manifests use `path`-based nested dependencies only
- every nested model and child space path stays inside the archive payload tree
- every embedded model or child space manifest is valid

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

```yaml
models:
  - path: models/example-counter
    alias: counter
```

`biosim pack build path/to/space` always emits a self-contained `.bsispace`. The packaged
payload preserves the runnable source tree exactly as it exists on disk under `payload/`.

Nested `models[]` and `children[]` must use relative `path` refs only. Nested executable
`package`, `version`, `model_id`, `space_id`, `hub_model_id`, and `hub_space_id` are invalid.

If a space depends on another model or child space, that dependency must already exist inside
the space directory before packaging. Packaging does not rewrite the manifest and does not bundle
nested `.bsimodel` or `.bsispace` archives.
