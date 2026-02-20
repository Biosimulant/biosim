import pytest


def test_wiring_builder_connects_by_names_and_topics(biosim):
    calls = {"lgn": 0, "sc": 0}

    class Eye(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def outputs(self):
            return {"visual_stream"}

        def advance_to(self, t: float) -> None:
            self._outputs = {"visual_stream": biosim.BioSignal(source="eye", name="visual_stream", value=t, time=t)}

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
                calls["lgn"] += 1
                sig = signals["retina"]
                self._outputs = {"thalamus": biosim.BioSignal(source="lgn", name="thalamus", value=sig.value, time=sig.time)}

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
                calls["sc"] += 1

        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld()
    wb = biosim.WiringBuilder(world)
    wb.add("eye", Eye(), priority=2).add("lgn", LGN(), priority=1).add("sc", SC(), priority=0)
    wb.connect("eye.visual_stream", ["lgn.retina"])  # Eye -> LGN
    wb.connect("lgn.thalamus", ["sc.vision"]).apply()  # LGN -> SC

    world.run(duration=0.2, tick_dt=0.1)

    assert calls["lgn"] >= 1
    assert calls["sc"] >= 1
