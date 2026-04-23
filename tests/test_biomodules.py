from __future__ import annotations

from biosim import ScalarSignal, SignalSpec


def test_setup_called_and_outputs_available(biosim):
    seen = {"setup": 0}

    class TestModule(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def setup(self, config=None):
            seen["setup"] += 1

        def outputs(self):
            return {"out": SignalSpec.scalar(dtype="float64")}

        def advance_window(self, start: float, end: float) -> None:
            self._outputs = {"out": ScalarSignal(source="test", name="out", value=end, emitted_at=end)}

        def get_outputs(self):
            return dict(self._outputs)

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("test", TestModule())
    world.run(duration=0.1, tick_dt=0.1)

    assert seen["setup"] == 1
    outputs = world.get_outputs("test")
    assert "out" in outputs


def test_branch_round_trip_restores_module_state(biosim):
    class Counter(biosim.BioModule):
        def __init__(self):
            self.value = 0
            self._outputs = {}

        def outputs(self):
            return {"count": SignalSpec.scalar(dtype="int64")}

        def advance_window(self, start: float, end: float) -> None:
            self.value += 1
            self._outputs = {"count": ScalarSignal(source="counter", name="count", value=self.value, emitted_at=end)}

        def get_outputs(self):
            return dict(self._outputs)

        def snapshot(self):
            return {"value": self.value}

        def restore(self, snapshot):
            self.value = int(snapshot["value"])

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("counter", Counter())
    world.run(duration=0.2)

    snapshot = world.snapshot()
    branched = world.branch()

    world.run(duration=0.1)
    branched.restore(snapshot)

    assert world.get_outputs("counter")["count"].value == 3
    assert branched.get_outputs("counter")["count"].value == 2

