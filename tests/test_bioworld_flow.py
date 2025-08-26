import pytest


def test_event_flow_with_custom_solver(bsim, custom_solver):
    world = bsim.BioWorld(solver=custom_solver)
    events = []

    def listener(ev, payload):
        events.append((ev, payload))

    world.on(listener)
    result = world.simulate(steps=3, dt=0.5)

    assert result["steps"] == 3
    assert result["time"] == pytest.approx(1.5)

    assert len(events) >= 5
    assert events[0][0] == bsim.BioWorldEvent.LOADED
    assert events[1][0] == bsim.BioWorldEvent.BEFORE_SIMULATION
    step_events = [e for e in events if e[0] == bsim.BioWorldEvent.STEP]
    assert len(step_events) == 3
    assert [p["i"] for _, p in step_events] == [0, 1, 2]
    assert [p["t"] for _, p in step_events] == [0.5, 1.0, 1.5]
    assert events[-1][0] == bsim.BioWorldEvent.AFTER_SIMULATION


def test_ready_made_fixed_step_solver(bsim):
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    steps = []

    def listener(ev, payload):
        if ev == bsim.BioWorldEvent.STEP:
            steps.append(payload["t"])

    world.on(listener)
    result = world.simulate(steps=2, dt=0.1)
    assert steps == [0.1, 0.2]
    assert result["steps"] == 2
    assert result["time"] == pytest.approx(0.2)
