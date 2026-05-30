# Biosimulant CLI Extensions

The open-source `biosimulant` Python package owns the local developer workflow.
Product, Desktop, Hub, cloud, auth, agent, and commercial behavior are extension
surfaces over that core.

## Open-Source Core

These commands work without Desktop, Hub credentials, cloud access, or a product
binary:

```bash
biosimulant labs init ./my-lab --name "My Lab"
biosimulant labs validate ./my-lab
biosimulant labs run ./my-lab
biosimulant labs serve ./my-lab

biosimulant packages validate biosimulant-packages.yaml
biosimulant packages build biosimulant-packages.yaml
biosimulant packages run dist/biosimulant-packages/example.bsilab

biosimulant pack build ./my-lab
biosimulant pack validate ./dist/my-lab.bsilab
biosimulant pack run ./dist/my-lab.bsilab
```

The OSS package also exposes runtime APIs such as `BioWorld`, `BioModule`,
signals, wiring, package validation, and local package execution.

## Product Extension Boundary

Commands in these areas require the `biosimulant-product` extension:

- `auth`: Hub login, logout, token exchange, and secure credentials
- `hub`: Hub labs, Hub runs, publishing, downloads, and cloud APIs
- `runs`: Desktop run index, cloud runs, upload, logs, and reports
- `models`: Desktop model registry and Hub-backed model workflows
- `runtime`: Desktop-managed runtime bootstrap and inspection
- `settings`: Desktop settings, logs, data directory, and dashboard integration
- `jobs`: commercial hosted jobs and job inspection
- `self`: product CLI self-update behavior
- `agent`, `agents`, `chat`: authenticated product agent workflows
- product-only `labs` commands such as `pull`, `open`, `add-model`, `export`, and `publish`
- product-only `packages` commands such as `preview`, `import`, `export-model`, `export-lab`, `publish`, and `ci`

When the extension is not installed, the OSS CLI exits with a clear
`extension_unavailable` error instead of trying to interpret the command as a
local simulation config.

Human-readable example:

```text
Biosimulant product extension required.
Command: biosimulant hub labs list
Category: hub/cloud
Extension: biosimulant-product
```

JSON example:

```bash
biosimulant packages publish biosimulant-packages.yaml --json
```

```json
{
  "error": "extension_unavailable",
  "command": "packages publish",
  "extension": "biosimulant-product"
}
```

## Integration Contract

Product code should register one extension implementation with:

```python
from biosimulant.extensions import register_extension

register_extension("biosimulant-product", product_extension)
```

The registered object must implement:

```python
def run_cli_command(command: str, argv: Sequence[str], *, prog: str) -> int | None:
    ...
```

The command path is a stable ownership key such as `hub`, `runtime`,
`labs publish`, or `packages publish`. The `argv` sequence is the original
remaining CLI argument list for that command surface.

Local workflow implementations should remain in the OSS core. Product code may
authenticate, persist, adapt, upload, download, or decorate shared behavior, but
should not reimplement local lab/package validation, build, run, or serve logic.
