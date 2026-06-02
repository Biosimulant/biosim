from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pytest

from biosim.__main__ import main
import biosim.extensions as extension_module
from biosim.extensions import (
    DEFAULT_PRODUCT_EXTENSION,
    DESKTOP_CLI_ENV,
    DISABLE_DESKTOP_DELEGATION_ENV,
    clear_extensions,
    extension_command_specs,
    register_extension,
    run_extension_command,
)


class RecordingExtension:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], str]] = []

    def run_cli_command(self, command: str, argv: Sequence[str], *, prog: str) -> int:
        self.calls.append((command, list(argv), prog))
        return 0


@pytest.fixture(autouse=True)
def _clear_extensions(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_extensions()
    monkeypatch.setenv(DISABLE_DESKTOP_DELEGATION_ENV, "1")
    yield
    clear_extensions()


def test_extension_command_metadata_marks_product_only_surface() -> None:
    specs = {spec.command: spec for spec in extension_command_specs()}

    for command in (
        "auth",
        "runs",
        "runtime",
        "jobs",
        "self",
        "labs publish",
        "labs sync-status",
        "labs release publish",
        "labs release ci",
    ):
        assert specs[command].extension == DEFAULT_PRODUCT_EXTENSION

    assert specs["runs"].category == "desktop/cloud"
    assert specs["runtime"].category == "desktop"
    assert "hub" not in specs
    assert "packages publish" not in specs


def test_biosimulant_namespace_exposes_extension_contracts() -> None:
    import biosimulant.extensions as extensions

    assert extensions.DEFAULT_PRODUCT_EXTENSION == DEFAULT_PRODUCT_EXTENSION
    assert extensions.extension_command_specs()


def test_removed_hub_surface_has_clean_removed_command_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["hub", "labs", "list"], prog="biosimulant")

    assert exc_info.value.code == 2
    captured = capsys.readouterr()
    assert "Command removed: biosimulant hub" in captured.err
    assert "biosimulant labs search" in captured.err
    assert "Config file not found" not in captured.err


def test_removed_packages_surface_can_return_json_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["packages", "validate", "biosimulant-packages.yaml", "--json"], prog="biosimulant")

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "command_removed"
    assert payload["command"] == "packages"
    assert "labs release" in payload["replacement"]


def test_removed_labs_export_surface_can_return_json_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["labs", "export", "./lab", "--json"], prog="biosimulant")

    assert exc_info.value.code == 2
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "command_removed"
    assert payload["command"] == "labs export"
    assert "labs package" in payload["replacement"]


def test_missing_lab_publish_extension_is_not_an_argparse_unknown_command(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["labs", "publish", "./my-lab", "--visibility", "private"], prog="biosimulant")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Command: biosimulant labs publish ./my-lab --visibility private" in captured.err
    assert "Reason: Hub lab publishing" in captured.err
    assert "https://biosimulant.com" in captured.err
    assert "invalid choice" not in captured.err


def test_missing_lab_release_publish_extension_can_return_json_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "labs",
                "release",
                "publish",
                "biosimulant-packages.yaml",
                "--dry-run",
                "--json",
            ],
            prog="biosimulant",
        )

    assert exc_info.value.code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "extension_unavailable"
    assert payload["command"] == "labs release publish"
    assert payload["category"] == "hub"
    assert payload["extension"] == DEFAULT_PRODUCT_EXTENSION


def test_registered_extension_handles_lab_release_command() -> None:
    extension = RecordingExtension()
    register_extension(DEFAULT_PRODUCT_EXTENSION, extension)

    main(["labs", "release", "publish", "biosimulant-packages.yaml"], prog="biosimulant")

    assert extension.calls == [
        (
            "labs release publish",
            ["release", "publish", "biosimulant-packages.yaml"],
            "biosimulant labs",
        )
    ]


def test_registered_extension_handles_desktop_runtime_command() -> None:
    extension = RecordingExtension()
    register_extension(DEFAULT_PRODUCT_EXTENSION, extension)

    main(["runtime", "status"], prog="biosimulant")

    assert extension.calls == [("runtime", ["status"], "biosimulant runtime")]


def test_missing_extension_delegates_to_desktop_cli_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[list[str], dict[str, str] | None]] = []
    candidate = extension_module.DesktopCliCandidate(Path("/tmp/desktop-biosimulant"))

    monkeypatch.delenv(DISABLE_DESKTOP_DELEGATION_ENV, raising=False)
    monkeypatch.setattr(extension_module, "_find_desktop_cli", lambda: candidate)
    monkeypatch.setattr(
        extension_module.subprocess,
        "call",
        lambda args, env=None: calls.append((list(args), env)) or 17,
    )

    exit_code = run_extension_command(
        "labs open",
        ["open", "."],
        prog="biosimulant labs",
    )

    assert exit_code == 17
    assert calls[0][0] == ["/tmp/desktop-biosimulant", "labs", "open", "."]
    assert calls[0][1] is not None
    assert calls[0][1][DISABLE_DESKTOP_DELEGATION_ENV] == "1"


def test_desktop_cli_discovery_uses_explicit_env_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    desktop_cli = tmp_path / "biosimulant"
    desktop_cli.write_text("#!/bin/sh\n", encoding="utf-8")
    desktop_cli.chmod(0o755)

    monkeypatch.delenv(DISABLE_DESKTOP_DELEGATION_ENV, raising=False)
    monkeypatch.setenv(DESKTOP_CLI_ENV, str(desktop_cli))
    monkeypatch.setattr(
        extension_module,
        "_is_desktop_cli",
        lambda candidate: candidate.executable == desktop_cli.resolve(),
    )

    found = extension_module._find_desktop_cli()

    assert found == extension_module.DesktopCliCandidate(desktop_cli.resolve())
