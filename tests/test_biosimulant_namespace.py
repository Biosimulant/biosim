"""Compatibility tests for the primary biosimulant namespace."""
from __future__ import annotations

from pathlib import Path

import pytest


def _load_pyproject() -> dict:
    try:
        import tomllib
    except ImportError:  # pragma: no cover - Python < 3.11
        import tomli as tomllib  # type: ignore

    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        return tomllib.load(handle)


def test_biosimulant_reexports_biosim_runtime_api() -> None:
    import biosim
    import biosimulant
    import biosimulant.package_repo
    import biosimulant.signals
    import biosimulant.world

    assert biosimulant.__version__ == biosim.__version__
    assert biosimulant.BioWorld is biosim.BioWorld
    assert biosimulant.BioModule is biosim.BioModule
    assert biosimulant.build_package is biosim.build_package
    assert biosimulant.package_repo.validate_package_repo is not None
    assert biosimulant.world.BioWorld is biosim.BioWorld
    assert biosimulant.signals.SignalSpec is biosim.SignalSpec


def test_biosimulant_cli_help_uses_primary_command_name(capsys) -> None:
    from biosimulant.__main__ import main

    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: biosimulant" in captured.out
    assert "python -m biosim" not in captured.out


def test_biosimulant_pack_help_uses_primary_command_name(capsys) -> None:
    from biosimulant.__main__ import main

    with pytest.raises(SystemExit) as exc_info:
        main(["pack", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage: biosimulant pack" in captured.out
    assert "python -m biosim pack" not in captured.out


def test_pyproject_declares_biosimulant_distribution_and_console_script() -> None:
    pyproject = _load_pyproject()

    assert pyproject["project"]["name"] == "biosimulant"
    assert pyproject["project"]["scripts"]["biosimulant"] == "biosimulant.__main__:main"
    assert "src/biosim" in pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert "src/biosimulant" in pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]


def test_release_version_targets_first_biosimulant_package() -> None:
    import biosimulant

    assert biosimulant.__version__ == "0.0.11"
