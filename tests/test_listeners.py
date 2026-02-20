
def test_listener_on_off(biosim):
    world = biosim.BioWorld()
    called = {"n": 0}

    class Ticker(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def advance_to(self, t: float) -> None:
            self._outputs = {"out": biosim.BioSignal(source="ticker", name="out", value=t, time=t)}

        def get_outputs(self):
            return dict(self._outputs)

    world.add_biomodule("ticker", Ticker())

    def listener(_ev, _payload):
        called["n"] += 1

    world.on(listener)
    world.off(listener)
    world.run(duration=0.1, tick_dt=0.1)
    assert called["n"] == 0
