from __future__ import annotations

import threading
import time

import pytest

from biosim import ScalarSignal, SignalSpec


def _ticker_module(biosim):
    class Ticker(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"out": SignalSpec.scalar(dtype="float64")}

        def advance_window(self, start: float, end: float) -> None:
            self._outputs = {"out": ScalarSignal(source="ticker", name="out", value=end, emitted_at=end)}

        def get_outputs(self):
            return dict(self._outputs)

    return Ticker()


def test_run_emits_ticks(biosim):
    events = []
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("ticker", _ticker_module(biosim))

    def listener(ev, payload):
        events.append((ev, payload))

    world.on(listener)
    world.run(duration=0.3, tick_dt=0.1)

    assert events[0][0] == biosim.WorldEvent.STARTED
    started_payload = events[0][1]
    assert started_payload["start"] == 0.0
    assert started_payload["end"] == pytest.approx(0.3)
    assert started_payload["duration"] == pytest.approx(0.3)
    assert started_payload["progress"] == 0.0
    assert started_payload["progress_pct"] == 0.0
    assert started_payload["remaining"] == pytest.approx(0.3)

    tick_events = [e for e in events if e[0] == biosim.WorldEvent.TICK]
    assert [round(p["t"], 2) for _, p in tick_events] == [0.1, 0.2, 0.3]
    assert tick_events[-1][1]["progress_pct"] == pytest.approx(100.0)
    assert events[-1][0] == biosim.WorldEvent.FINISHED


def test_request_stop_emits_stopped(biosim):
    seen = []
    stopped_payloads = []
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("ticker", _ticker_module(biosim))

    def listener(ev, payload):
        seen.append(ev)
        if ev == biosim.WorldEvent.STOPPED:
            stopped_payloads.append(payload)
        if ev == biosim.WorldEvent.TICK:
            world.request_stop()

    world.on(listener)
    world.run(duration=10.0, tick_dt=0.1)

    assert biosim.WorldEvent.STOPPED in seen
    assert len(stopped_payloads) == 1
    assert stopped_payloads[0]["progress_pct"] < 100.0


def test_request_pause_blocks_until_resume(biosim):
    about_to_tick = threading.Event()
    done = threading.Event()
    world = biosim.BioWorld(communication_step=0.1)
    world.add_biomodule("ticker", _ticker_module(biosim))

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

