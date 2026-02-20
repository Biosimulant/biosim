# biosim Documentation

Welcome to the biosim documentation. This guide explains the core concepts, APIs, and practical wiring patterns for building modular biological simulations.

## Contents

- [Overview](overview.md): high-level architecture, core concepts (BioWorld, BioModule, BioSignal, SimUI)
- [Quickstart](quickstart.md): install, run, and explore
- API:
  - [BioWorld](bioworld.md): orchestrator, events, run control (pause/resume/stop), signal routing
  - [BioModule](biomodule.md): module interface, lifecycle, port metadata, visualization
  - [Wiring](wiring.md): WiringBuilder, `build_from_spec`, and YAML/TOML loaders
  - [Configuration](config.md): how to write wiring files
- [Example: Eye → LGN → SC pipeline](brain_pipeline.md)
- [Neuro packs](neuro.md): computational neuroscience modules (Izhikevich, Hodgkin-Huxley, Poisson input, synapses, monitors) — lives in the companion [`models`](https://github.com/Biosimulant/models) repo
- [Plugin Development](plugin-development.md): creating and distributing custom biomodules

See the files in this folder for a textbook-style walkthrough with code and concrete data examples.

## SimUI

The biosim core includes a lightweight web UI (SimUI) for running and visualizing simulations. See the [README](../README.md#simui-python-declared-ui) for:
- Python-declared interface API
- Full REST + SSE endpoint reference
- Config editor sub-API for visual wiring editing
- VisualSpec render types (timeseries, bar, table, image, scatter, heatmap, graph, custom)

## Building a single PDF
- Requirements: `pandoc` and a LaTeX engine (e.g., TeX Live)
- Status: planned (no `scripts/build_pdf.sh` in this repo yet)
