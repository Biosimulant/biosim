# Compose Hub Labs Locally

`HubComposition` resolves a version-pinned public Hub Lab into the same
`BioWorld` as your local `BioModule` instances. Resolution is explicit: Python
imports never download a package.

This API is available in `biosimulant 0.0.20` and later.

## Create the lockfile

The parent Lab owns the dependency declaration and its checksum provenance:

```yaml
# lab.yaml
children:
  - alias: medium
    package: your-namespace/nutrient-medium
    version: "1.1.0"
```

```yaml
# biosimulant.lock
lock_version: 1
dependencies:
  - package: your-namespace/nutrient-medium
    version: "1.1.0"
    artifact_sha256: "<64-character archive SHA-256 from Hub>"
```

Every package-backed child requires an exact version and one matching lockfile
entry. The checksum is for the downloaded `.bsilab` archive, not a mutable
latest-version alias.

## Compose it with local code

```python
from biosimulant import BioWorld
from biosimulant.hub import HubComposition

world = BioWorld(communication_step=0.1)
world.add_biomodule("controller", DoseController())  # Your local BioModule.

composition = HubComposition(world, lab_root="./lab")
composition.add("medium", "your-namespace/nutrient-medium@1.1.0")

# Add composition.connect(...) only for ports exposed by the child Lab's root io.
composition.apply()
composition.setup()
world.run(duration=24.0)
```

`lab_root` must contain the matching `biosimulant.lock`. `apply()` resolves the
Hub Lab, verifies its archive SHA-256, flattens its models into `world`, and
applies its declared wiring. `setup()` initializes both the Hub Lab's models
and the local modules already added to the world.

## Lab-local state and offline reuse

For source Labs, downloaded payloads live only under the parent Lab:

```text
lab/
  .biosimulant/
    dependencies/
```

This directory is disposable and excluded from ordinary package payloads.
Delete it to force a clean resolution; a different Lab never reuses it. The
first resolution needs access to Hub. Later runs reuse the verified local copy.

For a standalone `.bsilab`, the default state directory is beside the archive:

```text
.biosimulant/<archive-name>.dependencies/
```

If that location is read-only, provide an explicit writable location:

```bash
biosimulant labs run dist/my-lab.bsilab --dependency-root /tmp/my-lab-state
```

## Create an archival package

Normal packages preserve package references and `biosimulant.lock`, keeping the
parent archive small. To create an offline, fully self-contained archive, vendor
every locked Hub child at build time:

```bash
biosimulant labs package ./lab --out dist --vendor-dependencies
```

Vendoring is intended for archival, regulated, or air-gapped distribution. It
does not replace the compact reference-and-lockfile workflow used while
composing and developing a Lab.
