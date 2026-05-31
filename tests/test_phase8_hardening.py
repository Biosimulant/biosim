from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from biosim.__main__ import main
from biosim.pack import build_package


def test_labs_validate_source_tree_does_not_build_package(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    temp_root = _isolated_system_temp(tmp_path, monkeypatch)
    lab_dir = tmp_path / "validated-lab"
    main(
        ["labs", "init", str(lab_dir), "--name", "Validated Lab"],
        prog="biosimulant",
    )
    capsys.readouterr()

    with patch("biosim.__main__.build_package") as build_package:
        main(["labs", "validate", str(lab_dir), "--json"], prog="biosimulant")

    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["package"] == "local/validated-lab"
    assert payload["metadata"]["source_format"] == "source-tree"
    build_package.assert_not_called()
    _assert_no_lab_temp_residue(temp_root)


def test_labs_run_and_serve_clean_temporary_directories(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    temp_root = _isolated_system_temp(tmp_path, monkeypatch)
    lab_dir = tmp_path / "runtime-lab"
    main(
        ["labs", "init", str(lab_dir), "--name", "Runtime Lab"],
        prog="biosimulant",
    )
    capsys.readouterr()

    main(
        ["labs", "run", str(lab_dir), "--no-install-deps", "--json"],
        prog="biosimulant",
    )
    run_payload = json.loads(capsys.readouterr().out)
    assert run_payload["package"] == "local/runtime-lab"
    _assert_no_lab_temp_residue(temp_root)

    with patch("biosim.__main__.run_simui") as run_simui:
        main(
            [
                "labs",
                "serve",
                str(lab_dir),
                "--port",
                "9999",
                "--no-install-deps",
                "--json",
            ],
            prog="biosimulant",
        )

    serve_payload = json.loads(capsys.readouterr().out)
    assert serve_payload["package"] == "local/runtime-lab"
    run_simui.assert_called_once()
    _assert_no_lab_temp_residue(temp_root)


def test_labs_validate_archive_still_uses_archive_validation(
    tmp_path: Path,
    capsys,
) -> None:
    lab_dir = tmp_path / "archive-lab"
    main(
        ["labs", "init", str(lab_dir), "--name", "Archive Lab"],
        prog="biosimulant",
    )
    capsys.readouterr()
    package_file = build_package(lab_dir, output_path=tmp_path / "archive.bsilab")

    main(["labs", "validate", str(package_file), "--json"], prog="biosimulant")

    payload = json.loads(capsys.readouterr().out)
    assert payload["valid"] is True
    assert payload["package"] == "local/archive-lab"
    assert payload["metadata"]["package_type"] == "lab"
    assert "source_format" not in payload["metadata"]


def _isolated_system_temp(tmp_path: Path, monkeypatch) -> Path:
    temp_root = tmp_path / "system-temp"
    temp_root.mkdir()
    monkeypatch.setenv("TMPDIR", str(temp_root))
    monkeypatch.setattr(tempfile, "tempdir", None)
    return temp_root


def _assert_no_lab_temp_residue(temp_root: Path) -> None:
    assert not list(temp_root.glob("biosim-lab-*"))
    assert not list(temp_root.glob("biosim-pack-*"))
