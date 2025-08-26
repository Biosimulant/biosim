def test_listener_on_off(bsim):
    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    called = {"n": 0}

    def listener(_ev, _payload):
        called["n"] += 1

    world.on(listener)
    world.off(listener)
    world.simulate(steps=1, dt=0.1)
    assert called["n"] == 0
