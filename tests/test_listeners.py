
def test_listener_on_off(biosim):
    world = biosim.BioWorld(communication_step=0.1)
    called = {"n": 0}

    class Ticker(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"out": biosim.SignalSpec.scalar(dtype="float64")}

        def advance_window(self, _start: float, t: float) -> None:
            self._outputs = {"out": biosim.ScalarSignal(source="ticker", name="out", value=t, emitted_at=t)}

        def get_outputs(self):
            return dict(self._outputs)

    world.add_biomodule("ticker", Ticker())

    def listener(_ev, _payload):
        called["n"] += 1

    world.on(listener)
    world.off(listener)
    world.run(duration=0.1)
    assert called["n"] == 0
