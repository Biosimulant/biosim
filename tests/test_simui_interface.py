"""Tests for biosim.simui.interface – 100% coverage."""
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from biosim import __version__
from biosim.world import BioWorld, WorldEvent
from biosim.simui.interface import (
    Interface, Number, Button, EventLog, VisualsPanel,
)
from biosim.modules import BioModule


class SimpleModule(BioModule):
    def __init__(self, slow=False):
        self.min_dt = 0.01
        self._slow = slow

    def advance_to(self, t):
        if self._slow:
            import time as _t
            _t.sleep(0.001)

    def get_outputs(self):
        return {}


class VisualModule(BioModule):
    def __init__(self):
        self.min_dt = 0.1

    def advance_to(self, t):
        pass

    def get_outputs(self):
        return {}

    def visualize(self):
        return {"render": "bar", "data": {"items": [{"label": "a", "value": 1}]}, "description": "Test vis"}


def _make_world():
    world = BioWorld()
    world.add_biomodule("m", SimpleModule())
    return world


def _make_app(world=None, **kwargs):
    world = world or _make_world()
    # Create a static dir with app.js for mount to succeed
    static_dir = Path(__file__).parent.parent / "src" / "biosim" / "simui" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app_js = static_dir / "app.js"
    if not app_js.exists():
        app_js.write_text("// placeholder")
    ui = Interface(world, **kwargs)
    app = FastAPI()
    ui.mount(app, "/ui")
    return app, ui


class TestComponents:
    def test_number(self):
        n = Number("x", 1.0, label="X", minimum=0, maximum=10, step=0.1)
        assert n.name == "x"
        assert n.default == 1.0

    def test_button(self):
        b = Button("Go")
        assert b.label == "Go"

    def test_event_log(self):
        e = EventLog(limit=50)
        assert e.limit == 50

    def test_visuals_panel(self):
        v = VisualsPanel(refresh="manual", interval_ms=1000)
        assert v.refresh == "manual"


class TestInterfaceInit:
    def test_default_controls(self):
        world = _make_world()
        ui = Interface(world)
        assert ui._title == "BioSim UI"
        assert ui._description is None

    def test_custom_controls(self):
        world = _make_world()
        ui = Interface(
            world,
            title="Custom",
            description="Desc",
            controls=[Number("dur", 5.0), Button("Start")],
            outputs=[EventLog(limit=50), VisualsPanel()],
        )
        assert ui._title == "Custom"
        assert ui._event_limit == 50

    def test_mount_path_normalization(self):
        world = _make_world()
        ui = Interface(world, mount_path="/api/")
        assert ui._mount_path == "/api"


