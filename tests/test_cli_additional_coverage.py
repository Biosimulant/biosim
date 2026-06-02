from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

import biosim.__main__ as cli
from biosim.pack import PackageError


class _ValidationResult:
    def __init__(self, *, valid: bool = True) -> None:
        self.valid = valid
        self.errors = [] if valid else ["broken archive"]
        self.warnings = ["watch this"] if valid else ["still readable"]
        self.metadata = (
            {"package": "demo/lab", "version": "1.0.0", "package_type": "lab"}
            if valid
            else None
        )


class _ManifestEntry:
    package = "demo/lab"
    version = "1.0.0"
    package_type = "lab"
    path = Path("lab")
    visibility = "public"


class _RepoManifest:
    path = Path("biosimulant-packages.yaml")
    packages = [_ManifestEntry()]


def _workspace_payload(command: str = "labs.save") -> dict:
    return {
        "command": command,
        "path": "/tmp/lab",
        "alias": "hello",
        "lab": {
            "id": "lab_1",
            "title": "Demo Lab",
            "path": "/tmp/lab",
            "package": "demo/lab",
            "version": "1.0.0",
        },
    }


def test_create_world_requires_communication_step() -> None:
    with pytest.raises(ValueError, match="communication_step"):
        cli.create_world({})


def test_print_helpers_cover_human_and_json_branches(capsys) -> None:
    cli._print_workspace_result({"command": "labs.list", "labs": []}, json_output=False)
    assert "No local labs found" in capsys.readouterr().out

    cli._print_workspace_result(
        {
            "command": "labs.list",
            "labs": [
                "ignored",
                {
                    "id": "lab_1",
                    "title": "Readable",
                    "path": "/tmp/readable",
                    "package": "demo/readable",
                },
            ],
        },
        json_output=False,
    )
    assert "Readable" in capsys.readouterr().out

    cli._print_workspace_result(_workspace_payload(), json_output=False)
    workspace_out = capsys.readouterr().out
    assert "Demo Lab" in workspace_out
    assert "Alias: hello" in workspace_out

    cli._print_workspace_result(_workspace_payload(), json_output=True)
    assert '"command": "labs.save"' in capsys.readouterr().out

    cli._print_lab_package_result(
        {
            "package": "demo/lab",
            "version": "1.0.0",
            "package_file": "/tmp/lab.bsilab",
            "warnings": ["warn"],
        },
        json_output=False,
    )
    assert "Warning: warn" in capsys.readouterr().out

    cli._print_lab_package_result({"package": "demo/lab"}, json_output=True)
    assert '"package": "demo/lab"' in capsys.readouterr().out

    cli._print_registry_result(
        {
            "command": "labs.search",
            "result": {
                "items": [
                    "ignored",
                    {
                        "id": "lab-id",
                        "title": "Registry Lab",
                        "qualified_package_name": "demo/registry",
                    },
                ]
            },
        },
        json_output=False,
    )
    registry_out = capsys.readouterr().out
    assert "Registry Lab" in registry_out
    assert "demo/registry" in registry_out

    cli._print_registry_result(
        {"command": "labs.search", "result": {"items": []}},
        json_output=False,
    )
    assert "No public labs found" in capsys.readouterr().out

    cli._print_registry_result(
        {
            "command": "labs.info",
            "path": "/tmp/pulled",
            "result": {
                "artifact": {
                    "qualified_name": "demo/lab",
                    "version": "1.0.0",
                    "id": "artifact-id",
                },
                "lab": {
                    "title": "Lab Info",
                    "qualified_package_name": "demo/lab",
                },
            },
        },
        json_output=False,
    )
    info_out = capsys.readouterr().out
    assert "Artifact: artifact-id" in info_out
    assert "Lab: Lab Info" in info_out
    assert "Path: /tmp/pulled" in info_out

    cli._print_registry_result({"command": "labs.search"}, json_output=True)
    assert '"command": "labs.search"' in capsys.readouterr().out

    cli._print_package_repo_validation_success(_RepoManifest(), json_output=False)
    assert "demo/lab@1.0.0" in capsys.readouterr().out

    cli._print_package_repo_validation_success(_RepoManifest(), json_output=True)
    assert '"package_count": 1' in capsys.readouterr().out

    built = [
        {
            "package": "demo/lab",
            "version": "1.0.0",
            "package_type": "lab",
            "path": "/tmp/lab.bsilab",
        }
    ]
    cli._print_package_repo_build_success(built, json_output=False)
    assert "Built packages: 1" in capsys.readouterr().out

    cli._print_package_repo_build_success(built, json_output=True)
    assert '"built"' in capsys.readouterr().out

    cli._print_pack_result(
        False,
        {
            "command": "fetch",
            "package": "demo/lab",
            "version": "1.0.0",
            "package_type": "lab",
            "package_file": "/tmp/lab.bsilab",
            "warnings": ["heads up"],
        },
    )
    assert "heads up" in capsys.readouterr().out

    cli._print_pack_result(True, {"command": "fetch"})
    assert '"command": "fetch"' in capsys.readouterr().out

    cli._print_validation_success(Path("lab.bsilab"), _ValidationResult(), json_output=False)
    assert "Type: lab" in capsys.readouterr().out

    cli._print_validation_success(Path("lab.bsilab"), _ValidationResult(), json_output=True)
    assert '"valid": true' in capsys.readouterr().out

    cli._print_validation_failure(Path("bad.bsilab"), _ValidationResult(valid=False), json_output=False)
    assert "broken archive" in capsys.readouterr().err

    cli._print_validation_failure(Path("bad.bsilab"), _ValidationResult(valid=False), json_output=True)
    assert '"valid": false' in capsys.readouterr().err

    cli._print_run_result(
        Path("lab.bsilab"),
        {
            "package": "demo/lab",
            "version": "1.0.0",
            "outputs": ["state"],
            "modules": [{"alias": "hello", "path": "models/hello"}],
            "duration": 1.0,
        },
        json_output=False,
    )
    run_out = capsys.readouterr().out
    assert "Outputs: state" in run_out
    assert "hello=models/hello" in run_out

    cli._print_run_result(Path("lab.bsilab"), {"outputs": []}, json_output=True)
    assert '"outputs": []' in capsys.readouterr().out

    cli._print_pack_error(PackageError("bad"), json_output=False)
    assert "Error: bad" in capsys.readouterr().err

    cli._print_pack_error(PackageError("bad"), json_output=True)
    assert '"error": "bad"' in capsys.readouterr().err


