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
        "hub",
        "runs",
        "runtime",
        "jobs",
        "self",
        "labs publish",
        "packages publish",
    ):
        assert specs[command].extension == DEFAULT_PRODUCT_EXTENSION

    assert specs["hub"].category == "hub/cloud"
    assert specs["runs"].category == "desktop/cloud"
    assert specs["runtime"].category == "desktop"


def test_biosimulant_namespace_exposes_extension_contracts() -> None:
    import biosimulant.extensions as extensions

    assert extensions.DEFAULT_PRODUCT_EXTENSION == DEFAULT_PRODUCT_EXTENSION
    assert extensions.extension_command_specs()


def test_missing_hub_extension_has_clean_actionable_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["hub", "labs", "list"], prog="biosimulant")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Biosimulant product extension required." in captured.err
    assert "Command: biosimulant hub labs list" in captured.err
    assert "Category: hub/cloud" in captured.err
    assert "Biosimulant Desktop/product CLI extension" in captured.err
    assert "Config file not found" not in captured.err


def test_missing_lab_publish_extension_is_not_an_argparse_unknown_command(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["labs", "publish", "./my-lab", "--visibility", "private"], prog="biosimulant")

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "Command: biosimulant labs publish ./my-lab --visibility private" in captured.err
    assert "Reason: Hub lab publishing" in captured.err
    assert "invalid choice" not in captured.err


def test_missing_package_publish_extension_can_return_json_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            ["packages", "publish", "biosimulant-packages.yaml", "--dry-run", "--json"],
            prog="biosimulant",
        )

    assert exc_info.value.code == 1
    payload = json.loads(capsys.readouterr().err)
    assert payload["error"] == "extension_unavailable"
    assert payload["command"] == "packages publish"
    assert payload["category"] == "hub"
    assert payload["extension"] == DEFAULT_PRODUCT_EXTENSION


def test_registered_extension_handles_hub_command() -> None:
    extension = RecordingExtension()
    register_extension(DEFAULT_PRODUCT_EXTENSION, extension)

    main(["hub", "labs", "list"], prog="biosimulant")

    assert extension.calls == [("hub", ["labs", "list"], "biosimulant hub")]


def test_registered_extension_handles_desktop_runtime_command() -> None:
    extension = RecordingExtension()
    register_extension(DEFAULT_PRODUCT_EXTENSION, extension)

    main(["runtime", "status"], prog="biosimulant")

    assert extension.calls == [("runtime", ["status"], "biosimulant runtime")]
