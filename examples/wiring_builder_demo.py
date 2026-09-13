"""
Demonstrates WiringBuilder to declaratively connect modules in code.

Run:
    pip install -e .
    python examples/wiring_builder_demo.py
"""

from __future__ import annotations

import biosimulant as biosim


class Eye(biosim.BioModule):
    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def outputs(self):
        return {"visual_stream": biosim.SignalSpec.scalar(dtype="float64")}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        assert context.window_end is not None
        return {"visual_stream": context.window_end}


class LGN(biosim.BioModule):
    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def inputs(self):
        return {"retina": biosim.SignalSpec.scalar(dtype="float64", max_age=0.2)}

    def outputs(self):
        return {"thalamus": biosim.SignalSpec.scalar(dtype="float64")}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        signal = inputs.get("retina")
        return {} if signal is None else {"thalamus": signal.value}


class SC(biosim.BioModule):
    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def inputs(self):
        return {"vision": biosim.SignalSpec.scalar(dtype="float64", max_age=0.2)}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        signal = inputs.get("vision")
        if signal is not None:
            print("[SC] vision:", signal.value)
        return {}


def main() -> None:
    world = biosim.BioWorld(communication_step=0.1)
    eye, lgn, sc = Eye(), LGN(), SC()

    wb = biosim.WiringBuilder(world)
    wb.add("eye", eye).add("lgn", lgn).add("sc", sc)
    wb.connect("eye.visual_stream", ["lgn.retina", "sc.vision"]).apply()

    world.run(duration=0.3)


if __name__ == "__main__":
    main()
