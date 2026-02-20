"""
Demonstrates the Python-first SimUI Interface with a BioWorld.

Run after installing UI extras:
    pip install -e '.[ui]'
    python examples/ui_demo.py

Or:
    PYTHONPATH=src python examples/ui_demo.py
"""

from __future__ import annotations

import biosim


def main() -> None:
    world = biosim.BioWorld()

    class TS(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._points = []

        def reset(self):
            self._points = []

        def advance_to(self, t: float) -> None:
            self._points.append([t, len(self._points)])

        def get_outputs(self):
            return {}

        def visualize(self):
            return {"render": "timeseries", "data": {"series": [{"name": "i", "points": self._points}]}}

    world.add_biomodule("ts", TS())

    from biosim.simui import Interface, Number, Button, EventLog, VisualsPanel

    ui = Interface(
        world,
        title="BioSim UI",
        controls=[Number("duration", 5, label="Duration", minimum=0.1), Number("tick_dt", 0.1, label="tick_dt", step=0.1), Button("Run")],
        outputs=[EventLog(limit=200), VisualsPanel(refresh="auto", interval_ms=800)],
    )
    ui.launch(port=7861)


if __name__ == "__main__":
    main()
