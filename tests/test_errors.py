import pytest


def test_error_event_and_after_simulation_emitted(bsim, failing_solver):
    world = bsim.BioWorld(solver=failing_solver)
    seen = []

    def listener(ev, _payload):
        seen.append(ev)

    world.on(listener)
    with pytest.raises(RuntimeError):
        world.simulate(steps=2, dt=0.1)

    assert bsim.BioWorldEvent.ERROR in seen
    assert bsim.BioWorldEvent.AFTER_SIMULATION in seen
