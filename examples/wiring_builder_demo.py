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
        self._outputs = {}

    def outputs(self):
        return {"visual_stream": biosim.SignalSpec.scalar(dtype="float64")}

    def advance_window(self, start: float, end: float) -> None:
        self._outputs = {
            "visual_stream": biosim.ScalarSignal(source="eye", name="visual_stream", value=end, emitted_at=end)
        }

    def get_outputs(self):
        return dict(self._outputs)


class LGN(biosim.BioModule):
    def __init__(self):
        self._outputs = {}

    def inputs(self):
        return {"retina": biosim.SignalSpec.scalar(dtype="float64", max_age=0.2)}

    def outputs(self):
        return {"thalamus": biosim.SignalSpec.scalar(dtype="float64")}

    def set_inputs(self, signals):
        if "retina" in signals:
            sig = signals["retina"]
            self._outputs = {
                "thalamus": biosim.ScalarSignal(source="lgn", name="thalamus", value=sig.value, emitted_at=sig.emitted_at)
            }

    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self):
        return dict(self._outputs)


class SC(biosim.BioModule):
    def inputs(self):
        return {"vision": biosim.SignalSpec.scalar(dtype="float64", max_age=0.2)}

    def set_inputs(self, signals):
        if "vision" in signals:
            print("[SC] vision:", signals["vision"].value)

    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self):
        return {}


def main() -> None:
    world = biosim.BioWorld(communication_step=0.1)
    eye, lgn, sc = Eye(), LGN(), SC()

    wb = biosim.WiringBuilder(world)
    wb.add("eye", eye).add("lgn", lgn).add("sc", sc)
    wb.connect("eye.visual_stream", ["lgn.retina", "sc.vision"]).apply()

    world.run(duration=0.3, tick_dt=0.1)


if __name__ == "__main__":
    main()

