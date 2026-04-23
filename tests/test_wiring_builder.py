import pytest


def test_wiring_builder_connects_by_names_and_topics(biosim):
    calls = {"lgn": 0, "sc": 0}
    scalar = biosim.SignalSpec.scalar(dtype="float64")

    class Eye(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"visual_stream": scalar}

        def advance_window(self, _start: float, t: float) -> None:
            self._outputs = {"visual_stream": biosim.ScalarSignal(source="eye", name="visual_stream", value=t, emitted_at=t)}

        def get_outputs(self):
            return dict(self._outputs)

    class LGN(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def inputs(self):
            return {"retina": scalar}

        def outputs(self):
            return {"thalamus": scalar}

        def set_inputs(self, signals):
            if "retina" in signals:
                calls["lgn"] += 1
                sig = signals["retina"]
                self._outputs = {
                    "thalamus": biosim.ScalarSignal(
                        source="lgn",
                        name="thalamus",
                        value=sig.value,
                        emitted_at=sig.emitted_at,
                    )
                }

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return dict(self._outputs)

    class SC(biosim.BioModule):
        def __init__(self):
            pass

        def inputs(self):
            return {"vision": scalar}

        def set_inputs(self, signals):
            if "vision" in signals:
                calls["sc"] += 1

        def advance_window(self, _start: float, t: float) -> None:
            return

        def get_outputs(self):
            return {}

    world = biosim.BioWorld(communication_step=0.1)
    wb = biosim.WiringBuilder(world)
    wb.add("eye", Eye()).add("lgn", LGN()).add("sc", SC())
    wb.connect("eye.visual_stream", ["lgn.retina"])  # Eye -> LGN
    wb.connect("lgn.thalamus", ["sc.vision"]).apply()  # LGN -> SC

    world.run(duration=0.3, tick_dt=0.1)

    assert calls["lgn"] >= 1
    assert calls["sc"] >= 1
