"""Tests for biosim.simui.runner – 100% coverage."""
import time
from unittest.mock import patch
import pytest
from biosim.world import BioWorld
from biosim.simui.runner import SimulationManager, RunStatus, _coerce_float, _ts, _update_progress


def _make_world_with_module(slow=False):
    """Create a BioWorld with a simple module for testing."""
    import biosim

    class M(biosim.BioModule):
        def __init__(self):
            pass

        def advance_window(self, _start, t):
            if slow:
                time.sleep(0.001)

        def get_outputs(self):
            return {}

    world = BioWorld(communication_step=0.1)
    world.add_biomodule("m", M())
    return world


class TestRunStatus:
    def test_defaults(self):
        s = RunStatus()
        assert s.running is False
        assert s.started_at is None
        assert s.finished_at is None
        assert s.step_count == 0
        assert s.error is None
        assert s.paused is False
        assert s.sim_time is None
        assert s.sim_start is None
        assert s.sim_end is None
        assert s.sim_remaining is None
        assert s.progress is None
        assert s.progress_pct is None


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
        started = mgr.start_run(duration=0.1)
        assert started is True
        mgr.join(timeout=5.0)
        st = mgr.status()
        assert st["running"] is False
        assert st["finished_at"] is not None
        assert st["step_count"] > 0
        assert st["sim_start"] == pytest.approx(0.0)
        assert st["sim_end"] == pytest.approx(0.1)
        assert st["sim_time"] == pytest.approx(0.1)
        assert st["sim_remaining"] == pytest.approx(0.0)
        assert st["progress"] == pytest.approx(1.0)
        assert st["progress_pct"] == pytest.approx(100.0)

    def test_double_start_returns_false(self):
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        assert mgr.start_run(duration=100.0) is True
        time.sleep(0.05)
        assert mgr.start_run(duration=100.0) is False
        mgr.request_stop()
        mgr.join(timeout=5.0)

    def test_on_start_callback(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        called = []
        mgr.start_run(duration=0.05, on_start=lambda: called.append(True))
        mgr.join(timeout=5.0)
        assert called == [True]

    def test_status_fields(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        st = mgr.status()
        assert st["running"] is False
        assert st["paused"] is False
        assert st["error"] is None
        assert "progress_pct" not in st

    def test_request_stop(self):
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
        time.sleep(0.1)
        mgr.request_stop()
        mgr.join(timeout=5.0)
        status = mgr.status()
        assert status["running"] is False
        assert status["progress_pct"] < 100.0

    def test_pause_resume(self):
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
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
        mgr.start_run(duration=0.05)
        mgr.join(timeout=5.0)
        mgr.reset()
        st = mgr.status()
        assert st["running"] is False
        assert st["step_count"] == 0
        assert "progress_pct" not in st

    def test_reset_while_running(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
        time.sleep(0.02)
        mgr.reset()
        mgr.join(timeout=5.0)
        # After reset, should be stopped
        assert mgr.status()["running"] is False

    def test_join_when_no_thread(self):
        world = _make_world_with_module()
        mgr = SimulationManager(world)
        mgr.join()  # should be a no-op

    def test_request_stop_world_error(self):
        """request_stop should not crash if world.request_stop fails."""
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
        time.sleep(0.05)
        with patch.object(world, "request_stop", side_effect=RuntimeError("oops")):
            mgr.request_stop()
        mgr.join(timeout=5.0)

    def test_pause_world_error(self):
        """pause should not crash if world.request_pause fails."""
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
        time.sleep(0.1)
        with patch.object(world, "request_pause", side_effect=RuntimeError("oops")):
            mgr.pause()
        mgr.request_stop()
        mgr.join(timeout=5.0)

    def test_resume_world_error(self):
        """resume should not crash if world.request_resume fails."""
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
        time.sleep(0.1)
        mgr.pause()
        time.sleep(0.05)
        with patch.object(world, "request_resume", side_effect=RuntimeError("oops")):
            mgr.resume()
        mgr.request_stop()
        mgr.join(timeout=5.0)

    def test_reset_while_running_and_join(self):
        """reset while running should stop, join thread, then reset status."""
        world = _make_world_with_module(slow=True)
        mgr = SimulationManager(world)
        mgr.start_run(duration=100.0)
        time.sleep(0.1)
        mgr.reset()
        assert mgr.status()["running"] is False


class TestProgressHelpers:
    def test_coerce_float(self):
        assert _coerce_float(1) == 1.0
        assert _coerce_float("2.5") == 2.5
        assert _coerce_float("bad") is None
        assert _coerce_float(float("nan")) is None

    def test_update_progress(self):
        status = RunStatus()
        _update_progress(status, "bad payload")
        assert status.progress is None

        _update_progress(
            status,
            {
                "t": 0.3,
                "start": 0.0,
                "end": 1.0,
                "remaining": 0.7,
                "progress": 0.3,
                "progress_pct": 30.0,
            },
        )
        assert status.sim_time == pytest.approx(0.3)
        assert status.sim_start == pytest.approx(0.0)
        assert status.sim_end == pytest.approx(1.0)
        assert status.sim_remaining == pytest.approx(0.7)
        assert status.progress == pytest.approx(0.3)
        assert status.progress_pct == pytest.approx(30.0)
