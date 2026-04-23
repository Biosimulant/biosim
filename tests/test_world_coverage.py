"""Coverage tests for the V2 communication-step BioWorld."""

from __future__ import annotations

import threading

import pytest

from biosim.world import BioWorld, WorldEvent


def _scalar_spec(biosim, **kwargs):
    return biosim.SignalSpec.scalar(dtype="float64", **kwargs)


def _make_module(biosim):
    class M(biosim.BioModule):
        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    return M()


def test_listener_off_nonexistent(biosim):
    world = BioWorld(communication_step=0.1)

    def dummy(_ev, _data):
        return

    world.off(dummy)


def test_listener_error_is_logged(biosim, caplog):
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))

    def bad_listener(_ev, _data):
        raise RuntimeError("boom")

    world.on(bad_listener)
    world.run(duration=0.1, tick_dt=0.1)

    assert world.current_time == pytest.approx(0.1)
    assert any("world listener raised" in record.message for record in caplog.records)


def test_add_duplicate_module_same_instance_is_allowed(biosim):
    world = BioWorld(communication_step=0.1)
    module = _make_module(biosim)
    world.add_biomodule("m", module)
    world.add_biomodule("m", module)


def test_add_duplicate_module_different_instance_raises(biosim):
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))
    with pytest.raises(ValueError, match="already registered"):
        world.add_biomodule("m", _make_module(biosim))


def test_connect_rejects_bad_references_and_unknown_modules(biosim):
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))

    with pytest.raises(ValueError, match="format"):
        world.connect("m_no_dot", "m.x")
    with pytest.raises(ValueError, match="format"):
        world.connect("m.x", "nodot")
    with pytest.raises(KeyError, match="Unknown source"):
        world.connect("unknown.x", "m.x")
    with pytest.raises(KeyError, match="Unknown target"):
        world.connect("m.x", "unknown.y")


def test_connect_rejects_undeclared_ports(biosim):
    scalar = _scalar_spec(biosim)

    class Src(biosim.BioModule):
        def outputs(self):
            return {"out": scalar}

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    class Dst(biosim.BioModule):
        def inputs(self):
            return {"in": scalar}

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.add_biomodule("dst", Dst())

    with pytest.raises(KeyError, match="Unknown source signal"):
        world.connect("src.missing", "dst.in")
    with pytest.raises(KeyError, match="Unknown target signal"):
        world.connect("src.out", "dst.missing")


def test_run_zero_duration_is_no_op(biosim):
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))
    world.setup()
    world.run(duration=0.0)
    assert world.current_time == 0.0


def test_run_auto_setup_and_tick_payloads(biosim):
    events = []
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))
    world.on(lambda ev, payload: events.append((ev, payload)))

    world.run(duration=0.2)

    assert world.current_time == pytest.approx(0.2)
    assert any(ev == WorldEvent.STARTED for ev, _ in events)
    ticks = [payload for ev, payload in events if ev == WorldEvent.TICK]
    assert ticks
    assert ticks[0]["window_start"] == pytest.approx(0.0)
    assert ticks[0]["window_end"] == pytest.approx(0.1)
    assert any(ev == WorldEvent.FINISHED for ev, _ in events)


def test_request_stop_emits_stopped(biosim):
    events = []
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))

    def listener(ev, _payload):
        events.append(ev)
        if ev == WorldEvent.STARTED:
            world.request_stop()

    world.on(listener)
    world.run(duration=10.0)

    assert WorldEvent.STOPPED in events
    assert world.current_time == pytest.approx(0.0)


def test_request_pause_and_resume_emit_events(biosim):
    events = []
    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", _make_module(biosim))

    def runner():
        world.run(duration=0.3, tick_dt=0.1)

    thread = threading.Thread(target=runner, daemon=True)
    world.on(lambda ev, _payload: events.append(ev))
    thread.start()
    world.request_pause()
    world.request_resume()
    thread.join(timeout=2.0)

    assert WorldEvent.PAUSED in events
    assert WorldEvent.RESUMED in events
    assert not thread.is_alive()