def test_internal_packages_dispatcher_covers_validate_build_run_and_errors(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "validate_package", lambda _path: _ValidationResult())
    monkeypatch.setattr(cli, "validate_package_repo", lambda _path: _RepoManifest())
    monkeypatch.setattr(cli, "build_package_repo", lambda _manifest, _out: [{
        "package": "demo/lab",
        "version": "1.0.0",
        "package_type": "lab",
        "path": "/tmp/lab.bsilab",
    }])
    monkeypatch.setattr(cli, "run_package", lambda _path, *, install_deps: {"outputs": []})

    cli._main_packages(["validate", "package.bsilab"])
    assert "validation passed" in capsys.readouterr().out

    cli._main_packages(["validate", "biosimulant-packages.yaml", "--json"])
    assert '"package_count": 1' in capsys.readouterr().out

    cli._main_packages(["build", "biosimulant-packages.yaml", "--out", "dist"])
    assert "build succeeded" in capsys.readouterr().out

    cli._main_packages(["run", "package.bsilab", "--no-install-deps", "--json"])
    assert '"outputs": []' in capsys.readouterr().out

    monkeypatch.setattr(cli, "run_package", lambda *_args, **_kwargs: (_ for _ in ()).throw(PackageError("nope")))
    with pytest.raises(SystemExit) as exc_info:
        cli._main_packages(["run", "package.bsilab"])
    assert exc_info.value.code == 1
    assert "nope" in capsys.readouterr().err


