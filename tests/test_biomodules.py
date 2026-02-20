import pytest


def test_min_dt_required(biosim):
    class BadModule(biosim.BioModule):
        def advance_to(self, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld()
    with pytest.raises(ValueError):
        world.add_biomodule("bad", BadModule())


def test_setup_called_and_outputs_available(biosim):
    seen = {"setup": 0}

    class TestModule(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def setup(self, config=None):
            seen["setup"] += 1

        def advance_to(self, t: float) -> None:
            self._outputs = {"out": biosim.BioSignal(source="test", name="out", value=t, time=t)}

        def get_outputs(self):
            return dict(self._outputs)

    world = biosim.BioWorld()
    world.add_biomodule("test", TestModule())
    world.run(duration=0.1, tick_dt=0.1)

    assert seen["setup"] == 1
    outputs = world.get_outputs("test")
    assert "out" in outputs
