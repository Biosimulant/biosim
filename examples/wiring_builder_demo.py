"""
Demonstrates WiringBuilder to declaratively connect modules in code.

Run:
    pip install -e .
    python examples/wiring_builder_demo.py
"""

from __future__ import annotations

import biosim


class Eye(biosim.BioModule):
    def __init__(self):
        self.min_dt = 0.1
        self._outputs = {}

    def outputs(self):
        return {"visual_stream"}

    def advance_to(self, t: float) -> None:
        self._outputs = {
            "visual_stream": biosim.BioSignal(source="eye", name="visual_stream", value=t, time=t)
        }

    def get_outputs(self):
        return dict(self._outputs)


class LGN(biosim.BioModule):
    def __init__(self):
        self.min_dt = 0.1
        self._outputs = {}

    def inputs(self):
        return {"retina"}

    def outputs(self):
        return {"thalamus"}

    def set_inputs(self, signals):
        if "retina" in signals:
            sig = signals["retina"]
            self._outputs = {
                "thalamus": biosim.BioSignal(source="lgn", name="thalamus", value=sig.value, time=sig.time)
            }

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        return dict(self._outputs)


class SC(biosim.BioModule):
    def __init__(self):
        self.min_dt = 0.1

    def inputs(self):
        return {"vision"}

    def set_inputs(self, signals):
        if "vision" in signals:
            print("[SC] vision:", signals["vision"].value)

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        return {}


def main() -> None:
    world = biosim.BioWorld()
    eye, lgn, sc = Eye(), LGN(), SC()

    wb = biosim.WiringBuilder(world)
    wb.add("eye", eye, priority=2).add("lgn", lgn, priority=1).add("sc", sc)
    wb.connect("eye.visual_stream", ["lgn.retina", "sc.vision"]).apply()

    world.run(duration=0.2, tick_dt=0.1)


if __name__ == "__main__":
    main()
