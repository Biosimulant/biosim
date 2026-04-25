import pytest


def test_error_event_and_finished_emitted(biosim):
    class Boom(biosim.BioModule):
        def __init__(self):
            pass

        def advance_window(self, _start: float, t: float) -> None:
            raise RuntimeError("boom")

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("boom", Boom())
    seen = []

    def listener(ev, _payload):
        seen.append(ev)

    world.on(listener)
    with pytest.raises(RuntimeError):
        world.run(duration=0.1)

    assert biosim.WorldEvent.ERROR in seen
    assert biosim.WorldEvent.FINISHED in seen
