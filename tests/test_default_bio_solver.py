import pytest


def test_default_bio_solver_temperature_only(bsim):
    # Increase temperature by 1.0 per step via delta_per_step
    solver = bsim.DefaultBioSolver(
        temperature=bsim.TemperatureParams(initial=0.0, delta_per_step=1.0)
    )
    world = bsim.BioWorld(solver=solver)
    events = []

    def listener(ev, payload):
        events.append((ev, payload))

    world.on(listener)
    result = world.simulate(steps=3, dt=0.5)

    # Event flow preserved and STEP count correct
    assert events[0][0] == bsim.BioWorldEvent.LOADED
    step_events = [e for e in events if e[0] == bsim.BioWorldEvent.STEP]
    assert len(step_events) == 3

    # Final time and temperature
    assert result["time"] == pytest.approx(1.5)
    assert result["steps"] == 3
    assert result["temperature"] == pytest.approx(3.0)


def test_default_bio_solver_water_and_oxygen_with_bounds(bsim):
    # Water and oxygen decay with clamping to [0, 1]
    water = bsim.ScalarRateParams(name="water", initial=1.0, rate_per_time=-0.6, bounds=(0.0, 1.0))
    oxygen = bsim.ScalarRateParams(name="oxygen", initial=0.3, rate_per_time=-0.2, bounds=(0.0, 1.0))
    solver = bsim.DefaultBioSolver(water=water, oxygen=oxygen)
    world = bsim.BioWorld(solver=solver)

    result = world.simulate(steps=2, dt=1.0)

    # Water would be 1.0 - 1.2 -> clamped to 0.0
    assert result["water"] == pytest.approx(0.0)
    # Oxygen: 0.3 - 0.2*2 = -0.1 -> clamped to 0.0
    assert result["oxygen"] == pytest.approx(0.0)
    # Time advances as usual
    assert result["time"] == pytest.approx(2.0)