def test_error_event_is_emitted_and_exception_is_reraised(biosim):
    events = []

    class Fail(biosim.BioModule):
        def advance_window(self, start, end):
            raise RuntimeError("boom")

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("bad", Fail())
    world.on(lambda ev, payload: events.append((ev, payload)))

    with pytest.raises(RuntimeError, match="boom"):
        world.run(duration=0.1)

    error_payloads = [payload for ev, payload in events if ev == WorldEvent.ERROR]
    assert len(error_payloads) == 1
    assert isinstance(error_payloads[0]["error"], RuntimeError)


def test_event_signals_deliver_once_per_timestamp_and_reset_on_setup(biosim):
    received = []
    event_spec = biosim.SignalSpec.event(schema={"code": "str"})

    class Src(biosim.BioModule):
        def outputs(self):
            return {"ev": event_spec}

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {
                "ev": biosim.EventSignal(
                    source="src",
                    name="ev",
                    value={"code": "pulse"},
                    emitted_at=0.1,
                    spec=event_spec,
                )
            }

    class Dst(biosim.BioModule):
        def inputs(self):
            return {"ev": event_spec}

        def set_inputs(self, signals):
            if "ev" in signals:
                received.append(signals["ev"].emitted_at)

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.add_biomodule("dst", Dst())
    world.connect("src.ev", "dst.ev")

    world.run(duration=0.3)
    assert received == [0.1]

    world.setup()
    world.run(duration=0.2)
    assert received == [0.1, 0.1]


