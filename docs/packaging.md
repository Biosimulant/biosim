# Packaging

`biosimulant` supports single-file package archives for both models and labs.
The `biosim` package/import name remains available for compatibility with
existing model code.

Package unit:
- one model package wraps one `model.yaml` into a `.bsimodel`
- one lab package wraps one `lab.yaml` into a self-contained `.bsilab`

Typical use cases:
- move a runnable model or lab without shipping a whole repository
- validate package structure before upload
- cache and fetch package-backed models locally
- export a self-contained lab whose full source tree is embedded in the archive

## CLI

Initialize, validate, run, and serve a local lab without Desktop:

```bash
biosimulant labs create ./my-lab --name "My Lab"
biosimulant labs validate ./my-lab
biosimulant labs run ./my-lab --no-install-deps
biosimulant labs serve ./my-lab
```

Manage a local lab source tree without Desktop:

```bash
biosimulant labs list .
biosimulant labs get ./my-lab
biosimulant labs save ./my-lab
biosimulant labs add-model models/example --lab ./my-lab --alias example
biosimulant labs vendor-model ../model-source --lab ./my-lab --alias vendored
biosimulant labs inspect-owned ./my-lab
biosimulant labs package ./my-lab --out dist
```

Local workspace identity is stored in `.biosimulant/lab.json`; `lab.yaml`
remains the portable lab manifest embedded in exported `.bsilab` files.

Build all packages declared in a package repository manifest:

```bash
biosimulant labs release validate biosimulant-packages.yaml
biosimulant labs release build biosimulant-packages.yaml --out dist/biosimulant-packages
```

Discover and pull public registry labs:

```bash
biosimulant labs search immune
biosimulant labs info owner/lab-name@1.0.0
biosimulant labs versions owner/lab-name
biosimulant labs pull owner/lab-name@1.0.0 --target ./labs/lab-name
```

Build a lab archive:

```bash
biosimulant labs package path/to/lab --out dist
```

Validate or run a lab source tree or `.bsilab`:

```bash
biosimulant labs validate path/to/lab
biosimulant labs run path/to/lab.bsilab --no-install-deps
```

Use `--json` with `biosimulant labs` commands when you need machine-readable output.

`biosimulant pack`, `biosimulant packages`, `biosimulant hub`, and standalone
`biosimulant models` are no longer public CLI surfaces. The library-level
package helpers remain available as Python APIs for internal tooling and
compatibility code.

Publishing, private Hub download/sync, cloud runs, Desktop state, and
self-update commands are routed through the product extension boundary described
in [CLI Extensions](extensions.md).

## Public Registry

```bash
biosimulant labs search [query]
biosimulant labs info namespace/name[@version]
biosimulant labs versions namespace/name
biosimulant labs pull namespace/name[@version] --target ./local-lab
```

Anonymous public reads are supported first. Private assets should fail with a
clean auth-required error until a product extension supplies credentials.

## Package Repository Manifest

A package repository manifest declares one or more top-level packages to build:

```yaml
schema_version: "1"
default_visibility: public
packages:
  - id: example-lab
    package: demo/example-lab
    version: 1.0.0
    type: lab
    path: labs/example-lab
    visibility: public
```

`labs release validate` checks the manifest shape, package identity, SemVer versions,
source paths, package type, dependency pins, embedded lab/model paths, and archive
compatibility by building into a temporary directory.

## Runtime Compatibility

Package execution uses the provisional `biosimulant.runtime` helpers for behavior that must match other Biosimulant runtimes:

- entrypoints are loaded from the model directory with file-spec loading when possible, so multiple models can each use a `src/` namespace-style layout in one process
- `runtime.initial_inputs` are coerced into typed `BioSignal` objects against each module's declared `inputs()`
- `communication_step` is resolved using the same precedence chain as platform executors: runtime override, simulation config, base runtime, then explicit fallback
- `settle_steps` is resolved with the same runtime precedence and defaults to `0`
- nested child labs are flattened with canonical alias scoping and `io.maps_to` remapping

The `biosimulant.runtime` API is public but provisional for this minor release. The `biosim.runtime` path remains available for compatibility.

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

then `biosimulant labs package` uses those values by default.

If they are not declared, `biosimulant` falls back to:
- package: `local/<directory-name>`
- version: `0.1.0`

You can also override both at the CLI:

```bash
biosimulant labs package path/to/lab --package biosimulant/example-lab --version 1.2.0
```

## Validation Rules

`biosimulant labs validate` checks source-tree labs and `.bsilab` archives:
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

## Intentional Runtime Differences

The open-source CLI and Biosimulant platform share package interpretation semantics, but they do not share every execution policy:

- `biosimulant labs run` installs exact-pinned manifest dependencies into the current Python environment when dependency installation is enabled
- platform and desktop executors install payload dependencies into isolated per-lock-hash environments with allow/deny policy
- `biosimulant labs run` returns a compact CLI-oriented summary
- platform and desktop runs return full per-module outputs, state, visuals, and run metadata for UI consumers

## Registries And Cache

The Python package still includes simple local package registry and cache helpers for API consumers:

- `BIOSIM_PACKAGE_REGISTRY_DIR`
- `BIOSIM_PACKAGE_CACHE_DIR`

Example:

```bash
export BIOSIM_PACKAGE_REGISTRY_DIR=/tmp/biosim-registry
export BIOSIM_PACKAGE_CACHE_DIR=/tmp/biosim-cache
```

Publish or fetch packages programmatically through the Python API when internal
tooling needs local cache behavior.

## Labs

```yaml
models:
  - path: models/example-counter
    alias: counter
```

`biosimulant labs package path/to/lab` always emits a self-contained `.bsilab`. The packaged
payload preserves the runnable source tree exactly as it exists on disk under `payload/`.

Lab-local visualisation modules should remain inside each lab when portability is
the goal. If several labs intentionally carry byte-identical visualisation code,
keep those copies local and use a drift check in repository maintenance rather
than introducing a shared runtime import path.

If a lab has downstream report, export, or visualisation modules that consume
outputs produced at the final simulation boundary, set `runtime.settle_steps` to
the number of extra graph hops needed. One direct producer-to-visualisation edge
usually needs `settle_steps: 1`; a producer-to-postprocessor-to-visualisation
chain needs `settle_steps: 2`. Settling does not extend simulated time.

Nested `models[]` and `children[]` must use relative `path` refs only. Nested executable
`package`, `version`, `model_id`, `lab_id`, `hub_model_id`, and `hub_lab_id` are invalid.

If a lab depends on another model or child lab, that dependency must already exist inside
the lab directory before packaging. Packaging does not rewrite the manifest and does not bundle
nested `.bsimodel` or `.bsilab` archives.
