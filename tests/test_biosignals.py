import pytest


def test_biosignal_routing_eye_to_lgn_to_sc(biosim):
    calls = {"lgn": 0, "sc": 0}

    class Eye(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def advance_to(self, t: float) -> None:
            self._outputs = {
                "vision": biosim.BioSignal(source="eye", name="vision", value=t, time=t)
            }

        def get_outputs(self):
            return dict(self._outputs)

    class LGN(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def set_inputs(self, signals):
            if "vision" in signals:
                calls["lgn"] += 1
                self._outputs = {
                    "thalamus": biosim.BioSignal(
                        source="lgn", name="thalamus", value=signals["vision"].value, time=signals["vision"].time
                    )
                }

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return dict(self._outputs)

    class SC(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def set_inputs(self, signals):
            if "thalamus" in signals:
                calls["sc"] += 1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld()
    world.add_biomodule("eye", Eye(), priority=2)
    world.add_biomodule("lgn", LGN(), priority=1)
    world.add_biomodule("sc", SC(), priority=0)
    world.connect("eye.vision", "lgn.vision")
    world.connect("lgn.thalamus", "sc.thalamus")

    world.run(duration=0.2, tick_dt=0.1)

    assert calls["lgn"] >= 1
    assert calls["sc"] >= 1


def test_biosignal_is_not_broadcast_without_connection(biosim):
    received = {"b": 0, "c": 0}

    class A(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def advance_to(self, t: float) -> None:
            self._outputs = {"sig": biosim.BioSignal(source="a", name="sig", value=t, time=t)}

        def get_outputs(self):
            return dict(self._outputs)

    class B(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def set_inputs(self, signals):
            received["b"] += 1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    class C(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def set_inputs(self, signals):
            received["c"] += 1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld()
    world.add_biomodule("a", A(), priority=1)
    world.add_biomodule("b", B(), priority=0)
    world.add_biomodule("c", C(), priority=0)
    world.connect("a.sig", "b.sig")

    world.run(duration=0.1, tick_dt=0.1)

    assert received["b"] >= 1
    assert received["c"] == 0