def test_routed_inputs_preserve_source_timestamp(biosim):
    received = []
    scalar = _scalar_spec(biosim)

    class Src(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def outputs(self):
            return {"x": scalar}

        def advance_window(self, start, end):
            if end <= 0.1 + 1e-12:
                self._outputs = {
                    "x": biosim.ScalarSignal(source="src", name="x", value=end, emitted_at=end, spec=scalar)
                }
            else:
                self._outputs = {}

        def get_outputs(self):
            return dict(self._outputs)

    class Dst(biosim.BioModule):
        def inputs(self):
            return {"x": _scalar_spec(biosim, max_age=1.0)}

        def set_inputs(self, signals):
            sig = signals.get("x")
            if sig is not None:
                received.append(sig.emitted_at)

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.add_biomodule("dst", Dst())
    world.connect("src.x", "dst.x")
    world.run(duration=0.3)

    assert received == [0.1, 0.1]


def test_warns_once_when_state_signal_is_stale(biosim, caplog):
    src_spec = _scalar_spec(biosim)
    dst_spec = _scalar_spec(biosim, max_age=0.05, stale_policy="warn")

    class Src(biosim.BioModule):
        def __init__(self):
            self._outputs = {
                "state": biosim.ScalarSignal(source="src", name="state", value=1.0, emitted_at=0.0, spec=src_spec)
            }

        def outputs(self):
            return {"state": src_spec}

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return dict(self._outputs)

    class Dst(biosim.BioModule):
        def inputs(self):
            return {"state": dst_spec}

        def set_inputs(self, signals):
            return

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.add_biomodule("dst", Dst())
    world.connect("src.state", "dst.state")
    world.run(duration=0.3)

    stale_logs = [record for record in caplog.records if "stale signal read" in record.message]
    assert len(stale_logs) == 1


def test_stale_policy_error_raises(biosim):
    src_spec = _scalar_spec(biosim)
    dst_spec = _scalar_spec(biosim, max_age=0.05, stale_policy="error")

    class Src(biosim.BioModule):
        def __init__(self):
            self._outputs = {
                "state": biosim.ScalarSignal(source="src", name="state", value=1.0, emitted_at=0.0, spec=src_spec)
            }

        def outputs(self):
            return {"state": src_spec}

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return dict(self._outputs)

    class Dst(biosim.BioModule):
        def inputs(self):
            return {"state": dst_spec}

        def set_inputs(self, signals):
            return

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.add_biomodule("dst", Dst())
    world.connect("src.state", "dst.state")

    with pytest.raises(ValueError, match="stale signal read"):
        world.run(duration=0.2)


def test_empty_outputs_do_not_clear_signal_store(biosim):
    scalar = _scalar_spec(biosim)

    class Src(biosim.BioModule):
        def __init__(self):
            self._step = 0

        def outputs(self):
            return {"state": scalar}

        def advance_window(self, start, end):
            self._step += 1

        def get_outputs(self):
            if self._step == 1:
                return {"state": biosim.ScalarSignal(source="src", name="state", value=1.0, emitted_at=0.1, spec=scalar)}
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.run(duration=0.2)

    outputs = world.get_outputs("src")
    assert outputs["state"].value == 1.0
    assert outputs["state"].emitted_at == pytest.approx(0.1)


def test_non_empty_output_map_replaces_prior_ports(biosim):
    scalar = _scalar_spec(biosim)

    class Src(biosim.BioModule):
        def __init__(self):
            self._step = 0

        def outputs(self):
            return {"a": scalar, "b": scalar}

        def advance_window(self, start, end):
            self._step += 1

        def get_outputs(self):
            if self._step == 1:
                return {
                    "a": biosim.ScalarSignal(source="src", name="a", value=1.0, emitted_at=0.1, spec=scalar),
                    "b": biosim.ScalarSignal(source="src", name="b", value=2.0, emitted_at=0.1, spec=scalar),
                }
            return {"a": biosim.ScalarSignal(source="src", name="a", value=3.0, emitted_at=0.2, spec=scalar)}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.run(duration=0.2)

    outputs = world.get_outputs("src")
    assert set(outputs) == {"a"}
    assert outputs["a"].value == 3.0


def test_setup_resets_signal_store_and_connection_state(biosim):
    received = []
    event_spec = biosim.SignalSpec.event(schema={"code": "str"})

    class Src(biosim.BioModule):
        def __init__(self):
            self._outputs = {}

        def setup(self, _config=None):
            self._outputs = {}

        def outputs(self):
            return {"ev": event_spec}

        def advance_window(self, start, end):
            self._outputs = {
                "ev": biosim.EventSignal(
                    source="src",
                    name="ev",
                    value={"code": "pulse"},
                    emitted_at=0.1,
                    spec=event_spec,
                )
            }

        def get_outputs(self):
            return dict(self._outputs)

    class Dst(biosim.BioModule):
        def inputs(self):
            return {"ev": event_spec}

        def set_inputs(self, signals):
            if "ev" in signals:
                received.append(signals["ev"].emitted_at)

        def advance_window(self, start, end):
            return

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("src", Src())
    world.add_biomodule("dst", Dst())
    world.connect("src.ev", "dst.ev")

    world.run(duration=0.2)
    assert world.get_outputs("src")["ev"].emitted_at == pytest.approx(0.1)
    assert received == [0.1]

    world.setup()
    assert world.get_outputs("src") == {}

    world.run(duration=0.2)
    assert received == [0.1, 0.1]


def test_snapshot_restore_and_branch_preserve_world_state(biosim):
    scalar = _scalar_spec(biosim)

    class Counter(biosim.BioModule):
        def __init__(self):
            self.count = 0
            self._outputs = {}

        def outputs(self):
            return {"count": scalar}

        def advance_window(self, start, end):
            self.count += 1
            self._outputs = {
                "count": biosim.ScalarSignal(source="counter", name="count", value=self.count, emitted_at=end, spec=scalar)
            }

        def get_outputs(self):
            return dict(self._outputs)

        def snapshot(self):
            return {"count": self.count}

        def restore(self, snapshot):
            self.count = int(snapshot["count"])

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("counter", Counter())
    world.run(duration=0.2)

    snapshot = world.snapshot()
    assert world.get_outputs("counter")["count"].value == 2

    branched = world.branch()
    branched.run(duration=0.1)
    assert branched.get_outputs("counter")["count"].value == 3

    world.run(duration=0.2)
    assert world.get_outputs("counter")["count"].value == 4

    world.restore(snapshot)
    assert world.current_time == pytest.approx(0.2)
    assert world.get_outputs("counter")["count"].value == 2

    world.run(duration=0.1)
    assert world.get_outputs("counter")["count"].value == 3
