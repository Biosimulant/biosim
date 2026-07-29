"""Unified headless CLI contract tests.

The filename is retained so downstream test selectors continue to work during
the migration from the former Desktop-extension CLI.
"""
from __future__ import annotations

import importlib
import io
import json
import os
import stat
from pathlib import Path

import pytest

from biosim import credentials
from biosimulant.__main__ import COMMANDS, main


def test_doctor_uses_schema_v1_envelope_with_global_flag_anywhere(capsys) -> None:
    main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["meta"]["schemaVersion"] == "1"
    assert payload["meta"]["command"] == "doctor"
    assert isinstance(payload["data"]["checks"], dict)


def test_doctor_has_concise_human_output(capsys) -> None:
    main(["doctor"])
    output = capsys.readouterr().out
    assert "Biosimulant doctor succeeded" in output
    assert "Healthy:" in output


def test_doctor_accepts_the_managed_uv_sidecar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uv_path = tmp_path / ("uv.exe" if os.name == "nt" else "uv")
    uv_path.write_bytes(b"sidecar")
    monkeypatch.setenv("BIOSIM_UV_PATH", str(uv_path))

    main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["data"]["checks"]["uv"] == {
        "ok": True,
        "path": str(uv_path.resolve()),
    }


def test_validate_alias_and_global_options_delegate_to_canonical_labs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli = importlib.import_module("biosimulant.__main__")
    calls: list[tuple[list[str], str]] = []

    def fake_legacy(argv: list[str], *, prog: str) -> None:
        calls.append((argv, prog))
        print(json.dumps({"command": "labs.validate", "valid": True}))

    monkeypatch.setattr(cli, "_legacy_main", fake_legacy)
    main(["--no-open", "validate", ".", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert calls == [(["labs", "validate", ".", "--json"], "biosimulant")]
    assert payload["ok"] is True
    assert payload["data"]["command"] == "labs.validate"


def test_json_stream_finishes_with_one_terminal_result(capsys) -> None:
    main(["commands", "list", "--json-stream"])
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 2
    events = [json.loads(line) for line in lines]
    assert [event["type"] for event in events] == ["progress", "result"]
    assert [event["seq"] for event in events] == [1, 2]
    assert events[0]["stage"] == "starting"
    assert events[0]["percentage"] == 0
    assert events[1]["stage"] == "complete"
    assert events[1]["percentage"] == 100
    assert events[1]["result"]["ok"] is True


@pytest.mark.parametrize("command_path, _summary", COMMANDS)
def test_every_public_command_has_headless_help(
    command_path: str,
    _summary: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([*command_path.split(), "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert output.startswith("usage: biosimulant")


def test_migration_json_adapters_preserve_previous_shapes(capsys) -> None:
    main(["--legacy-json=bare", "commands", "list"])
    bare = json.loads(capsys.readouterr().out)
    assert "commands" in bare
    assert "ok" not in bare

    main(["commands", "list", "--legacy-json", "desktop"])
    desktop = json.loads(capsys.readouterr().out)
    assert desktop["ok"] is True
    assert "commands" in desktop["data"]
    assert desktop["error"] is None
    assert desktop["meta"]["format"] == "json"
    assert desktop["meta"]["cwd"]
    assert "schemaVersion" not in desktop["meta"]


def test_invalid_migration_json_adapter_is_usage_error(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["doctor", "--legacy-json", "unknown"])
    assert exc_info.value.code == 2
    assert "--legacy-json" in capsys.readouterr().err


def test_headless_auth_stores_registry_scoped_owner_only_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    credential_file = tmp_path / "credentials.json"
    monkeypatch.setenv(credentials.CREDENTIALS_FILE_ENV, str(credential_file))
    monkeypatch.setenv(credentials.DISABLE_KEYRING_ENV, "1")
    monkeypatch.setattr("sys.stdin", io.StringIO("secret-token\n"))

    main(["auth", "login", "registry.example.com", "--token-stdin", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert payload["ok"] is True
    assert payload["data"]["registry"] == "https://registry.example.com"
    stored = json.loads(credential_file.read_text(encoding="utf-8"))
    assert stored["registries"]["https://registry.example.com"] == "secret-token"
    if stat.S_IMODE(credential_file.stat().st_mode) != 0:  # Windows ACLs differ.
        assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600


def test_desktop_only_command_is_explicitly_unavailable(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["raw", "open-window", "--json"])

    assert exc_info.value.code == 7
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "deprecated_desktop_command"
    assert "Desktop interface" in payload["error"]["message"]


@pytest.mark.parametrize(
    "argv",
    [
        ["runs", "start", "run-1", "--json"],
        ["runs", "upload", "run-1", "result.json", "--json"],
        ["jobs", "list", "--json"],
    ],
)
def test_advertised_but_unsupported_api_capability_exits_seven(
    argv: list[str],
    capsys,
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(argv)
    assert exc_info.value.code == 7
    payload = json.loads(capsys.readouterr().out)
    assert payload["error"]["code"] == "capability_unavailable"