def test_internal_pack_dispatcher_covers_legacy_helpers(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "build_package", lambda *_args, **_kwargs: Path("built.bsilab"))
    monkeypatch.setattr(cli, "validate_package", lambda _path: _ValidationResult())
    monkeypatch.setattr(cli, "fetch_package", lambda package, version: Path(f"{package}-{version}.bsimodel"))
    monkeypatch.setattr(cli, "run_package", lambda _path, *, install_deps: {"package": "demo/lab"})

    cli._main_pack(["--json", "build", "source", "--package", "demo/lab"])
    assert '"command": "build"' in capsys.readouterr().out

    cli._main_pack(["validate", "built.bsilab"])
    assert "validation passed" in capsys.readouterr().out

    cli._main_pack(["--json", "fetch", "demo/lab@1.2.3"])
    assert '"version": "1.2.3"' in capsys.readouterr().out

    cli._main_pack(["run", "built.bsilab", "--no-install-deps"])
    assert "run completed" in capsys.readouterr().out

    monkeypatch.setattr(cli, "validate_package", lambda _path: _ValidationResult(valid=False))
    with pytest.raises(SystemExit) as exc_info:
        cli._main_pack(["validate", "bad.bsilab"])
    assert exc_info.value.code == 1
    assert "broken archive" in capsys.readouterr().err

    with pytest.raises(PackageError, match="package@version"):
        cli._parse_package_reference("missing-version")


