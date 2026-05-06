# BioModule Refactor Snapshots

These JSON files are committed regression baselines for the opt-in BioModule
helper refactor. They are intentionally normalized with `--source-root` so local
checkout paths do not appear in the artifacts.

- `biomodule_refactor_fast.json` covers fast local checks: microbiology hello
  world, Lotka-Volterra, Leibovich competition, and deterministic no-runtime
  error payloads for Vina, DiffDock, and Boltz core wrappers.
- `biomodule_refactor_koo2013_integrated_amd64.json` covers the Tellurium-backed
  Koo2013 integrated lab from a `linux/amd64` runtime.

Regenerate or compare the fast baseline from the monorepo root:

```bash
python biosim/scripts/snapshot_biomodule_outputs.py \
  --source-root . \
  --duration 0.01 \
  --compare biosim/tests/snapshots/biomodule_refactor_fast.json \
  models-done/models-microbiology-hello-world/labs/microbiology-hello-world-growth \
  models-done/models-ecology/labs/ecology-lotka-volterra-system \
  models-done/models-ecology/labs/ecology-leibovich2022-multispecies-competition \
  models-done/models-autodock-vina/labs/vina-autodock-vina-docking-predictor/models/core \
  models-done/models-diffdock/labs/diffdock-diffdockl-docking-predictor/models/core \
  models-done/models-boltz/labs/boltz-boltz2-affinity-predictor/models/core
```

The Koo2013 Tellurium baseline must be compared from an amd64 Python runtime
with Tellurium installed:

```bash
docker build --platform linux/amd64 -t biosim-tellurium-snapshot:py311 -f - . <<'EOF'
FROM --platform=linux/amd64 python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
  && apt-get install -y --no-install-recommends git libxml2 \
  && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --upgrade pip \
  && python -m pip install pyyaml pytest tellurium==2.2.11.2
EOF

docker run --platform linux/amd64 --rm -v "$PWD":/work -w /work \
  -e PYTHONPATH=/work/biosim/src biosim-tellurium-snapshot:py311 \
  python biosim/scripts/snapshot_biomodule_outputs.py \
    --source-root /work \
    --duration 10 \
    --compare biosim/tests/snapshots/biomodule_refactor_koo2013_integrated_amd64.json \
    models-done/models-biomechanics/labs/koo2013-integrated
```
