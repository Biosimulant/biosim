# biosimulant Documentation

Welcome to the biosimulant documentation. This guide explains the core concepts, APIs, and practical wiring patterns for building modular biological simulations.

`biosimulant` is the primary package, import namespace, and CLI name. The
`biosim` import path and `python -m biosim` command remain supported for
existing model packages.

## Contents

- [Overview](overview.md): high-level architecture, core concepts (BioWorld, BioModule, BioSignal, Local Lab UI)
- [Quickstart](quickstart.md): install, run, and explore
- API:
  - [BioWorld](bioworld.md): orchestrator, events, run control (pause/resume/stop), signal routing
  - [BioModule](biomodule.md): module interface, lifecycle, port metadata, visualization
  - [Wiring](wiring.md): WiringBuilder, `build_from_spec`, and YAML/TOML loaders
  - [Configuration](config.md): how to write wiring files
- Optional contrib runtimes:
  - [CellML runtime](cellml.md): libCellML-backed CellML parsing, codegen, SciPy integration, and wrapper migration guidance
- [Example: Eye → LGN → SC pipeline](brain_pipeline.md)
- [Neuro packs](neuro.md): computational neuroscience modules (Izhikevich, Hodgkin-Huxley, Poisson input, synapses, monitors) — lives in the companion [`models`](https://github.com/Biosimulant/models) repo
- [Plugin Development](plugin-development.md): creating and distributing custom biomodules
- [Packaging](packaging.md): building, validating, fetching, and exporting `.bsimodel` and `.bsilab` artifacts
- [CLI Extensions](extensions.md): OSS/product command ownership and extension integration contract
- [Releasing](releasing.md): PyPI release/tag workflow and helper script

See the files in this folder for a textbook-style walkthrough with code and concrete data examples.

## Local Lab UI

The Biosimulant core includes a bundled web UI for local labs. Run
`biosimulant labs serve ./my-lab` and open the root URL to inspect, edit, run,
and compare lab runs.

## Building a single PDF
- Requirements: `pandoc` and a LaTeX engine (e.g., TeX Live)
- Status: planned (no `scripts/build_pdf.sh` in this repo yet)
