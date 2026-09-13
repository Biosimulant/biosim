"""
Demonstrates BioWorld orchestration and signal routing.

Run with:
    pip install -e .
    python examples/world_simulation.py

Or without installing:
    PYTHONPATH=src python examples/world_simulation.py
"""

from __future__ import annotations

import biosimulant as biosim


def print_listener(event: biosim.WorldEvent, payload: dict) -> None:
    print(f"EVENT: {event.value} -> {payload}")


class StepLoggerModule(biosim.BioModule):
    """Example module that advances on its schedule."""

    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        assert context.window_start is not None and context.window_end is not None
        print(f"[Module] window [{context.window_start:.1f}, {context.window_end:.1f}]")
        return {}


class Eye(biosim.BioModule):
    """Publishes a vision signal each step."""

    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def outputs(self):
        return {"vision": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        return {"vision": {"photon": True}}


class LGN(biosim.BioModule):
    """Receives Eye.vision and relays to thalamus channel."""

    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def inputs(self):
        return {"vision": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def outputs(self):
        return {"thalamus": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        signal = inputs.get("vision")
        return {} if signal is None else {"thalamus": signal.value}


class SuperiorColliculus(biosim.BioModule):
    """Receives LGN.thalamus signals."""

    execution_policy = biosim.ExecutionPolicy.EACH_WINDOW

    def inputs(self):
        return {"thalamus": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def execute(self, inputs, *, context: biosim.ExecutionContext):
        signal = inputs.get("thalamus")
        if signal is not None:
            print("[SC] received:", signal.value)
        return {}


def main() -> None:
    world = biosim.BioWorld(communication_step=0.1)
    world.on(print_listener)
    world.add_biomodule("logger", StepLoggerModule())
    world.run(duration=0.3)

    print("--- Signal routing demo ---")
    bw = biosim.BioWorld(communication_step=0.1)
    eye = Eye()
    lgn = LGN()
    sc = SuperiorColliculus()

    bw.add_biomodule("eye", eye)
    bw.add_biomodule("lgn", lgn)
    bw.add_biomodule("sc", sc)
    bw.connect("eye.vision", "lgn.vision")
    bw.connect("lgn.thalamus", "sc.thalamus")
    bw.run(duration=0.3)


if __name__ == "__main__":
    main()
