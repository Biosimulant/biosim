Examples
========

Quick index
-----------

Core usage
- `basic_usage.py`: Prints the installed package version to verify imports.
- `world_simulation.py`: Shows BioWorld orchestration and biosignal routing.
- `wiring_builder_demo.py`: Demonstrates `WiringBuilder` (including port validation).
- `visuals_demo.py`: Minimal example of module-provided visuals + `world.collect_visuals()`.

SimUI
- `ui_demo.py`: Minimal SimUI demo (requires UI extras).
- `multi_module_ui_demo.py`: Multi-module visuals demo in SimUI (large defaults).

Advanced models, spaces, and domain demos
-----------------------------------------

For neuroscience/ecology demos, wiring configs, and model-pack templates, see the companion repo:

- https://github.com/Biosimulant/biomodels

How to run
----------

Option A: Editable install (recommended during development)

1. Create/activate a virtualenv.
2. Install the project in editable mode: `pip install -e '.[dev]'`
3. Run an example: `python examples/world_simulation.py`

Option B: Without installing

- Run with the source path on `PYTHONPATH` so Python can find the `src` layout, e.g.:
  - `PYTHONPATH=src python examples/world_simulation.py`
  - `PYTHONPATH=src python -m bsim <path-to-wiring.yaml>`

SimUI notes
-----------

- SimUI requires UI deps: `pip install -e '.[ui]'`
- SimUI mounts at `http://localhost:<port>/ui/` by default.
