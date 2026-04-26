# Packaging

`biosim` supports single-file package archives for both models and labs.

Package unit:
- one model package wraps one `model.yaml` into a `.bsimodel`
- one lab package wraps one `lab.yaml` into a self-contained `.bsilab`

Typical use cases:
- move a runnable model or lab without shipping a whole repository
- validate package structure before upload
- cache and fetch package-backed models locally
- export a self-contained lab whose full source tree is embedded in the archive

## CLI

Build a package from a model or lab directory:

```bash
python -m biosim pack build path/to/model-or-lab
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

Lab package source:

```text
my-lab/
├── models/
├── labs/
├── lab.yaml
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

Lab package payload usually includes:
- `payload/lab.yaml`
- embedded model folders such as `payload/models/**`
- embedded child-lab folders such as `payload/labs/**`
- any additional helper files required by the lab

## Package Identity

If `model.yaml` or `lab.yaml` declares:

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
- lab manifests contain valid `models`, `wiring`, and `runtime`
- model dependencies use exact `==` pins only
- lab manifests use `path`-based nested dependencies only
- every nested model and child lab path stays inside the archive payload tree
- every embedded model or child lab manifest is valid

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

## Labs

```yaml
models:
  - path: models/example-counter
    alias: counter
```

`biosim pack build path/to/lab` always emits a self-contained `.bsilab`. The packaged
payload preserves the runnable source tree exactly as it exists on disk under `payload/`.

Nested `models[]` and `children[]` must use relative `path` refs only. Nested executable
`package`, `version`, `model_id`, `lab_id`, `hub_model_id`, and `hub_lab_id` are invalid.

If a lab depends on another model or child lab, that dependency must already exist inside
the lab directory before packaging. Packaging does not rewrite the manifest and does not bundle
nested `.bsimodel` or `.bsilab` archives.
