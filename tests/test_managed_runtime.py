from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from biosim import managed_runtime
from biosim.pack import PackageError


def test_run_package_with_managed_python_uses_in_process_runner_when_version_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[Path] = []
    package_file = Path("lab.bsilab")
    monkeypatch.setattr(
        managed_runtime,
        "requested_package_python_version",
        lambda _path: "3.12",
    )
    monkeypatch.setattr(managed_runtime, "_current_python_minor", lambda: "3.12")

    result = managed_runtime.run_package_with_managed_python(
        package_file,
        in_process_runner=lambda path: calls.append(Path(path)) or {"ok": True},
    )

    assert result == {"ok": True}
    assert calls == [package_file]


def test_run_package_with_managed_python_spawns_managed_runtime_on_mismatch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package_file = Path("lab.bsilab")
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        managed_runtime,
        "requested_package_python_version",
        lambda _path: "3.11",
    )
    monkeypatch.setattr(managed_runtime, "_current_python_minor", lambda: "3.12")

    def fake_ensure_executor_python(version: str) -> Path:
        calls["version"] = version
        return Path("/runtime/python")

    monkeypatch.setattr(
        managed_runtime,
        "ensure_executor_python",
        fake_ensure_executor_python,
    )

    def fake_run_child(python_path: Path, path: str | Path, *, install_deps: bool):
        calls["python_path"] = python_path
        calls["package_file"] = Path(path)
        calls["install_deps"] = install_deps
        return {"managed": True}

    monkeypatch.setattr(managed_runtime, "run_child_package", fake_run_child)

    result = managed_runtime.run_package_with_managed_python(
        package_file,
        install_deps=False,
    )

    assert result == {"managed": True}
    assert (
        "Re-launching package run under managed Python 3.11: /runtime/python"
        in capsys.readouterr().err
    )
    assert calls == {
        "version": "3.11",
        "python_path": Path("/runtime/python"),
        "package_file": package_file,
        "install_deps": False,
    }


def test_run_labs_serve_with_managed_python_skips_without_declared_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(managed_runtime.BIOSIM_MANAGED_RUNTIME_CHILD_ENV, raising=False)
    monkeypatch.setattr(
        managed_runtime,
        "requested_package_python_version",
        lambda _path: None,
    )
    monkeypatch.setattr(
        managed_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess should not run"),
    )

    result = managed_runtime.run_labs_serve_with_managed_python(
        Path("lab.bsilab"),
        ["labs", "serve", "lab"],
    )

    assert result is None


def test_run_labs_serve_with_managed_python_skips_when_version_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(managed_runtime.BIOSIM_MANAGED_RUNTIME_CHILD_ENV, raising=False)
    monkeypatch.setattr(
        managed_runtime,
        "requested_package_python_version",
        lambda _path: "3.12",
    )
    monkeypatch.setattr(managed_runtime, "_current_python_minor", lambda: "3.12")
    monkeypatch.setattr(
        managed_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess should not run"),
    )

    result = managed_runtime.run_labs_serve_with_managed_python(
        Path("lab.bsilab"),
        ["labs", "serve", "lab"],
    )

    assert result is None


def test_run_labs_serve_with_managed_python_spawns_on_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, object] = {}
    monkeypatch.delenv(managed_runtime.BIOSIM_MANAGED_RUNTIME_CHILD_ENV, raising=False)
    monkeypatch.setattr(
        managed_runtime,
        "requested_package_python_version",
        lambda _path: "3.10",
    )
    monkeypatch.setattr(managed_runtime, "_current_python_minor", lambda: "3.14")

    def fake_ensure_executor_python(version: str) -> Path:
        observed["version"] = version
        return Path("/runtime/python")

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["env"] = kwargs["env"]
        return SimpleNamespace(returncode=7)

    monkeypatch.setattr(
        managed_runtime,
        "ensure_executor_python",
        fake_ensure_executor_python,
    )
    monkeypatch.setattr(managed_runtime.subprocess, "run", fake_run)

    result = managed_runtime.run_labs_serve_with_managed_python(
        Path("lab.bsilab"),
        ["labs", "serve", "/lab", "--port", "9999"],
    )

    assert result == 7
    assert observed["version"] == "3.10"
    assert observed["args"] == [
        "/runtime/python",
        "-m",
        "biosim",
        "labs",
        "serve",
        "/lab",
        "--port",
        "9999",
    ]
    assert observed["env"][managed_runtime.BIOSIM_MANAGED_RUNTIME_CHILD_ENV] == "1"


def test_run_labs_serve_with_managed_python_child_env_skips_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(managed_runtime.BIOSIM_MANAGED_RUNTIME_CHILD_ENV, "1")
    monkeypatch.setattr(
        managed_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("subprocess should not run"),
    )

    result = managed_runtime.run_labs_serve_with_managed_python(
        Path("lab.bsilab"),
        ["labs", "serve", "lab"],
    )

    assert result is None


def test_uv_command_prefers_configured_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    uv_path = tmp_path / "uv"
    uv_path.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setenv(managed_runtime.BIOSIM_UV_PATH_ENV, str(uv_path))

    assert managed_runtime._uv_command() == [str(uv_path)]


def test_uv_command_rejects_bad_configured_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(managed_runtime.BIOSIM_UV_PATH_ENV, str(tmp_path / "missing-uv"))

    with pytest.raises(PackageError, match=managed_runtime.BIOSIM_UV_PATH_ENV):
        managed_runtime._uv_command()


def test_run_child_package_parses_json_result(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["env"] = kwargs["env"]
        return SimpleNamespace(
            returncode=0,
            stdout='model log\n{"outputs": ["state"]}\n',
            stderr="",
        )

    monkeypatch.setattr(managed_runtime.subprocess, "run", fake_run)

    result = managed_runtime.run_child_package(
        Path("/runtime/python"),
        Path("lab.bsilab"),
        install_deps=True,
    )

    assert result == {"outputs": ["state"]}
    assert observed["args"][-2:] == ["lab.bsilab", "1"]
    assert observed["env"][managed_runtime.BIOSIM_MANAGED_RUNTIME_CHILD_ENV] == "1"


def test_run_child_package_reports_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        managed_runtime.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="boom",
        ),
    )

    with pytest.raises(PackageError, match="Managed Python runtime failed"):
        managed_runtime.run_child_package(
            Path("/runtime/python"),
            Path("lab.bsilab"),
            install_deps=True,
        )


def test_parse_json_result_requires_object() -> None:
    with pytest.raises(PackageError, match="without a JSON package result"):
        managed_runtime._parse_json_result(json.dumps(["not", "an", "object"]))
