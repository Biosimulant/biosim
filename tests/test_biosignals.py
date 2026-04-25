from __future__ import annotations

from biosim import ScalarSignal, SignalSpec


def test_biosignal_routing_eye_to_lgn_to_sc(biosim):
    calls = {"lgn": 0, "sc": 0}

    class Eye(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"vision": SignalSpec.scalar(dtype="float64")}

        def advance_window(self, start: float, end: float) -> None:
            self._outputs = {"vision": ScalarSignal(source="eye", name="vision", value=end, emitted_at=end)}

        def get_outputs(self):
            return dict(self._outputs)

    class LGN(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def inputs(self):
            return {"vision": SignalSpec.scalar(dtype="float64", max_age=0.2)}

        def outputs(self):
            return {"thalamus": SignalSpec.scalar(dtype="float64")}

        def set_inputs(self, signals):
            if "vision" in signals:
                calls["lgn"] += 1
                self._outputs = {
                    "thalamus": ScalarSignal(
                        source="lgn",
                        name="thalamus",
                        value=signals["vision"].value,
                        emitted_at=signals["vision"].emitted_at,
                    )
                }

        def advance_window(self, start: float, end: float) -> None:
            return

        def get_outputs(self):
            return dict(self._outputs)

    class SC(biosim.BioModule):
        def inputs(self):
            return {"thalamus": SignalSpec.scalar(dtype="float64", max_age=0.2)}

        def set_inputs(self, signals):
            if "thalamus" in signals:
                calls["sc"] += 1

        def advance_window(self, start: float, end: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("eye", Eye())
    world.add_biomodule("lgn", LGN())
    world.add_biomodule("sc", SC())
    world.connect("eye.vision", "lgn.vision")
    world.connect("lgn.thalamus", "sc.thalamus")

    world.run(duration=0.3)

    assert calls["lgn"] >= 1
    assert calls["sc"] >= 1


def test_biosignal_is_not_broadcast_without_connection(biosim):
    received = {"b": 0, "c": 0}

    class A(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"sig": SignalSpec.scalar(dtype="float64")}

        def advance_window(self, start: float, end: float) -> None:
            self._outputs = {"sig": ScalarSignal(source="a", name="sig", value=end, emitted_at=end)}

        def get_outputs(self):
            return dict(self._outputs)

    class B(biosim.BioModule):
        def inputs(self):
            return {"sig": SignalSpec.scalar(dtype="float64")}

        def set_inputs(self, signals):
            received["b"] += 1

        def advance_window(self, start: float, end: float) -> None:
            return

        def get_outputs(self):
            return {}

    class C(biosim.BioModule):
        def set_inputs(self, signals):
            received["c"] += 1

        def advance_window(self, start: float, end: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("a", A())
    world.add_biomodule("b", B())
    world.add_biomodule("c", C())
    world.connect("a.sig", "b.sig")

    world.run(duration=0.2)

    assert received["b"] >= 1
    assert received["c"] == 0
