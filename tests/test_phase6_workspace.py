from __future__ import annotations

import json
from pathlib import Path

import pytest

from biosim.__main__ import main
from biosim.pack import validate_package


def test_local_lab_workspace_crud_package_and_metadata(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    lab_dir = tmp_path / "managed-lab"
    main(
        ["labs", "create", str(lab_dir), "--name", "Managed Lab", "--json"],
        prog="biosimulant",
    )
    create_payload = json.loads(capsys.readouterr().out)
    metadata_path = lab_dir / ".biosimulant" / "lab.json"
    assert create_payload["created"] is True
    assert metadata_path.is_file()
    assert create_payload["id"] == json.loads(metadata_path.read_text())["id"]
    assert "lab_" not in (lab_dir / "lab.yaml").read_text(encoding="utf-8")

    explicit_dir = tmp_path / "explicit-id-lab"
    main(
        [
            "labs",
            "create",
            str(explicit_dir),
            "--name",
            "Explicit ID Lab",
            "--id",
            "desktop-lab-id",
            "--json",
        ],
        prog="biosimulant",
    )
    explicit_payload = json.loads(capsys.readouterr().out)
    assert explicit_payload["id"] == "desktop-lab-id"

    main(["labs", "list", str(tmp_path), "--json"], prog="biosimulant")
    list_payload = json.loads(capsys.readouterr().out)
    assert {lab["id"] for lab in list_payload["labs"]} == {
        create_payload["id"],
        "desktop-lab-id",
    }

    main(
        ["labs", "get", create_payload["id"], "--root", str(tmp_path), "--json"],
        prog="biosimulant",
    )
    get_payload = json.loads(capsys.readouterr().out)
    assert get_payload["lab"]["path"] == str(lab_dir.resolve())

    main(
        [
            "labs",
            "rename",
            create_payload["id"],
            "Root Renamed Lab",
            "--root",
            str(tmp_path),
            "--json",
        ],
        prog="biosimulant",
    )
    root_rename_payload = json.loads(capsys.readouterr().out)
    assert root_rename_payload["lab"]["title"] == "Root Renamed Lab"

    monkeypatch.chdir(lab_dir)
    main(["labs", "save", "--json"], prog="biosimulant")
    save_payload = json.loads(capsys.readouterr().out)
    assert save_payload["saved"] is True
    assert save_payload["lab"]["id"] == create_payload["id"]

    manifest_file = tmp_path / "manifest.json"
    layout_file = tmp_path / "layout.json"
    manifest_file.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "title": "Saved Manifest Lab",
                "description": "saved from payload",
                "package": "local/saved-manifest-lab",
                "version": "0.1.0",
                "models": [
                    {
                        "path": "models/hello",
                        "alias": "hello",
                    }
                ],
                "children": [],
                "wiring": [],
                "runtime": {
                    "communication_step": 1.0,
                    "duration": 1.0,
                    "initial_inputs": {},
                },
            }
        ),
        encoding="utf-8",
    )
    layout_file.write_text(json.dumps({"nodes": [{"id": "hello"}]}), encoding="utf-8")
    main(
        [
            "labs",
            "save",
            "--manifest-file",
            str(manifest_file),
            "--wiring-layout-file",
            str(layout_file),
            "--json",
        ],
        prog="biosimulant",
    )
    payload_save = json.loads(capsys.readouterr().out)
    assert payload_save["saved"] is True
    assert "Saved Manifest Lab" in (lab_dir / "lab.yaml").read_text(encoding="utf-8")
    assert json.loads((lab_dir / "wiring-layout.json").read_text())["nodes"][0]["id"] == "hello"

    main(["labs", "rename", "Renamed Lab", "--json"], prog="biosimulant")
    rename_payload = json.loads(capsys.readouterr().out)
    assert rename_payload["lab"]["title"] == "Renamed Lab"

    out_dir = tmp_path / "dist"
    main(["labs", "package", "--out", str(out_dir), "--json"], prog="biosimulant")
    package_payload = json.loads(capsys.readouterr().out)
    package_file = Path(package_payload["package_file"])
    assert package_file.is_file()
    assert validate_package(package_file).valid

    delete_dir = tmp_path / "delete-me"
    main(
        ["labs", "create", str(delete_dir), "--name", "Delete Me", "--json"],
        prog="biosimulant",
    )
    capsys.readouterr()
    main(
        ["labs", "delete", str(delete_dir), "--yes", "--json"],
        prog="biosimulant",
    )
    delete_payload = json.loads(capsys.readouterr().out)
    assert delete_payload["deleted"] is True
    assert not delete_dir.exists()


