"""Tests for biosim.world – cover all uncovered lines."""
import threading
import time

import pytest
from biosim.world import BioWorld, WorldEvent, SimulationStop


def _make_module(biosim, min_dt=0.1):
    class M(biosim.BioModule):
        def __init__(self):
            self.min_dt = min_dt

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    return M()


def test_listener_off_nonexistent(biosim):
    """off() for unregistered listener should be a silent no-op."""
    world = BioWorld()

    def dummy(ev, data):
        pass

    world.off(dummy)  # should not raise


def test_listener_error_is_logged(biosim, caplog):
    """A failing listener should not crash the world."""
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))

    def bad_listener(ev, data):
        raise RuntimeError("boom")

    world.on(bad_listener)
    world.run(duration=0.1, tick_dt=0.1)
    # Should complete without exception
    assert world.current_time > 0


def test_add_duplicate_module_same_instance(biosim):
    """Re-adding the same module instance with the same name should not raise."""
    world = BioWorld()
    m = _make_module(biosim)
    world.add_biomodule("m", m)
    world.add_biomodule("m", m)  # same instance, same name -> no error


def test_add_duplicate_module_different_instance(biosim):
    """Adding a different module with the same name should raise."""
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    with pytest.raises(ValueError, match="already registered"):
        world.add_biomodule("m", _make_module(biosim))


def test_add_module_no_min_dt_raises(biosim):
    """Module without positive min_dt should raise."""

    class NoMinDt(biosim.BioModule):
        min_dt = 0.0

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    world = BioWorld()
    with pytest.raises(ValueError, match="positive min_dt"):
        world.add_biomodule("bad", NoMinDt())


def test_add_module_negative_min_dt_raises(biosim):
    class NegDt(biosim.BioModule):
        min_dt = -1.0

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    world = BioWorld()
    with pytest.raises(ValueError, match="positive min_dt"):
        world.add_biomodule("bad", NegDt())


def test_connect_bad_format(biosim):
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    with pytest.raises(ValueError, match="format"):
        world.connect("m_no_dot", "m.x")
    with pytest.raises(ValueError, match="format"):
        world.connect("m.x", "nodot")


def test_connect_unknown_source(biosim):
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    with pytest.raises(KeyError, match="Unknown source"):
        world.connect("unknown.x", "m.x")


def test_connect_unknown_target(biosim):
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    with pytest.raises(KeyError, match="Unknown target"):
        world.connect("m.x", "unknown.y")


