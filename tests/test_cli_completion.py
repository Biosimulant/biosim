from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytest.importorskip("argcomplete")


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


def _completion_values(comp_line: str, tmp_path: Path) -> list[str]:
    output_file = tmp_path / "argcomplete.out"
    env = os.environ.copy()
    env.update(
        {
            "_ARGCOMPLETE": "1",
            "COMP_LINE": comp_line,
            "COMP_POINT": str(len(comp_line)),
            "COMP_TYPE": "9",
            "_ARGCOMPLETE_STDOUT_FILENAME": str(output_file),
            "PYTHONPATH": os.pathsep.join(
                [str(SRC_ROOT), env.get("PYTHONPATH", "")]
            ),
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "biosimulant"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    raw_output = (
        output_file.read_text(encoding="utf-8")
        if output_file.exists()
        else result.stdout
    )
    return [
        value.strip().removesuffix("\\")
        for value in raw_output.replace("\x0b", "\n").splitlines()
        if value.strip()
    ]


def test_register_python_argcomplete_emits_biosimulant_hook() -> None:
    command = shutil.which("register-python-argcomplete")
    args = (
        [command, "biosimulant"]
        if command
        else [
            sys.executable,
            "-m",
            "argcomplete.scripts.register_python_argcomplete",
            "biosimulant",
        ]
    )
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "biosimulant" in result.stdout
    assert "python_argcomplete" in result.stdout


def test_completion_parser_exposes_nested_labs_commands() -> None:
    import biosim.__main__ as cli

    parser = cli._build_completion_parser(prog="biosimulant")

    run_args = parser.parse_args(["labs", "run", "--no-install-deps", "--json"])
    package_args = parser.parse_args(["labs", "package", "--out", "dist"])
    release_args = parser.parse_args(["labs", "release", "validate", "manifest.yaml"])

    assert run_args.command == "run"
    assert run_args.no_install_deps is True
    assert run_args.json_output is True
    assert package_args.command == "package"
    assert package_args.out == Path("dist")
    assert release_args.command == "release"
    assert release_args.release_command == "validate"


def test_completion_env_and_top_level_completer(monkeypatch: pytest.MonkeyPatch) -> None:
    import biosim.__main__ as cli

    monkeypatch.setenv("COMP_LINE", "python -m biosimulant labs run")
    monkeypatch.setenv("COMP_POINT", str(len("python -m biosimulant labs run")))
    monkeypatch.setattr(cli, "_path_completer", lambda prefix, **kwargs: [])

    assert cli._completion_args_from_env() == ["labs", "run"]
    assert cli._top_level_config_completer("l") == ["labs "]


def test_top_level_completion_includes_labs(tmp_path: Path) -> None:
    completions = _completion_values("biosimulant l", tmp_path)

    assert "labs" in completions


def test_nested_labs_completion_includes_core_commands(tmp_path: Path) -> None:
    completions = _completion_values("biosimulant labs ", tmp_path)

    assert {"run", "validate", "package"}.issubset(set(completions))


def test_labs_option_completion(tmp_path: Path) -> None:
    run_completions = _completion_values("biosimulant labs run --", tmp_path)
    package_completions = _completion_values("biosimulant labs package --", tmp_path)

    assert "--json" in run_completions
    assert "--no-install-deps" in run_completions
    assert "--out" in package_completions


def test_path_completion_for_config_and_lab_paths(tmp_path: Path) -> None:
    (tmp_path / "config.yaml").write_text(
        "runtime:\n  communication_step: 0.1\n",
        encoding="utf-8",
    )
    (tmp_path / "lab-one").mkdir()

    config_completions = _completion_values("biosimulant con", tmp_path)
    lab_completions = _completion_values("biosimulant labs run lab-", tmp_path)

    assert any(value.startswith("config.yaml") for value in config_completions)
    assert any(value.startswith("lab-one") for value in lab_completions)
