import pytest


def test_wiring_builder_connects_by_names_and_topics(bsim):
    calls = {"lgn": 0, "sc": 0}

    class Eye(bsim.BioModule):
        def subscriptions(self):
            return {bsim.BioWorldEvent.STEP}

        def on_event(self, event, payload, world):
            world.publish_biosignal(self, topic="visual_stream", payload={"t": payload.get("t")})

    class LGN(bsim.BioModule):
        def on_signal(self, topic, payload, source, world):
            if topic == "visual_stream":
                calls["lgn"] += 1
                world.publish_biosignal(self, topic="thalamus", payload=payload)

    class SC(bsim.BioModule):
        def on_signal(self, topic, payload, source, world):
            if topic == "thalamus":
                calls["sc"] += 1

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    wb = bsim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
    wb.connect("eye.out.visual_stream", ["lgn.in.retina"])  # Eye -> LGN
    wb.connect("lgn.out.thalamus", ["sc.in.vision"]).apply()  # LGN -> SC

    world.simulate(steps=2, dt=0.1)

    assert calls["lgn"] == 2
    assert calls["sc"] == 2
