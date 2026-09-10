"""
Minimal demo showing module-provided visuals and world collection.

Run:
    pip install -e .
    python examples/visuals_demo.py

Or without installing:
    PYTHONPATH=src python examples/visuals_demo.py
"""

from __future__ import annotations

import sys

try:
    import biosimulant as biosim
except ModuleNotFoundError:
    sys.stderr.write(
        "Could not import 'biosimulant'. Did you run 'pip install -e .'?\n"
        "Alternatively, run with 'PYTHONPATH=src'.\n"
    )
    raise


class StepSeries(biosim.BioModule):
    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def __init__(self) -> None:
        self._points: list[list[float]] = []

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        assert context.window_end is not None
        self._points.append([context.window_end, len(self._points)])
        return {}

    def visualize(self):
        return {
            "render": "timeseries",
            "data": {"series": [{"name": "step_index", "points": self._points}]},
        }


def main() -> None:
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("step_series", StepSeries())
    world.run(duration=0.5)

    visuals = world.collect_visuals()
    print("Collected visuals:")
    for entry in visuals:
        print(entry["module"], "->", entry["visuals"])


if __name__ == "__main__":
    main()