def test_local_lab_source_tree_model_edits(
    tmp_path: Path,
    capsys,
) -> None:
    lab_dir = tmp_path / "model-lab"
    main(
        ["labs", "create", str(lab_dir), "--name", "Model Lab", "--json"],
        prog="biosimulant",
    )
    capsys.readouterr()

    extra_model = lab_dir / "models" / "extra"
    replacement_model = lab_dir / "models" / "replacement"
    external_model = tmp_path / "external-model"
    _write_model(extra_model, title="Extra Model")
    _write_model(replacement_model, title="Replacement Model")
    _write_model(external_model, title="Vendored Model")

    main(
        [
            "labs",
            "add-model",
            "models/extra",
            "--lab",
            str(lab_dir),
            "--alias",
            "extra",
            "--json",
        ],
        prog="biosimulant",
    )
    add_payload = json.loads(capsys.readouterr().out)
    assert add_payload["added"] is True
    assert add_payload["alias"] == "extra"

    main(
        [
            "labs",
            "change-model",
            "hello",
            "models/replacement",
            "--lab",
            str(lab_dir),
            "--json",
        ],
        prog="biosimulant",
    )
    change_payload = json.loads(capsys.readouterr().out)
    assert change_payload["changed"] is True

    main(
        [
            "labs",
            "vendor-model",
            str(external_model),
            "--lab",
            str(lab_dir),
            "--alias",
            "vendored",
            "--json",
        ],
        prog="biosimulant",
    )
    vendor_payload = json.loads(capsys.readouterr().out)
    assert vendor_payload["vendored"] is True
    assert (lab_dir / "models" / "vendored" / "model.yaml").is_file()

    main(["labs", "inspect-owned", str(lab_dir), "--json"], prog="biosimulant")
    inspect_payload = json.loads(capsys.readouterr().out)
    aliases = {model["alias"] for model in inspect_payload["models"]}
    assert {"hello", "extra", "vendored"} <= aliases
    assert all(model["owned"] for model in inspect_payload["models"])

    main(
        ["labs", "package", str(lab_dir), "--out", str(tmp_path / "out"), "--json"],
        prog="biosimulant",
    )
    package_payload = json.loads(capsys.readouterr().out)
    assert validate_package(package_payload["package_file"]).valid


def test_local_lab_save_can_mark_empty_draft_managed(
    tmp_path: Path,
    capsys,
) -> None:
    lab_dir = tmp_path / "draft-lab"
    main(
        [
            "labs",
            "create",
            str(lab_dir),
            "--name",
            "Draft Lab",
            "--empty",
            "--json",
        ],
        prog="biosimulant",
    )
    capsys.readouterr()

    main(
        ["labs", "save", str(lab_dir), "--allow-draft", "--json"],
        prog="biosimulant",
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["saved"] is True
    assert payload["lab"]["managed"] is True


def test_local_lab_save_can_create_first_manifest_snapshot(
    tmp_path: Path,
    capsys,
) -> None:
    lab_dir = tmp_path / "first-save-lab"
    lab_dir.mkdir()
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "title": "First Save Lab",
                "models": [],
                "children": [],
                "wiring": [],
                "runtime": {
                    "duration": 10.0,
                    "communication_step": 1.0,
                    "initial_inputs": {},
                },
            }
        ),
        encoding="utf-8",
    )

    main(
        [
            "labs",
            "save",
            str(lab_dir),
            "--manifest-file",
            str(manifest_file),
            "--allow-draft",
            "--json",
        ],
        prog="biosimulant",
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["saved"] is True
    assert (lab_dir / "lab.yaml").is_file()
    assert payload["lab"]["title"] == "First Save Lab"


def test_hub_only_lab_commands_remain_extension_owned(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["labs", "publish", "./lab", "--json"], prog="biosimulant")

    assert exc_info.value.code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "extension_unavailable"
    assert payload["command"] == "labs publish"


def test_top_level_models_surface_is_removed(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["models", "list", "--json"], prog="biosimulant")

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "command_removed"
    assert payload["command"] == "models"
    assert "labs add-model" in payload["replacement"]


def _write_model(path: Path, *, title: str) -> None:
    path.mkdir(parents=True)
    path.joinpath("model.yaml").write_text(
        f"""schema_version: "2.0"
title: "{title}"
description: null
package: local/{path.name}
version: 0.1.0
biosim:
  entrypoint: "src.model:Model"
  communication_step: 1.0
""",
        encoding="utf-8",
    )
    src_dir = path / "src"
    src_dir.mkdir()
    src_dir.joinpath("model.py").write_text(
        """from biosim import BioModule


class Model(BioModule):
    pass
""",
        encoding="utf-8",
    )
