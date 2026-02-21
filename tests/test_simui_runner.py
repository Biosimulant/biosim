"""Tests for biosim.simui.runner – 100% coverage."""
import time
import pytest
from biosim.world import BioWorld
from biosim.simui.runner import SimulationManager, RunStatus, _ts


def _make_world_with_module(slow=False):
    """Create a BioWorld with a simple module for testing."""
    import biosim

    class M(biosim.BioModule):
        def __init__(self):
            self.min_dt = 0.01

        def advance_to(self, t):
            if slow:
                time.sleep(0.001)

        def get_outputs(self):
            return {}

    world = BioWorld()
    world.add_biomodule("m", M())
    return world


class TestRunStatus:
    def test_defaults(self):
        s = RunStatus()
        assert s.running is False
        assert s.started_at is None
        assert s.finished_at is None
        assert s.tick_count == 0
        assert s.error is None
        assert s.paused is False


class TestTimestamp:
    def test_none(self):
        assert _ts(None) is None

    def test_value(self):
        result = _ts(0.0)
        assert result is not None
        assert "1970" in result


class TestSimulationManager:
    def test_start_and_join(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        started = mgr.start_run(duration=0.1, tick_dt=0.01)
        assert started is True
        mgr.join(timeout=5.0)
        st = mgr.status()
        assert st["running"] is False
        assert st["finished_at"] is not None
        assert st["tick_count"] > 0

    def test_double_start_returns_false(self):
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        assert mgr.start_run(duration=100.0, tick_dt=0.01) is True
        time.sleep(0.05)
        assert mgr.start_run(duration=100.0, tick_dt=0.01) is False
        mgr.request_stop()
        mgr.join(timeout=5.0)

    def test_on_start_callback(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        called = []
        mgr.start_run(duration=0.05, tick_dt=0.01, on_start=lambda: called.append(True))
        mgr.join(timeout=5.0)
        assert called == [True]

    def test_status_fields(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        st = mgr.status()
        assert st["running"] is False
        assert st["paused"] is False
        assert st["error"] is None

    def test_request_stop(self):
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0, tick_dt=0.01)
        time.sleep(0.1)
        mgr.request_stop()
        mgr.join(timeout=5.0)
        assert mgr.status()["running"] is False

    def test_pause_resume(self):
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0, tick_dt=0.01)
        time.sleep(0.1)
        mgr.pause()
        time.sleep(0.05)
        assert mgr.status()["paused"] is True
        mgr.resume()
        assert mgr.status()["paused"] is False
        mgr.request_stop()
        mgr.join(timeout=5.0)

    def test_pause_when_not_running(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        mgr.pause()  # should be a no-op
        assert mgr.status()["paused"] is False

    def test_reset_when_not_running(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        mgr.start_run(duration=0.05, tick_dt=0.01)
        mgr.join(timeout=5.0)
        mgr.reset()
        st = mgr.status()
        assert st["running"] is False
        assert st["tick_count"] == 0

    def test_reset_while_running(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0, tick_dt=0.01)
        time.sleep(0.02)
        mgr.reset()
        mgr.join(timeout=5.0)
        # After reset, should be stopped
        assert mgr.status()["running"] is False

    def test_join_when_no_thread(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        mgr.join()  # should be a no-op
