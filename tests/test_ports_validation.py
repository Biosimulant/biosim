import pytest


def test_port_validation_success_with_declared_ports(bsim):
    class Eye(bsim.BioModule):
        def outputs(self):
            return {"visual_stream"}

        def subscriptions(self):
            return {bsim.BioWorldEvent.STEP}

        def on_event(self, event, payload, world):
            world.publish_biosignal(self, topic="visual_stream", payload={})

    class LGN(bsim.BioModule):
        def inputs(self):
            return {"retina"}

        def on_signal(self, topic, payload, source, world):
            pass

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    wb = bsim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN())
    wb.connect("eye.out.visual_stream", ["lgn.in.retina"]).apply()
    world.simulate(steps=1, dt=0.1)


def test_port_validation_raises_for_unknown_output(bsim):
    class Eye(bsim.BioModule):
        def outputs(self):
            return {"visual_stream"}

    class LGN(bsim.BioModule):
        def inputs(self):
            return {"retina"}

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    wb = bsim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN())

    with pytest.raises(ValueError):
        wb.connect("eye.out.nope", ["lgn.in.retina"]).apply()


def test_port_validation_raises_for_unknown_input(bsim):
    class Eye(bsim.BioModule):
        def outputs(self):
            return {"visual_stream"}

    class LGN(bsim.BioModule):
        def inputs(self):
            return {"retina"}

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    wb = bsim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN())

    with pytest.raises(ValueError):
        wb.connect("eye.out.visual_stream", ["lgn.in.unknown"]).apply()