class TestSpecEndpoint:
    def test_spec(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/api/spec")
        assert r.status_code == 200
        data = r.json()
        assert data["version"] == "2"
        assert data["bsim_version"] == __version__
        assert "m" in data["modules"]
        assert data["title"] == "BioSim UI"

    def test_spec_with_custom_controls(self):
        app, ui = _make_app(
            controls=[Number("x", 1.0, label="X", minimum=0, maximum=10, step=0.5), Button("Go")],
            outputs=[EventLog(50), VisualsPanel()],
        )
        client = TestClient(app)
        r = client.get("/ui/api/spec")
        data = r.json()
        ctrl_types = [c["type"] for c in data["controls"]]
        assert "number" in ctrl_types
        assert "button" in ctrl_types
        out_types = [o["type"] for o in data["outputs"]]
        assert "event_log" in out_types
        assert "visuals" in out_types

    def test_spec_unknown_control_ignored(self):
        app, ui = _make_app(controls=["unknown_control"])
        client = TestClient(app)
        r = client.get("/ui/api/spec")
        data = r.json()
        assert len(data["controls"]) == 0

    def test_spec_unknown_output_ignored(self):
        app, ui = _make_app(outputs=["unknown_output"])
        client = TestClient(app)
        r = client.get("/ui/api/spec")
        data = r.json()
        assert len(data["outputs"]) == 0


class TestRunEndpoint:
    def test_run_success(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/run", json={"duration": 0.05, "tick_dt": 0.01})
        assert r.status_code == 202
        assert r.json()["ok"] is True
        # Wait for completion
        ui._runner.join(timeout=5.0)

    def test_run_already_running(self):
        world = BioWorld()
        world.add_biomodule("m", SimpleModule(slow=True))
        app, ui = _make_app(world=world)
        client = TestClient(app)
        r1 = client.post("/ui/api/run", json={"duration": 100.0, "tick_dt": 0.01})
        assert r1.status_code == 202
        time.sleep(0.1)
        r2 = client.post("/ui/api/run", json={"duration": 100.0, "tick_dt": 0.01})
        assert r2.status_code == 409
        ui._runner.request_stop()
        ui._runner.join(timeout=5.0)

    def test_run_bad_duration(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/run", json={"duration": "bad"})
        assert r.status_code == 400

    def test_run_negative_duration(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/run", json={"duration": -1})
        assert r.status_code == 400

    def test_run_bad_tick_dt(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/run", json={"duration": 1.0, "tick_dt": "bad"})
        assert r.status_code == 400

    def test_run_negative_tick_dt(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/run", json={"duration": 1.0, "tick_dt": -0.1})
        assert r.status_code == 400

    def test_run_no_tick_dt(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/run", json={"duration": 0.05})
        assert r.status_code == 202
        ui._runner.join(timeout=5.0)


class TestStatusEndpoints:
    def test_status(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/api/status")
        assert r.status_code == 200
        assert r.json()["running"] is False

    def test_state(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/api/state")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "modules" in data

    def test_snapshot(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/api/snapshot")
        assert r.status_code == 200
        data = r.json()
        assert "status" in data
        assert "visuals" in data
        assert "events" in data

    def test_status_includes_progress_after_run(self):
        app, ui = _make_app()
        client = TestClient(app)
        run_response = client.post("/ui/api/run", json={"duration": 0.05, "tick_dt": 0.01})
        assert run_response.status_code == 202
        ui._runner.join(timeout=5.0)

        r = client.get("/ui/api/status")
        assert r.status_code == 200
        data = r.json()
        assert data["progress"] == pytest.approx(1.0)
        assert data["progress_pct"] == pytest.approx(100.0)
        assert data["sim_time"] == pytest.approx(0.05)
        assert data["sim_start"] == pytest.approx(0.0)
        assert data["sim_end"] == pytest.approx(0.05)
        assert data["sim_remaining"] == pytest.approx(0.0)


class TestPauseResumeEndpoints:
    def test_pause_not_running(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/pause")
        assert r.json()["ok"] is False
        assert r.json()["reason"] == "not_running"

    def test_resume_not_running(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/resume")
        assert r.json()["ok"] is False
        assert r.json()["reason"] == "not_running"

    def test_pause_and_resume(self):
        world = BioWorld()
        world.add_biomodule("m", SimpleModule(slow=True))
        app, ui = _make_app(world=world)
        client = TestClient(app)
        # Start a run
        client.post("/ui/api/run", json={"duration": 100.0, "tick_dt": 0.01})
        time.sleep(0.15)
        # Pause
        r = client.post("/ui/api/pause")
        assert r.json()["ok"] is True
        # Double pause
        r = client.post("/ui/api/pause")
        assert r.json()["reason"] == "already_paused"
        # Resume
        r = client.post("/ui/api/resume")
        assert r.json()["ok"] is True
        # Double resume
        r = client.post("/ui/api/resume")
        assert r.json()["reason"] == "not_paused"
        ui._runner.request_stop()
        ui._runner.join(timeout=5.0)


class TestEventsEndpoint:
    def test_events_empty(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/api/events")
        data = r.json()
        assert data["events"] == []

    def test_events_with_data(self):
        app, ui = _make_app()
        client = TestClient(app)
        # Run a quick simulation to generate events
        client.post("/ui/api/run", json={"duration": 0.05, "tick_dt": 0.01})
        ui._runner.join(timeout=5.0)
        r = client.get("/ui/api/events")
        data = r.json()
        assert len(data["events"]) > 0

    def test_events_since_id(self):
        app, ui = _make_app()
        client = TestClient(app)
        client.post("/ui/api/run", json={"duration": 0.05, "tick_dt": 0.01})
        ui._runner.join(timeout=5.0)
        r = client.get("/ui/api/events?since_id=1&limit=5")
        data = r.json()
        assert "next_since_id" in data


class TestVisualsEndpoint:
    def test_visuals_empty(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/api/visuals")
        assert r.status_code == 200

    def test_visuals_with_module(self):
        world = BioWorld()
        world.add_biomodule("vis", VisualModule())
        app, ui = _make_app(world=world)
        client = TestClient(app)
        # Run to generate outputs
        client.post("/ui/api/run", json={"duration": 0.2, "tick_dt": 0.1})
        ui._runner.join(timeout=5.0)
        r = client.get("/ui/api/visuals")
        data = r.json()
        assert len(data) > 0
        assert data[0]["visuals"][0]["render"] == "bar"
        assert data[0]["visuals"][0]["description"] == "Test vis"


class TestResetEndpoint:
    def test_reset(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.post("/ui/api/reset")
        assert r.json()["ok"] is True


class TestIndexEndpoint:
    def test_index_html(self):
        app, ui = _make_app()
        client = TestClient(app)
        r = client.get("/ui/")
        assert r.status_code == 200
        assert "<!doctype html>" in r.text


class TestMountErrors:
    def test_missing_static(self, tmp_path, monkeypatch):
        world = _make_world()
        ui = Interface(world)
        app = FastAPI()
        # Patch the static dir check to point to a nonexistent dir
        with patch.object(Path, "exists", return_value=False):
            with pytest.raises(RuntimeError, match="static bundle missing"):
                ui.mount(app, "/ui")


class TestClose:
    def test_close(self):
        world = _make_world()
        ui = Interface(world)
        ui.close()  # Should not raise


class TestListenerAndSSE:
    def test_listener_records_events(self):
        world = _make_world()
        ui = Interface(world)
        # Simulate a tick event
        ui._listener(WorldEvent.TICK, {"t": 0.1, "module": "m"})
        assert len(ui._events) == 1
        assert ui._last_step is not None

    def test_listener_non_tick_event(self):
        world = _make_world()
        ui = Interface(world)
        ui._listener(WorldEvent.STARTED, {"t": 0.0})
        assert len(ui._events) == 1
        assert ui._last_step is None

    def test_sse_subscribe_unsubscribe(self):
        world = _make_world()
        ui = Interface(world)
        q = ui._subscribe_sse()
        assert q in ui._sse_subscribers
        ui._unsubscribe_sse(q)
        assert q not in ui._sse_subscribers

    def test_broadcast_sse(self):
        world = _make_world()
        ui = Interface(world)
        q = ui._subscribe_sse()
        ui._broadcast_sse({"type": "test"})
        msg = q.get_nowait()
        assert msg["type"] == "test"
        ui._unsubscribe_sse(q)

    def test_tick_sse_includes_progress(self):
        world = _make_world()
        ui = Interface(world)
        q = ui._subscribe_sse()
        with patch.object(
            ui._runner,
            "status",
            return_value={"running": True, "paused": False, "progress": 0.1, "progress_pct": 10.0},
        ):
            ui._listener(WorldEvent.TICK, {"t": 0.1, "progress": 0.1, "progress_pct": 10.0})
        msg = q.get_nowait()
        assert msg["type"] == "tick"
        assert msg["data"]["status"]["progress_pct"] == pytest.approx(10.0)
        assert msg["data"]["event"]["payload"]["progress_pct"] == pytest.approx(10.0)
        ui._unsubscribe_sse(q)

    def test_collect_visuals_safe_error(self):
        world = _make_world()
        ui = Interface(world)
        with patch.object(world, "collect_visuals", side_effect=RuntimeError("oops")):
            result = ui._collect_visuals_safe()
            assert result == []

    def test_collect_visuals_safe_with_description(self):
        world = BioWorld()
        world.add_biomodule("vis", VisualModule())
        world.run(duration=0.1)
        ui = Interface(world)
        result = ui._collect_visuals_safe()
        assert len(result) > 0


class TestLaunch:
    def test_launch_calls_uvicorn(self):
        world = _make_world()
        ui = Interface(world)
        mock_uv = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uv}):
            ui.launch(host="0.0.0.0", port=9999)
            mock_uv.run.assert_called_once()
            call_kwargs = mock_uv.run.call_args
            assert call_kwargs[1]["host"] == "0.0.0.0"
            assert call_kwargs[1]["port"] == 9999

    def test_launch_with_open_browser(self):
        world = _make_world()
        ui = Interface(world)
        mock_uv = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uv}):
            with patch("webbrowser.open") as mock_wb:
                ui.launch(open_browser=True)
                mock_wb.assert_called_once()

    def test_launch_browser_error_ignored(self):
        world = _make_world()
        ui = Interface(world)
        mock_uv = MagicMock()
        with patch.dict("sys.modules", {"uvicorn": mock_uv}):
            with patch("webbrowser.open", side_effect=RuntimeError("no browser")):
                ui.launch(open_browser=True)  # Should not raise


class TestReloadWorld:
    def test_reload_no_config_path(self):
        world = _make_world()
        ui = Interface(world)
        result = ui._reload_world()
        assert result is False

    def test_reload_missing_file(self, tmp_path):
        world = _make_world()
        ui = Interface(world, config_path=tmp_path / "missing.yaml")
        result = ui._reload_world()
        assert result is False

    def test_reload_exception(self, tmp_path):
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("modules: {}\n")
        world = _make_world()
        ui = Interface(world, config_path=cfg)
        # Patch the world to raise during reload
        with patch.object(ui._runner, "reset", side_effect=RuntimeError("test")):
            result = ui._reload_world()
            assert result is False


class TestSSEStream:
    def test_stream_subscribe_and_broadcast(self):
        """Test SSE subscribe/broadcast mechanism used by the stream endpoint."""
        world = _make_world()
        ui = Interface(world)
        q = ui._subscribe_sse()
        assert q is not None
        assert len(ui._sse_subscribers) == 1
        # Broadcast should put message in queue
        ui._broadcast_sse({"type": "test", "data": {}})
        msg = q.get_nowait()
        assert msg["type"] == "test"
        ui._unsubscribe_sse(q)
        assert len(ui._sse_subscribers) == 0

    def test_stream_broadcast_error_handling(self):
        """Broadcast should not crash if a queue is full or broken."""
        world = _make_world()
        ui = Interface(world)
        from queue import Queue
        q = Queue(maxsize=1)
        q.put({"filler": True})  # fill the queue
        ui._sse_subscribers.add(q)
        # Should not raise even though queue is full
        ui._broadcast_sse({"type": "overflow"})
        ui._sse_subscribers.discard(q)


class TestSpecModuleNamesError:
    def test_module_names_exception(self):
        world = _make_world()
        app, ui = _make_app(world=world)
        client = TestClient(app)
        with patch.object(type(world), "module_names", new_callable=lambda: property(lambda s: (_ for _ in ()).throw(RuntimeError()))):
            r = client.get("/ui/api/spec")
            assert r.status_code == 200
            assert r.json()["modules"] == []


class TestEventsInternals:
    def test_events_since_no_items(self):
        world = _make_world()
        ui = Interface(world)
        result = ui._events_since(None, 200)
        assert result["events"] == []
        assert result["next_since_id"] == 0

    def test_events_since_with_since_id(self):
        world = _make_world()
        ui = Interface(world)
        ui._listener(WorldEvent.STARTED, {})
        ui._listener(WorldEvent.TICK, {"t": 0.1})
        ui._listener(WorldEvent.FINISHED, {})
        result = ui._events_since(1, 200)
        # Should get events with id > 1
        assert all(e["id"] > 1 for e in result["events"])


class TestCloseErrorPath:
    def test_close_error_ignored(self):
        """close() should not crash if world.off() raises."""
        world = _make_world()
        ui = Interface(world)
        with patch.object(world, "off", side_effect=RuntimeError("oops")):
            ui.close()  # Should not raise


class TestResetExceptionPath:
    def test_reset_exception_ignored(self):
        """Reset endpoint should not crash if runner.reset() raises."""
        app, ui = _make_app()
        client = TestClient(app)
        with patch.object(ui._runner, "reset", side_effect=RuntimeError("oops")):
            r = client.post("/ui/api/reset")
            assert r.status_code == 200
            assert r.json()["ok"] is True


class TestReloadWorldSuccess:
    def test_reload_success(self, tmp_path):
        """_reload_world should succeed with a valid config file."""
        config = tmp_path / "test.yaml"
        config.write_text("modules: {}\n")
        world = _make_world()
        # Add the internal attributes that _reload_world expects
        world._biomodule_listeners = {"m": None}
        world.remove_biomodule = MagicMock()
        world._signal_routes = {}
        ui = Interface(world, config_path=config)
        with patch("biosim.load_wiring"):
            result = ui._reload_world()
        assert result is True

    def test_reload_with_new_path(self, tmp_path):
        """_reload_world should accept a new config path."""
        config = tmp_path / "new.yaml"
        config.write_text("modules: {}\n")
        world = _make_world()
        world._biomodule_listeners = {}
        world._signal_routes = {}
        ui = Interface(world)
        with patch("biosim.load_wiring"):
            result = ui._reload_world(new_config_path=config)
        assert result is True
        assert ui._config_path == config
