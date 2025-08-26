import pytest


def test_biosignal_routing_eye_to_lgn_to_sc(bsim):
    calls = {"lgn": 0, "sc": 0}

    class Eye(bsim.BioModule):
        def subscriptions(self):
            return {bsim.BioWorldEvent.STEP}

        def on_event(self, event, payload, world):
            world.publish_biosignal(self, topic="vision", payload={"t": payload.get("t")})

    class LGN(bsim.BioModule):
        def on_event(self, event, payload, world):
            pass

        def on_signal(self, topic, payload, source, world):
            if topic == "vision":
                calls["lgn"] += 1
                world.publish_biosignal(self, topic="thalamus", payload={"relay": payload})

    class SC(bsim.BioModule):
        def on_event(self, event, payload, world):
            pass

        def on_signal(self, topic, payload, source, world):
            if topic == "thalamus":
                calls["sc"] += 1

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    eye, lgn, sc = Eye(), LGN(), SC()
    world.add_biomodule(eye)
    world.add_biomodule(lgn)
    world.add_biomodule(sc)
    world.connect_biomodules(eye, "vision", lgn)
    world.connect_biomodules(lgn, "thalamus", sc)

    world.simulate(steps=2, dt=0.1)

    assert calls["lgn"] == 2
    assert calls["sc"] == 2


def test_biosignal_is_not_broadcast_without_connection(bsim):
    received = {"a": 0, "b": 0}

    class A(bsim.BioModule):
        def subscriptions(self):
            return {bsim.BioWorldEvent.STEP}

        def on_event(self, event, payload, world):
            world.publish_biosignal(self, topic="sig", payload={"t": payload.get("t")})

    class B(bsim.BioModule):
        def on_signal(self, topic, payload, source, world):
            received["b"] += 1

    class C(bsim.BioModule):
        def on_signal(self, topic, payload, source, world):
            received["a"] += 1

    world = bsim.BioWorld(solver=bsim.FixedStepSolver())
    a, b, c = A(), B(), C()
    world.add_biomodule(a)
    world.add_biomodule(b)
    world.add_biomodule(c)
    world.connect_biomodules(a, "sig", b)

    world.simulate(steps=1, dt=0.1)

    assert received["b"] == 1
    assert received["a"] == 0