def test_setup_bad_next_due_time_raises(biosim):
    """Module returning next_due_time <= current should raise."""

    class BadSchedule(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

        def next_due_time(self, now):
            return now  # equals current, not greater

    world = BioWorld()
    world.add_biomodule("bad", BadSchedule())
    with pytest.raises(ValueError, match="must be > current"):
        world.setup()


def test_run_zero_duration(biosim):
    """run(duration=0) should be a no-op."""
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    world.setup()
    world.run(duration=0)
    assert world.current_time == 0.0


def test_run_auto_setup(biosim):
    """run() should call setup if not already done."""
    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    world.run(duration=0.1)
    assert world.current_time > 0


def test_run_emits_started_finished(biosim):
    events = []

    def listener(ev, data):
        events.append(ev)

    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    world.on(listener)
    world.run(duration=0.1, tick_dt=0.1)
    assert WorldEvent.STARTED in events
    assert WorldEvent.FINISHED in events


def test_run_emits_tick_with_module_name(biosim):
    """Without tick_dt, ticks should include module name."""
    payloads = []

    def listener(ev, data):
        if ev == WorldEvent.TICK:
            payloads.append(data)

    world = BioWorld()
    world.add_biomodule("m", _make_module(biosim))
    world.on(listener)
    world.run(duration=0.1)  # No tick_dt -> per-module ticks
    assert any("module" in p for p in payloads)


def test_request_stop(biosim):
    """request_stop() should cause STOPPED event."""
    events = []

    class SlowModule(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.01

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    def listener(ev, data):
        events.append(ev)
        if ev == WorldEvent.STARTED:
            world.request_stop()

    world = BioWorld()
    world.add_biomodule("m", SlowModule())
    world.on(listener)
    world.run(duration=100.0)
    assert WorldEvent.STOPPED in events


def test_request_pause_resume(biosim):
    events = []

    class SlowModule(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.01
            self.step_count = 0

        def advance_to(self, t):
            self.step_count += 1

        def get_outputs(self):
            return {}

    mod = SlowModule()
    world = BioWorld()
    world.add_biomodule("m", mod)

    def listener(ev, data):
        events.append(ev)

    world.on(listener)

    # Pause after a short delay, then resume, then stop
    def pause_then_resume():
        time.sleep(0.05)
        world.request_pause()
        time.sleep(0.05)
        world.request_resume()
        time.sleep(0.05)
        world.request_stop()

    t = threading.Thread(target=pause_then_resume, daemon=True)
    t.start()
    world.run(duration=1000.0, tick_dt=0.01)
    t.join(timeout=2.0)

    assert WorldEvent.PAUSED in events
    assert WorldEvent.RESUMED in events


def test_error_event_on_module_exception(biosim):
    events = []

    class FailModule(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            raise RuntimeError("advance failed")

        def get_outputs(self):
            return {}

    def listener(ev, data):
        events.append(ev)

    world = BioWorld()
    world.add_biomodule("fail", FailModule())
    world.on(listener)

    with pytest.raises(RuntimeError, match="advance failed"):
        world.run(duration=1.0)

    assert WorldEvent.ERROR in events
    assert WorldEvent.FINISHED in events


def test_run_next_due_time_bad_during_loop(biosim):
    """Module returning bad next_due_time during the loop should raise."""

    class BadAfterFirst(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1
            self._first = True

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

        def next_due_time(self, now):
            if self._first:
                self._first = False
                return now + self.min_dt
            return now  # bad! <= current

    world = BioWorld()
    world.add_biomodule("bad", BadAfterFirst())

    with pytest.raises(ValueError, match="must be > current"):
        world.run(duration=1.0)


def test_module_names(biosim):
    world = BioWorld()
    world.add_biomodule("a", _make_module(biosim))
    world.add_biomodule("b", _make_module(biosim))
    assert set(world.module_names) == {"a", "b"}


def test_get_outputs_empty(biosim):
    world = BioWorld()
    assert world.get_outputs("nonexistent") == {}


def test_collect_visuals_visualize_exception(biosim):
    """Module that raises in visualize() should be skipped."""

    class BadVis(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

        def visualize(self):
            raise RuntimeError("vis error")

    world = BioWorld()
    world.add_biomodule("bad", BadVis())
    world.run(duration=0.1)
    result = world.collect_visuals()
    assert result == []


def test_collect_visuals_normalize_empty(biosim):
    """Module returning empty list from visualize() should produce no visuals."""

    class EmptyVis(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

        def visualize(self):
            return []

    world = BioWorld()
    world.add_biomodule("empty", EmptyVis())
    world.run(duration=0.1)
    assert world.collect_visuals() == []


def test_event_signals_filter_already_seen(biosim):
    """Event signals should not be re-delivered if already seen."""

    received = []

    class Src(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {
                "ev": biosim.BioSignal(
                    source="src", name="ev", value=1, time=0.1,
                    metadata={"kind": "event"},
                )
            }

    class Dst(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def set_inputs(self, signals):
            if "ev" in signals:
                received.append(signals["ev"])

        def get_outputs(self):
            return {}

        def inputs(self):
            return {"ev"}

    world = BioWorld()
    world.add_biomodule("src", Src(), priority=1)
    world.add_biomodule("dst", Dst())
    world.connect("src.ev", "dst.ev")
    world.run(duration=0.3, tick_dt=0.1)

    # The event signal is produced at time=0.1 with same time every step,
    # so it should only be delivered once (when first seen)
    assert len(received) == 1


def test_current_time_property(biosim):
    world = BioWorld()
    assert world.current_time == 0.0
    world.add_biomodule("m", _make_module(biosim))
    world.run(duration=0.5, tick_dt=0.1)
    assert world.current_time == pytest.approx(0.5, abs=0.01)


def test_simulation_stop_is_exception():
    assert issubclass(SimulationStop, Exception)


def test_setattr_world_name_on_module(biosim):
    """add_biomodule should set _world_name on module."""
    m = _make_module(biosim)
    world = BioWorld()
    world.add_biomodule("mymod", m)
    assert getattr(m, "_world_name", None) == "mymod"


def test_setattr_world_name_fails_silently(biosim):
    """If setattr fails (e.g., __slots__ module), it should be silently ignored."""

    class Frozen(biosim.BioModule):
        __slots__ = ("min_dt",)

        def __init__(self):
            self.min_dt = 0.1

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    world = BioWorld()
    # Should not raise even though __slots__ prevents _world_name
    world.add_biomodule("frozen", Frozen())


def test_stop_requested_after_wait(biosim):
    """Stop requested while blocked on _run_event.wait() should be detected."""
    events = []

    class M(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.01

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

    world = BioWorld()
    world.add_biomodule("m", M())

    def listener(ev, data):
        events.append(ev)

    world.on(listener)

    # Pause the world, then request stop while paused
    def pause_then_stop():
        time.sleep(0.02)
        world.request_pause()
        time.sleep(0.02)
        world._stop_requested = True
        world._run_event.set()  # unblock wait

    t = threading.Thread(target=pause_then_stop, daemon=True)
    t.start()
    world.run(duration=1000.0, tick_dt=0.01)
    t.join(timeout=2.0)
    assert WorldEvent.STOPPED in events
