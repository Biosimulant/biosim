from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from biosim.labs_serve import server
from biosim.labs_serve.server import LabServeSession, RunRecord, create_app
from biosim.pack import _safe_yaml_dump, _safe_yaml_load
from tests.test_pack import _write_lab


def _client(lab: Path) -> tuple[TestClient, LabServeSession]:
    session = LabServeSession(lab, install_deps=False)
    return TestClient(create_app(session)), session


def test_root_html_static_assets_and_legacy_ui_redirect(tmp_path: Path, monkeypatch) -> None:
    lab = _write_lab(tmp_path / "lab")
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>labs serve</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")
    monkeypatch.setattr(server, "STATIC_DIR", static)

    client, _session = _client(lab)

    root = client.get("/")
    assert root.status_code == 200
    assert "labs serve" in root.text
    assert client.get("/assets/app.js").status_code == 200
    redirected = client.get("/ui/", follow_redirects=False)
    assert redirected.status_code == 307
    assert redirected.headers["location"] == "/"


def test_lab_api_enriches_payload_and_persists_edits(tmp_path: Path) -> None:
    lab = _write_lab(tmp_path / "lab")
    client, _session = _client(lab)

    payload = client.get("/api/lab").json()
    assert payload["ok"] is True
    lab_payload = payload["data"]["lab"]
    assert lab_payload["title"] == "Test: Lab"
    counter = lab_payload["manifest"]["models"][0]
    assert counter["alias"] == "counter"
    assert counter["resolved_model"]["io"]["outputs"][0]["name"] == "count"

    renamed = client.put("/api/lab/models/counter", json={"alias": "source"}).json()
    assert renamed["ok"] is True
    manifest = _safe_yaml_load((lab / "lab.yaml").read_bytes())
    assert manifest["models"][0]["alias"] == "source"
    assert manifest["wiring"][0]["from"] == "source.count"

    saved = client.put(
        "/api/lab/layout",
        json={"nodes": [{"id": "source", "position": {"x": 10, "y": 20}}]},
    ).json()
    assert saved["ok"] is True
    layout = json.loads((lab / "wiring-layout.json").read_text(encoding="utf-8"))
    assert layout["nodes"][0]["position"] == {"x": 10, "y": 20}

    world_saved = client.put(
        "/api/lab/world",
        json={"wiring": [{"from": "source.count", "to": "accumulator.value"}]},
    ).json()
    assert world_saved["ok"] is True
    manifest = _safe_yaml_load((lab / "lab.yaml").read_bytes())
    assert manifest["wiring"] == [{"from": "source.count", "to": "accumulator.value"}]


def test_run_overrides_map_world_inputs_to_alias_nested_shape() -> None:
    manifest = {
        "models": [{"alias": "accumulator"}],
        "io": {"inputs": [{"name": "seed", "maps_to": "accumulator.value"}]},
    }

    overlay = server._map_initial_inputs(
        manifest,
        {
            "seed": 4,
            "accumulator.extra": 2,
            "accumulator": {"other": 1},
        },
    )

    assert overlay == {"accumulator": {"value": 4, "extra": 2, "other": 1}}


def test_run_lifecycle_maps_world_inputs_and_returns_visuals(tmp_path: Path) -> None:
    lab = _write_lab(tmp_path / "lab")
    manifest = _safe_yaml_load((lab / "lab.yaml").read_bytes())
    manifest["io"] = {"inputs": [{"name": "seed", "maps_to": "accumulator.value"}], "outputs": []}
    manifest["wiring"] = []
    (lab / "lab.yaml").write_bytes(_safe_yaml_dump(manifest))
    client, session = _client(lab)

    created = client.post(
        "/api/runs",
        json={
            "parameters": {
                "initial_inputs": {"seed": 4},
                "per_model": {"counter": {"step": 2}},
            },
            "simulation_config": {"duration": 0.1, "settle_steps": 1},
        },
    ).json()
    assert created["ok"] is True
    run_id = created["data"]["run"]["id"]
    run = session.get_run(run_id)
    assert run.thread is not None
    run.thread.join(timeout=5)

    for _ in range(20):
        run_payload = client.get(f"/api/runs/{run_id}").json()["data"]["run"]
        status = run_payload["status"]
        if status != "running":
            break
        time.sleep(0.05)
    assert status == "completed"
    assert run_payload["progress"]["progress_pct"] == 100.0

    results = client.get(f"/api/runs/{run_id}/results").json()
    assert results["ok"] is True
    visuals = results["data"]["results"]["visuals"]
    assert visuals[0]["module"] == "accumulator"
    assert visuals[0]["visuals"][0]["render"] == "table"
    assert visuals[0]["visuals"][0]["data"]["rows"][0]["total"] == 4.0
    logs = client.get(f"/api/runs/{run_id}/logs").json()
    assert logs["data"]["logs"]
    assert any("progress" in entry["message"] for entry in logs["data"]["logs"])


def test_run_overrides_normalize_world_inputs_and_deep_merge() -> None:
    manifest = {
        "models": [{"alias": "accumulator"}],
        "io": {
            "inputs": [
                {"name": "seed", "maps_to": "accumulator.value"},
                {"name": "label", "maps_to": "accumulator.label"},
            ]
        },
        "runtime": {
            "initial_inputs": {
                "accumulator": {"value": 1, "other": 2},
            }
        },
    }

    server._apply_run_overrides(
        manifest,
        parameters={"initial_inputs": {"seed": 4, "label": "run"}},
        simulation_config={},
    )

    assert manifest["runtime"]["initial_inputs"] == {
        "accumulator": {"value": 4, "other": 2, "label": "run"}
    }


def test_run_overrides_preserve_dotted_alias_input_refs() -> None:
    manifest = {
        "models": [{"alias": "nested.counter"}],
        "runtime": {"initial_inputs": {}},
    }

    server._apply_run_overrides(
        manifest,
        parameters={"initial_inputs": {"nested.counter.value": 5}},
        simulation_config={},
    )

    assert manifest["runtime"]["initial_inputs"] == {
        "nested.counter": {"value": 5}
    }


def test_active_run_results_remain_compatible_empty_payload(tmp_path: Path) -> None:
    lab = _write_lab(tmp_path / "lab")
    client, session = _client(lab)
    run = RunRecord(id="run-active", lab_id="lab", parameters=None, simulation_config=None)
    run.status = "running"
    session._runs[run.id] = run

    response = client.get(f"/api/runs/{run.id}/results")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "data": {"results": {}}, "error": None}


def test_api_error_envelope_for_missing_run(tmp_path: Path) -> None:
    client, _session = _client(_write_lab(tmp_path / "lab"))

    response = client.get("/api/runs/missing")

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["message"] == "Run not found: missing"
