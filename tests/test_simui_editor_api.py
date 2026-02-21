"""Tests for biosim.simui.editor_api – 100% coverage."""
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from biosim.simui.editor_api import (
    _get_allowed_base_paths, _resolve_config_path,
    build_editor_router,
    PositionModel, NodeDataModel, NodeModel, EdgeModel,
    MetaModel, GraphModel, SaveConfigRequest, ApplyConfigRequest,
    ValidateResponse, ConfigFileInfo,
)
from biosim.simui.graph import ConfigGraph, GraphNode, Position


def _make_app(config_path=None, world=None, reload_fn=None):
    """Create a FastAPI app with the editor router."""
    app = FastAPI()
    router = build_editor_router(
        get_config_path=lambda: config_path,
        get_world=lambda: world,
        reload_world=reload_fn,
    )
    app.include_router(router, prefix="/api")
    return TestClient(app)


class TestAllowedBasePaths:
    def test_includes_cwd(self):
        paths = _get_allowed_base_paths()
        assert Path.cwd() in paths

    def test_env_variable(self, monkeypatch):
        monkeypatch.setenv("BSIM_CONFIG_PATH", "/tmp/bsim-configs")
        paths = _get_allowed_base_paths()
        assert Path("/tmp/bsim-configs") in paths


class TestResolveConfigPath:
    def test_relative_in_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test.yaml").write_text("x: 1")
        result = _resolve_config_path("test.yaml")
        assert result == (tmp_path / "test.yaml").resolve()

    def test_absolute_path_allowed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        target = tmp_path / "configs" / "test.yaml"
        target.parent.mkdir()
        target.write_text("x: 1")
        result = _resolve_config_path(str(target))
        assert result == target.resolve()

    def test_path_traversal_blocked(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _resolve_config_path("/etc/passwd")
        assert exc_info.value.status_code == 403


class TestPydanticModels:
    def test_position_model(self):
        p = PositionModel(x=1.0, y=2.0)
        assert p.x == 1.0

    def test_node_data_model(self):
        d = NodeDataModel()
        assert d.args == {}

    def test_node_model(self):
        n = NodeModel(id="a", type="my.A", position=PositionModel(x=0, y=0), data=NodeDataModel())
        assert n.id == "a"

    def test_edge_model(self):
        e = EdgeModel(id="e1", source="a", sourceHandle="out", target="b", targetHandle="in")
        assert e.source == "a"

    def test_meta_model(self):
        m = MetaModel(title="T")
        assert m.title == "T"

    def test_graph_model(self):
        g = GraphModel(nodes=[], edges=[])
        assert g.meta.title is None

    def test_validate_response(self):
        v = ValidateResponse(valid=True)
        assert v.errors == []

    def test_config_file_info(self):
        f = ConfigFileInfo(name="test.yaml", path="test.yaml", is_dir=False)
        assert f.is_dir is False


class TestGetModules:
    def test_modules_endpoint(self):
        client = _make_app()
        r = client.get("/api/editor/modules")
        assert r.status_code == 200
        data = r.json()
        assert "modules" in data
        assert "categories" in data


class TestGetCurrentConfig:
    def test_no_callback(self):
        app = FastAPI()
        router = build_editor_router()
        app.include_router(router, prefix="/api")
        client = TestClient(app)
        r = client.get("/api/editor/current")
        assert r.json()["available"] is False

    def test_no_config_path(self):
        client = _make_app(config_path=None)
        r = client.get("/api/editor/current")
        assert r.json()["available"] is False

    def test_missing_config_file(self, tmp_path):
        client = _make_app(config_path=tmp_path / "missing.yaml")
        r = client.get("/api/editor/current")
        assert r.json()["available"] is False

    def test_valid_config(self, tmp_path):
        cfg = tmp_path / "test.yaml"
        cfg.write_text("modules:\n  a:\n    class: my.A\n")
        client = _make_app(config_path=cfg)
        r = client.get("/api/editor/current")
        data = r.json()
        assert data["available"] is True
        assert "graph" in data

    def test_config_load_error(self, tmp_path):
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("!!!invalid yaml [[[")
        client = _make_app(config_path=cfg)
        r = client.get("/api/editor/current")
        data = r.json()
        assert data["available"] is False
        assert "error" in data


class TestGetConfig:
    def test_load_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "test.yaml"
        cfg.write_text("modules:\n  a:\n    class: my.A\n")
        client = _make_app()
        r = client.get("/api/editor/config", params={"path": "test.yaml"})
        assert r.status_code == 200

    def test_config_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = _make_app()
        r = client.get("/api/editor/config", params={"path": "missing.yaml"})
        assert r.status_code == 404

    def test_config_load_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("- not a dict\n")
        client = _make_app()
        r = client.get("/api/editor/config", params={"path": "bad.yaml"})
        assert r.status_code == 400


class TestSaveConfig:
    def test_save(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = _make_app()
        graph = {
            "nodes": [{"id": "a", "type": "my.A", "position": {"x": 0, "y": 0},
                        "data": {"args": {}, "inputs": [], "outputs": []}}],
            "edges": [],
            "meta": {"title": "Test"},
        }
        r = client.put("/api/editor/config", json={"path": "out.yaml", "graph": graph})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert (tmp_path / "out.yaml").exists()

    def test_save_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = _make_app()
        # Provide invalid graph that will fail json_to_graph
        with patch("biosim.simui.editor_api.json_to_graph", side_effect=ValueError("bad")):
            graph = {"nodes": [], "edges": [], "meta": {}}
            r = client.put("/api/editor/config", json={"path": "out.yaml", "graph": graph})
            assert r.status_code == 400


class TestApplyConfig:
    def test_no_reload_fn(self):
        app = FastAPI()
        router = build_editor_router()
        app.include_router(router, prefix="/api")
        client = TestClient(app)
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/apply", json={"graph": graph})
        assert r.status_code == 501

    def test_apply_with_save_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        reloaded = []
        client = _make_app(reload_fn=lambda p: (reloaded.append(p), True)[-1])
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/apply", json={"graph": graph, "save_path": "test.yaml"})
        assert r.json()["ok"] is True

    def test_apply_with_current_path(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = tmp_path / "current.yaml"
        cfg.write_text("modules: {}\n")
        client = _make_app(config_path=cfg, reload_fn=lambda p: True)
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/apply", json={"graph": graph})
        assert r.json()["ok"] is True

    def test_apply_no_path(self):
        app = FastAPI()
        router = build_editor_router(
            get_config_path=lambda: None,
            reload_world=lambda p: True,
        )
        app.include_router(router, prefix="/api")
        client = TestClient(app)
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/apply", json={"graph": graph})
        assert r.status_code == 400

    def test_apply_no_get_config_path(self):
        app = FastAPI()
        router = build_editor_router(reload_world=lambda p: True)
        app.include_router(router, prefix="/api")
        client = TestClient(app)
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/apply", json={"graph": graph})
        assert r.status_code == 400

    def test_apply_reload_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = _make_app(reload_fn=lambda p: False)
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/apply", json={"graph": graph, "save_path": "test.yaml"})
        assert r.json()["ok"] is False

    def test_apply_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = _make_app(reload_fn=lambda p: True)
        with patch("biosim.simui.editor_api.json_to_graph", side_effect=ValueError("bad")):
            graph = {"nodes": [], "edges": [], "meta": {}}
            r = client.post("/api/editor/apply", json={"graph": graph, "save_path": "test.yaml"})
            assert r.status_code == 400


class TestValidateConfig:
    def test_valid_empty(self):
        client = _make_app()
        graph = {"nodes": [], "edges": [], "meta": {}}
        r = client.post("/api/editor/validate", json=graph)
        data = r.json()
        assert data["valid"] is True

    def test_node_no_type(self):
        client = _make_app()
        graph = {
            "nodes": [{"id": "a", "type": "", "position": {"x": 0, "y": 0},
                        "data": {"args": {}, "inputs": [], "outputs": []}}],
            "edges": [],
        }
        r = client.post("/api/editor/validate", json=graph)
        data = r.json()
        assert data["valid"] is False

    def test_edge_unknown_source(self):
        client = _make_app()
        graph = {
            "nodes": [{"id": "a", "type": "my.A", "position": {"x": 0, "y": 0},
                        "data": {"args": {}, "inputs": [], "outputs": []}}],
            "edges": [{"id": "e1", "source": "unknown", "sourceHandle": "out",
                        "target": "a", "targetHandle": "in"}],
        }
        r = client.post("/api/editor/validate", json=graph)
        data = r.json()
        assert data["valid"] is False

    def test_edge_unknown_target(self):
        client = _make_app()
        graph = {
            "nodes": [{"id": "a", "type": "my.A", "position": {"x": 0, "y": 0},
                        "data": {"args": {}, "inputs": [], "outputs": []}}],
            "edges": [{"id": "e1", "source": "a", "sourceHandle": "out",
                        "target": "unknown", "targetHandle": "in"}],
        }
        r = client.post("/api/editor/validate", json=graph)
        assert r.json()["valid"] is False


class TestLayoutEndpoint:
    def test_layout(self):
        client = _make_app()
        graph = {
            "nodes": [
                {"id": "a", "type": "x", "position": {"x": 0, "y": 0},
                 "data": {"args": {}, "inputs": [], "outputs": []}},
                {"id": "b", "type": "x", "position": {"x": 0, "y": 0},
                 "data": {"args": {}, "inputs": [], "outputs": []}},
            ],
            "edges": [{"id": "e1", "source": "a", "sourceHandle": "out",
                        "target": "b", "targetHandle": "in"}],
        }
        r = client.post("/api/editor/layout", json=graph)
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 2


class TestYamlConversion:
    def test_to_yaml(self):
        client = _make_app()
        graph = {
            "nodes": [{"id": "a", "type": "my.A", "position": {"x": 0, "y": 0},
                        "data": {"args": {}, "inputs": [], "outputs": []}}],
            "edges": [],
            "meta": {"title": "Test"},
        }
        r = client.post("/api/editor/to-yaml", json=graph)
        assert r.status_code == 200
        assert "yaml" in r.json()
        assert "my.A" in r.json()["yaml"]

    def test_from_yaml(self):
        client = _make_app()
        r = client.post("/api/editor/from-yaml", json={"yaml": "modules:\n  a:\n    class: my.A\n"})
        assert r.status_code == 200
        data = r.json()
        assert len(data["nodes"]) == 1

    def test_from_yaml_empty(self):
        client = _make_app()
        r = client.post("/api/editor/from-yaml", json={"yaml": ""})
        assert r.status_code == 400

    def test_from_yaml_invalid(self):
        client = _make_app()
        r = client.post("/api/editor/from-yaml", json={"yaml": "- not a dict\n"})
        assert r.status_code == 400


class TestListFiles:
    def test_list_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "config.yaml").write_text("x: 1")
        (tmp_path / "subdir").mkdir()
        (tmp_path / ".hidden").mkdir()
        client = _make_app()
        r = client.get("/api/editor/files")
        data = r.json()
        names = [f["name"] for f in data]
        assert "config.yaml" in names
        assert "subdir" in names
        assert ".hidden" not in names

    def test_list_subdir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        subdir = tmp_path / "configs"
        subdir.mkdir()
        (subdir / "a.yaml").write_text("x: 1")
        (subdir / "b.txt").write_text("ignored")
        client = _make_app()
        r = client.get("/api/editor/files", params={"path": "configs"})
        data = r.json()
        names = [f["name"] for f in data]
        assert "a.yaml" in names
        assert "b.txt" not in names

    def test_list_not_a_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "file.yaml").write_text("x: 1")
        client = _make_app()
        r = client.get("/api/editor/files", params={"path": "file.yaml"})
        assert r.status_code == 400
