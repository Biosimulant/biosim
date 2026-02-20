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
    import biosim
except ModuleNotFoundError:
    sys.stderr.write(
        "Could not import 'biosim'. Did you run 'pip install -e .'?\n"
        "Alternatively, run with 'PYTHONPATH=src'.\n"
    )
    raise


class StepSeries(biosim.BioModule):
    def __init__(self) -> None:
        self.min_dt = 0.1
        self._points: list[list[float]] = []

    def advance_to(self, t: float) -> None:
        self._points.append([t, len(self._points)])

    def get_outputs(self):
        return {}

    def visualize(self):
        return {
            "render": "timeseries",
            "data": {"series": [{"name": "step_index", "points": self._points}]},
        }


def main() -> None:
    world = biosim.BioWorld()
    world.add_biomodule("step_series", StepSeries())
    world.run(duration=0.5, tick_dt=0.1)

    visuals = world.collect_visuals()
    print("Collected visuals:")
    for entry in visuals:
        print(entry["module"], "->", entry["visuals"])


if __name__ == "__main__":
    main()
