from __future__ import annotations

import json
from pathlib import Path

import pytest

from biosim import workspace
from biosim.pack import PackageError


def _write_minimal_lab(path: Path, *, title: str = "Lab", package: str = "local/lab") -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "lab.yaml").write_text(
        f"""schema_version: "2.0"
title: "{title}"
description: null
package: {package}
version: 0.1.0
models: []
children: []
wiring: []
runtime:
  communication_step: 1.0
  duration: 1.0
  initial_inputs: {{}}
""",
        encoding="utf-8",
    )


def test_workspace_create_scan_delete_and_metadata_error_paths(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(PackageError, match="must be a directory"):
        workspace.create_lab(file_path, name="Bad")

    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "existing.txt").write_text("x", encoding="utf-8")
    with pytest.raises(PackageError, match="not empty"):
        workspace.create_lab(nonempty, name="Bad")

    with pytest.raises(PackageError, match="scan root not found"):
        workspace.list_labs(tmp_path / "missing")
    with pytest.raises(PackageError, match="scan root must be a directory"):
        workspace.list_labs(file_path)

    lab = tmp_path / "lab"
    workspace.create_lab(lab, name="Managed", empty=True)
    assert workspace.get_lab(lab / "lab.yaml").path == lab.resolve()
    with pytest.raises(PackageError, match="without --yes"):
        workspace.delete_lab(lab)

    metadata_path = lab / ".biosimulant" / "lab.json"
    metadata_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(PackageError, match="metadata must be a mapping"):
        workspace.get_lab(lab)


def test_workspace_identifier_resolution_legacy_metadata_and_scan_edges(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write_minimal_lab(first, title="First", package="local/shared")
    _write_minimal_lab(second, title="Second", package="local/shared")

    with pytest.raises(PackageError, match="Multiple labs match"):
        workspace.get_lab("local/shared", root=tmp_path)

    hidden = tmp_path / ".venv" / "hidden"
    _write_minimal_lab(hidden, title="Hidden", package="local/hidden")
    yml_lab = tmp_path / "yml-lab"
    yml_lab.mkdir()
    (yml_lab / "lab.yml").write_text((first / "lab.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    listed = workspace.list_labs(tmp_path)
    listed_paths = {Path(item["path"]).name for item in listed}
    assert "hidden" not in listed_paths
    assert "yml-lab" in listed_paths

    legacy = tmp_path / "legacy"
    _write_minimal_lab(legacy, title="Legacy", package="local/legacy")
    legacy_metadata = {
        "kind": "lab",
        "local_id": "legacy-id",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }
    (legacy / ".biosimulant-project.json").write_text(
        json.dumps(legacy_metadata),
        encoding="utf-8",
    )

    record = workspace.get_lab("legacy-id", root=tmp_path)

    assert record.id == "legacy-id"
    workspace.save_lab(legacy, allow_draft=True)
    assert (legacy / ".biosimulant" / "lab.json").is_file()


def test_workspace_save_draft_wiring_and_model_error_paths(tmp_path: Path) -> None:
    lab = tmp_path / "lab"
    workspace.create_lab(lab, name="Draft", empty=True)

    file_target = tmp_path / "file.txt"
    file_target.write_text("x", encoding="utf-8")
    with pytest.raises(PackageError, match="Lab path must be a directory"):
        workspace.save_lab(file_target, manifest={"models": []})

    with pytest.raises(PackageError, match="models must be a list"):
        workspace._validate_draft_lab_manifest({"models": "bad"})
    with pytest.raises(PackageError, match="model entries"):
        workspace._validate_draft_lab_manifest({"models": ["bad"]})
    with pytest.raises(PackageError, match="alias"):
        workspace._validate_draft_lab_manifest({"models": [{"alias": ""}]})
    with pytest.raises(PackageError, match="Duplicate"):
        workspace._validate_draft_lab_manifest({"models": [{"alias": "a"}, {"alias": "a"}]})
    with pytest.raises(PackageError, match="children"):
        workspace._validate_draft_lab_manifest({"models": [], "children": "bad"})
    with pytest.raises(PackageError, match="wiring"):
        workspace._validate_draft_lab_manifest({"models": [], "children": [], "wiring": "bad"})
    with pytest.raises(PackageError, match="runtime"):
        workspace._validate_draft_lab_manifest({"models": [], "children": [], "wiring": [], "runtime": "bad"})

    layout_path = lab / "wiring-layout.json"
    workspace.save_lab(lab, wiring_layout={"hello": {"x": 1}}, allow_draft=True)
    assert layout_path.is_file()
    workspace.save_lab(lab, wiring_layout=None, allow_draft=True)
    assert not layout_path.exists()

    external_model = tmp_path / "external-model"
    external_model.mkdir()
    (external_model / "model.yaml").write_text(
        """schema_version: "2.0"
title: External
standard: other
package: local/external
version: 0.1.0
biosim:
  entrypoint: "src.model:Model"
""",
        encoding="utf-8",
    )
    with pytest.raises(PackageError, match="inside the lab source tree"):
        workspace.add_model(external_model, lab=lab)
    with pytest.raises(PackageError, match="not found"):
        workspace.vendor_model(tmp_path / "missing-model", lab=lab)
