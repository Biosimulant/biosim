import threading
import time

import pytest


def test_run_emits_ticks(biosim):
    events = []

    class Ticker(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._t = 0.0
            self._outputs = {}

        def advance_to(self, t: float) -> None:
            self._t = t
            self._outputs = {
                "out": biosim.BioSignal(
                    source="ticker",
                    name="out",
                    value=t,
                    time=t,
                )
            }

        def get_outputs(self):
            return dict(self._outputs)

    world = biosim.BioWorld()
    world.add_biomodule("ticker", Ticker())

    def listener(ev, payload):
        events.append((ev, payload))

    world.on(listener)
    world.run(duration=0.3, tick_dt=0.1)

    assert events[0][0] == biosim.WorldEvent.STARTED
    tick_events = [e for e in events if e[0] == biosim.WorldEvent.TICK]
    assert [round(p["t"], 2) for _, p in tick_events] == [0.1, 0.2, 0.3]
    assert events[-1][0] == biosim.WorldEvent.FINISHED


def test_request_stop_emits_stopped(biosim):
    seen = []

    class Ticker(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def advance_to(self, t: float) -> None:
            self._outputs = {"out": biosim.BioSignal(source="ticker", name="out", value=t, time=t)}

        def get_outputs(self):
            return dict(self._outputs)

    world = biosim.BioWorld()
    world.add_biomodule("ticker", Ticker())

    def listener(ev, payload):
        seen.append(ev)
        if ev == biosim.WorldEvent.TICK:
            world.request_stop()

    world.on(listener)
    world.run(duration=10.0, tick_dt=0.1)

    assert biosim.WorldEvent.STOPPED in seen


def test_request_pause_blocks_until_resume(biosim):
    about_to_tick = threading.Event()
    done = threading.Event()

    class Ticker(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._outputs = {}

        def advance_to(self, t: float) -> None:
            self._outputs = {"out": biosim.BioSignal(source="ticker", name="out", value=t, time=t)}

        def get_outputs(self):
            return dict(self._outputs)

    world = biosim.BioWorld()
    world.add_biomodule("ticker", Ticker())

    def listener(ev, payload):
        if ev == biosim.WorldEvent.TICK and not about_to_tick.is_set():
            about_to_tick.set()
            world.request_pause()

    world.on(listener)

    def _run():
        world.run(duration=1.0, tick_dt=0.1)
        done.set()

    t = threading.Thread(target=_run, daemon=True)
    t.start()

    assert about_to_tick.wait(timeout=1.0)
    time.sleep(0.05)
    assert not done.is_set()

    world.request_resume()
    assert done.wait(timeout=2.0)
