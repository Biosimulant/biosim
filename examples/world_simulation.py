"""
Demonstrates BioWorld orchestration and signal routing.

Run with:
    pip install -e .
    python examples/world_simulation.py

Or without installing:
    PYTHONPATH=src python examples/world_simulation.py
"""

from __future__ import annotations

import biosim


def print_listener(event: biosim.WorldEvent, payload: dict) -> None:
    print(f"EVENT: {event.value} -> {payload}")


class StepLoggerModule(biosim.BioModule):
    """Example module that advances on its schedule."""

    def advance_window(self, start: float, end: float) -> None:
        print(f"[Module] window [{start:.1f}, {end:.1f}]")

    def get_outputs(self):
        return {}


class Eye(biosim.BioModule):
    """Publishes a vision signal each step."""

    def __init__(self):
        self._outputs = {}

    def outputs(self):
        return {"vision": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def advance_window(self, start: float, end: float) -> None:
        self._outputs = {
            "vision": biosim.RecordSignal(
                source="eye",
                name="vision",
                value={"photon": True},
                emitted_at=end,
                spec=self.outputs()["vision"],
            )
        }

    def get_outputs(self):
        return dict(self._outputs)


class LGN(biosim.BioModule):
    """Receives Eye.vision and relays to thalamus channel."""

    def __init__(self):
        self._outputs = {}

    def inputs(self):
        return {"vision": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def outputs(self):
        return {"thalamus": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def set_inputs(self, signals):
        if "vision" in signals:
            self._outputs = {
                "thalamus": biosim.RecordSignal(
                    source="lgn",
                    name="thalamus",
                    value=signals["vision"].value,
                    emitted_at=signals["vision"].emitted_at,
                    spec=self.outputs()["thalamus"],
                )
            }

    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self):
        return dict(self._outputs)


class SuperiorColliculus(biosim.BioModule):
    """Receives LGN.thalamus signals."""

    def inputs(self):
        return {"thalamus": biosim.SignalSpec.record(schema={"photon": "bool"})}

    def set_inputs(self, signals):
        if "thalamus" in signals:
            print("[SC] received:", signals["thalamus"].value)

    def advance_window(self, start: float, end: float) -> None:
        return

    def get_outputs(self):
        return {}


def main() -> None:
    world = biosim.BioWorld(communication_step=0.1)
    world.on(print_listener)
    world.add_biomodule("logger", StepLoggerModule())
    world.run(duration=0.3, tick_dt=0.1)

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
    bw.run(duration=0.3, tick_dt=0.1)


if __name__ == "__main__":
    main()
