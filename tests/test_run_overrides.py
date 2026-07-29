from __future__ import annotations

import json
from pathlib import Path

import yaml

from biosim.__main__ import _lab_path_with_run_inputs
from biosim.run_overrides import apply_run_overrides, map_initial_inputs


def test_run_overrides_map_public_inputs_and_runtime() -> None:
    manifest = {
        "models": [{"alias": "cell", "parameters": {"baseline": 1}}],
        "io": {
            "inputs": [
                {"name": "dose", "maps_to": "cell.drug.dose"},
            ]
        },
        "runtime": {
            "duration": 10,
            "communication_step": 1,
            "initial_inputs": {"cell": {"existing": 2}},
        },
    }

    apply_run_overrides(
        manifest,
        parameters={
            "initial_inputs": {"dose": 5, "cell.direct": 3},
            "per_model": {"cell": {"baseline": 9}},
        },
        simulation_config={"duration": 20, "settle_steps": 2},
    )

    assert manifest["runtime"] == {
        "duration": 20,
        "communication_step": 1,
        "settle_steps": 2,
        "initial_inputs": {
            "cell": {
                "existing": 2,
                "drug.dose": 5,
                "direct": 3,
            }
        },
    }
    assert manifest["models"][0]["parameters"] == {"baseline": 9}


def test_map_initial_inputs_preserves_unknown_public_keys() -> None:
    assert map_initial_inputs({"models": []}, {"temperature": 37}) == {
        "temperature": 37
    }


def test_run_input_staging_does_not_mutate_source(tmp_path: Path) -> None:
    lab_dir = tmp_path / "lab"
    lab_dir.mkdir()
    manifest_path = lab_dir / "lab.yaml"
    manifest_path.write_text(
        """\
schema_version: "2.0"
title: Test
package: tests/test
version: 1.0.0
models: []
wiring: []
runtime:
  duration: 10
  communication_step: 1
""",
        encoding="utf-8",
    )
    original = manifest_path.read_bytes()
    run_inputs = tmp_path / "run-inputs.json"
    run_inputs.write_text(
        json.dumps(
            {
                "parameters": {},
                "simulation_config": {"duration": 25},
            }
        ),
        encoding="utf-8",
    )

    with _lab_path_with_run_inputs(lab_dir, run_inputs) as staged:
        assert staged != lab_dir
        rendered = yaml.safe_load((staged / "lab.yaml").read_text(encoding="utf-8"))
        assert rendered["runtime"]["duration"] == 25

    assert manifest_path.read_bytes() == original
