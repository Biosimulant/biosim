# Biosimulant CLI Extensions

The open-source `biosimulant` Python package owns the local developer workflow.
Product, Desktop, Hub, cloud, auth, agent, and commercial behavior are extension
surfaces over that core.

## Open-Source Core

These commands work without Desktop, Hub credentials, cloud access, or a product
binary:

```bash
biosimulant labs create ./my-lab --name "My Lab"
biosimulant labs list .
biosimulant labs get ./my-lab
biosimulant labs save ./my-lab
biosimulant labs package ./my-lab --out dist
biosimulant labs add-model models/example --lab ./my-lab --alias example
biosimulant labs vendor-model ../model-source --lab ./my-lab --alias vendored
biosimulant labs inspect-owned ./my-lab
biosimulant labs validate ./my-lab
biosimulant labs run ./my-lab
biosimulant labs serve ./my-lab

biosimulant labs release validate biosimulant-packages.yaml
biosimulant labs release build biosimulant-packages.yaml

biosimulant labs search immune
biosimulant labs info biosimulant/example-lab@1.0.0
biosimulant labs pull biosimulant/example-lab@1.0.0 --target ./example-lab
```

The OSS package also exposes runtime APIs such as `BioWorld`, `BioModule`,
signals, wiring, package validation, and local package execution.

## Product Extension Boundary

Commands in these areas require the `biosimulant-product` extension:

- `auth`: Hub login, logout, token exchange, and secure credentials
- `runs`: Desktop run index, cloud runs, upload, logs, and reports
- `runtime`: Desktop-managed runtime bootstrap and inspection
- `settings`: Desktop settings, logs, data directory, and dashboard integration
- `jobs`: commercial hosted jobs and job inspection
- `self`: product CLI self-update behavior
- `agent`, `agents`, `chat`: authenticated product agent workflows
- product-only `labs` commands such as `import`, `open`, `publish`, `sync-status`, and `release publish|ci`
- product-only `runs remote ...` commands for Hub remote runs

When the extension is not installed, the OSS CLI exits with a clear
`extension_unavailable` error instead of trying to interpret the command as a
local simulation config.

Human-readable example:

```text
Biosimulant product extension required.
Command: biosimulant labs publish ./my-lab
Category: hub
Extension: biosimulant-product
```

JSON example:

```bash
biosimulant labs release publish biosimulant-packages.yaml --json
```

```json
{
  "error": "extension_unavailable",
  "command": "labs release publish",
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

The command path is a stable ownership key such as `runtime`,
`labs publish`, or `labs release publish`. The `argv` sequence is the original
remaining CLI argument list for that command surface.

Local workflow implementations should remain in the OSS core. Product code may
authenticate, persist, adapt, upload, download, or decorate shared behavior, but
should not reimplement local lab source-tree management, package validation,
build, run, or serve logic.
