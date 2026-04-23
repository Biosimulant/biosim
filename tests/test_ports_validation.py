import pytest


def test_port_validation_success_with_declared_ports(biosim):
    scalar = biosim.SignalSpec.scalar(dtype="float64")

    class Eye(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"visual_stream": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            self._outputs = {
                "visual_stream": biosim.ScalarSignal(source="eye", name="visual_stream", value=t, emitted_at=t, spec=scalar)
            }

        def get_outputs(self):
            return dict(self._outputs)

    class LGN(biosim.BioModule):
        def __init__(self):
            pass

        def inputs(self):
            return {"retina": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    wb = biosim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN())
    wb.connect("eye.visual_stream", ["lgn.retina"]).apply()
    world.run(duration=0.1, tick_dt=0.1)


def test_port_validation_raises_for_unknown_output(biosim):
    scalar = biosim.SignalSpec.scalar(dtype="float64")

    class Eye(biosim.BioModule):
        def __init__(self):
            pass

        def outputs(self):
            return {"visual_stream": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    class LGN(biosim.BioModule):
        def __init__(self):
            pass

        def inputs(self):
            return {"retina": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    wb = biosim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN())

    with pytest.raises(ValueError):
        wb.connect("eye.nope", ["lgn.retina"]).apply()


def test_port_validation_raises_for_unknown_input(biosim):
    scalar = biosim.SignalSpec.scalar(dtype="float64")

    class Eye(biosim.BioModule):
        def __init__(self):
            pass

        def outputs(self):
            return {"visual_stream": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    class LGN(biosim.BioModule):
        def __init__(self):
            pass

        def inputs(self):
            return {"retina": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    wb = biosim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN())

    with pytest.raises(ValueError):
        wb.connect("eye.visual_stream", ["lgn.unknown"]).apply()


def test_port_routing_supports_dst_port_mapping(biosim):
    received = {"count": 0}
    scalar = biosim.SignalSpec.scalar(dtype="float64")

    class Src(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"out_port": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            self._outputs = {"out_port": biosim.ScalarSignal(source="src", name="out_port", value=t, emitted_at=t, spec=scalar)}

        def get_outputs(self):
            return dict(self._outputs)

    class Dst(biosim.BioModule):
        def __init__(self):
            pass

        def inputs(self):
            return {"in_port": scalar}

        def set_inputs(self, signals):
            if "in_port" in signals:
                received["count"] += 1

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    wb = biosim.WiringBuilder(world)
    wb.add("src", Src()).add("dst", Dst())

    wb.connect("src.out_port", ["dst.in_port"]).apply()
    world.run(duration=0.3, tick_dt=0.1)

    assert received["count"] >= 1