def test_labs_dispatcher_covers_oss_commands_with_lightweight_fakes(monkeypatch, tmp_path, capsys) -> None:
    lab_path = tmp_path / "lab"
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text("title: From File\nmodels: []\nchildren: []\nwiring: []\n", encoding="utf-8")
    layout_path = tmp_path / "layout.json"
    layout_path.write_text('{"hello": {"x": 1}}\n', encoding="utf-8")

    monkeypatch.setattr(cli, "_init_lab_project", lambda *args, **kwargs: {"path": "/tmp/init", "manifest": "/tmp/init/lab.yaml", "starter_model": None})
    monkeypatch.setattr(cli, "workspace_create_lab", lambda *args, **kwargs: _workspace_payload("labs.create"))
    monkeypatch.setattr(cli, "workspace_list_labs", lambda _root: [_workspace_payload()["lab"]])
    monkeypatch.setattr(cli, "workspace_get_lab", lambda *_args, **_kwargs: SimpleNamespace(to_dict=lambda: _workspace_payload()["lab"]))
    monkeypatch.setattr(cli, "workspace_save_lab", lambda *args, **kwargs: _workspace_payload("labs.save"))
    monkeypatch.setattr(cli, "workspace_rename_lab", lambda *args, **kwargs: _workspace_payload("labs.rename"))
    monkeypatch.setattr(cli, "workspace_delete_lab", lambda *args, **kwargs: _workspace_payload("labs.delete"))
    monkeypatch.setattr(cli, "workspace_add_model", lambda *args, **kwargs: _workspace_payload("labs.add-model"))
    monkeypatch.setattr(cli, "workspace_change_model", lambda *args, **kwargs: _workspace_payload("labs.change-model"))
    monkeypatch.setattr(cli, "workspace_vendor_model", lambda *args, **kwargs: _workspace_payload("labs.vendor-model"))
    monkeypatch.setattr(cli, "workspace_inspect_owned", lambda *args, **kwargs: {"command": "labs.inspect-owned", "models": []})
    monkeypatch.setattr(cli, "_package_lab_source", lambda *args, **kwargs: {"package": "demo/lab", "version": "1.0.0", "package_file": "/tmp/lab.bsilab"})
    monkeypatch.setattr(cli, "validate_package_repo", lambda _path: _RepoManifest())
    monkeypatch.setattr(cli, "build_package_repo", lambda _manifest, _out: [{
        "package": "demo/lab",
        "version": "1.0.0",
        "package_type": "lab",
        "path": "/tmp/lab.bsilab",
    }])
    monkeypatch.setattr(cli, "_pull_public_lab", lambda *args, **kwargs: {"command": "labs.pull", "path": "/tmp/pulled"})

    class FakeRegistryClient:
        base_url = "https://registry.test/api"

        def __init__(self, _url=None):
            pass

        def search_labs(self, *args, **kwargs):
            return {"items": [{"title": "Search Lab"}]}

        def lab_info(self, reference):
            return {"artifact": {"qualified_name": reference, "version": "1.0.0", "id": "a1"}}

        def lab_versions(self, reference, **kwargs):
            return {"items": [{"version": "1.0.0", "qualified_package_name": reference}]}

    monkeypatch.setattr(cli, "PublicRegistryClient", FakeRegistryClient)

    commands = [
        ["init", str(lab_path), "--name", "Init", "--empty", "--json"],
        ["create", str(lab_path), "--name", "Created"],
        ["list", str(tmp_path)],
        ["get", "lab_1", "--root", str(tmp_path), "--json"],
        ["save", str(lab_path), "--manifest-file", str(manifest_path), "--wiring-layout-file", str(layout_path), "--allow-draft"],
        ["save", str(lab_path), "--clear-wiring-layout", "--json"],
        ["rename", "lab_1", "Renamed"],
        ["rename", "Only Name", "--json"],
        ["delete", str(lab_path), "--yes"],
        ["package", str(lab_path), "--out", str(tmp_path / "dist"), "--visibility", "public"],
        ["release", "validate", str(manifest_path), "--json"],
        ["release", "build", str(manifest_path), "--out", str(tmp_path / "dist")],
        ["search", "hello", "--tags", "demo"],
        ["info", "demo/lab", "--json"],
        ["versions", "demo/lab"],
        ["pull", "demo/lab", "--target", str(tmp_path / "pulled"), "--force"],
        ["add-model", str(tmp_path / "model"), "--lab", str(lab_path), "--alias", "m"],
        ["change-model", "m", str(tmp_path / "model"), "--lab", str(lab_path), "--json"],
        ["vendor-model", str(tmp_path / "model"), "--lab", str(lab_path), "--replace"],
        ["inspect-owned", str(lab_path), "--json"],
    ]
    for command in commands:
        cli._main_labs(command)
        capsys.readouterr()

    bad_manifest = tmp_path / "list.yaml"
    bad_manifest.write_text("- not\n- a mapping\n", encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        cli._main_labs(["save", str(lab_path), "--manifest-file", str(bad_manifest)])
    assert exc_info.value.code == 1


def test_labs_dispatcher_covers_validate_run_serve_and_extension_paths(monkeypatch, tmp_path, capsys) -> None:
    package_path = tmp_path / "lab.bsilab"
    package_path.write_text("placeholder", encoding="utf-8")
    results_path = tmp_path / "results.json"

    @contextmanager
    def fake_package_file(_path):
        yield package_path

    monkeypatch.setattr(cli, "_resolve_runtime_lab_path", lambda *args, **kwargs: (tmp_path / "lab", {"reused": True}))
    monkeypatch.setattr(cli, "_package_file_for_lab", fake_package_file)
    monkeypatch.setattr(cli, "run_package", lambda _path, *, install_deps: {"package": "demo/lab", "outputs": ["state"]})
    launched = {}
    def fake_serve_lab(_path, **kwargs):
        launched.update(kwargs)
        if kwargs.get("emit_json"):
            print('{"command": "serve", "url": "http://0.0.0.0:9999/"}')

    monkeypatch.setattr(cli, "serve_lab", fake_serve_lab)

    cli._main_labs(["run", "demo/lab", "--results-file", str(results_path)])
    assert "Outputs: state" in capsys.readouterr().out
    assert '"outputs": ["state"]' in results_path.read_text(encoding="utf-8")

    cli._main_labs(["serve", "demo/lab", "--json", "--host", "0.0.0.0", "--port", "9999", "--open"])
    assert '"command": "serve"' in capsys.readouterr().out
    assert launched["host"] == "0.0.0.0"
    assert launched["port"] == 9999
    assert launched["open_browser"] is True

    monkeypatch.setattr(cli, "_validate_local_lab", lambda _path: _ValidationResult())
    cli._main_labs(["validate", str(tmp_path / "lab"), "--json"])
    assert '"command": "labs.validate"' in capsys.readouterr().out

    monkeypatch.setattr(cli, "_validate_local_lab", lambda _path: _ValidationResult(valid=False))
    with pytest.raises(SystemExit) as exc_info:
        cli._main_labs(["validate", str(tmp_path / "lab")])
    assert exc_info.value.code == 1
    assert "broken archive" in capsys.readouterr().err

    seen = {}
    monkeypatch.setattr(cli, "_run_extension_or_exit", lambda command, argv, *, prog: seen.update(command=command, argv=argv, prog=prog))
    cli._main_labs(["release", "publish"])
    assert seen["command"] == "labs release publish"
