from __future__ import annotations

import json
from typing import Sequence

import pytest

from biosim.__main__ import main
from biosim.extensions import (
    DEFAULT_PRODUCT_EXTENSION,
    clear_extensions,
    extension_command_specs,
    register_extension,
)


class RecordingExtension:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], str]] = []

    def run_cli_command(self, command: str, argv: Sequence[str], *, prog: str) -> int:
        self.calls.append((command, list(argv), prog))
        return 0


@pytest.fixture(autouse=True)
def _clear_extensions() -> None:
    clear_extensions()
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
