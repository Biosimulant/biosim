Examples
========

Quick index
-----------

Core usage
- `basic_usage.py`: Prints the installed package version to verify imports.
- `world_simulation.py`: Shows DI with a solver, listeners, and biosignal routing.
- `wiring_builder_demo.py`: Demonstrates `WiringBuilder` (including port renaming).
- `visuals_demo.py`: Minimal example of module-provided visuals + `world.collect_visuals()`.

SimUI
- `ui_demo.py`: Minimal SimUI demo (requires UI extras).
- `multi_module_ui_demo.py`: Multi-module visuals demo in SimUI (large defaults).
- `ecology_simui_demo.py`: Ecology SimUI demo (predator-prey + three-species; can load a YAML config).
- `neuro_simui_demo.py`: Neuro SimUI demo for the neuro pack.

Domain packs (headless demos)
- `fixed_step_bio_solver.py`: `FixedStepBioSolver` built-in processes + custom process example.
- `neuro_single_neuron_demo.py`: Single-neuron Izhikevich demo + monitors/metrics.
- `neuro_microcircuit_demo.py`: E/I microcircuit demo + monitors/metrics.

Configs
- `configs/`: Example YAML/TOML configs runnable via the CLI (`python -m bsim ...`).

Adapters (TimeBroker)
- `adapters/test_tellurium_adapter.py`: End-to-end Tellurium adapter test (requires `bsim[tellurium]`).

Pack template
- `pack-template/`: Template for creating your own module pack (includes its own tests/configs).

How to run
----------

Option A: Editable install (recommended during development)

1. Create/activate a virtualenv.
2. Install the project in editable mode: `pip install -e '.[dev]'`
3. Run an example: `python examples/world_simulation.py`
4. Run a config via the CLI: `python -m bsim examples/configs/ecology_predator_prey.yaml`

Option B: Without installing

- Run with the source path on `PYTHONPATH` so Python can find the `src` layout, e.g.:
  - `PYTHONPATH=src python examples/world_simulation.py`
  - `PYTHONPATH=src python -m bsim examples/configs/neuro_single_neuron.yaml`

SimUI notes
-----------

- SimUI requires UI deps: `pip install -e '.[ui]'`
- SimUI mounts at `http://localhost:<port>/ui/` by default.
