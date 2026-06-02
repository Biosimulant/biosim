from __future__ import annotations

import hashlib
import json
from pathlib import Path

from biosim import __main__ as cli_main
from biosim.__main__ import main
from biosim.pack import build_package
from tests.test_pack import _write_lab, _write_lab_release_identity


def test_labs_registry_read_commands_use_public_client(monkeypatch, capsys) -> None:
    class FakeRegistryClient:
        def __init__(self, base_url: str | None = None) -> None:
            self.base_url = base_url or "https://registry.test/api"

        def search_labs(self, query, *, page, page_size, tags):
            return {
                "items": [{"id": "lab-1", "title": "Immune Lab"}],
                "query": query,
                "page": page,
                "page_size": page_size,
                "tags": tags,
            }

        def lab_info(self, reference):
            return {"id": "lab-1", "reference": reference}

        def lab_versions(self, reference, *, page, page_size):
            return {
                "reference": reference,
                "versions": ["1.0.0"],
                "page": page,
                "page_size": page_size,
            }

    monkeypatch.setattr(cli_main, "PublicRegistryClient", FakeRegistryClient)

    main(["labs", "search", "immune", "--tags", "demo", "--json"], prog="biosimulant")
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "labs.search"
    assert payload["result"]["items"][0]["title"] == "Immune Lab"
    assert payload["result"]["tags"] == ["demo"]

    main(["labs", "info", "demo/immune@1.0.0", "--json"], prog="biosimulant")
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "labs.info"
    assert payload["result"]["reference"] == "demo/immune@1.0.0"

    main(["labs", "versions", "demo/immune", "--page-size", "5", "--json"], prog="biosimulant")
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "labs.versions"
    assert payload["result"]["versions"] == ["1.0.0"]
    assert payload["result"]["page_size"] == 5


def test_labs_pull_downloads_public_lab_package(monkeypatch, tmp_path: Path, capsys) -> None:
    package_file = build_package(
        _write_lab_release_identity(
            _write_lab(tmp_path / "source-lab"),
            "demo/immune",
            "1.0.0",
        ),
        package_name="demo/immune",
        version="1.0.0",
    )
    package_bytes = package_file.read_bytes()
    sha256 = hashlib.sha256(package_bytes).hexdigest()

    class FakeRegistryClient:
        base_url = "https://registry.test/api"

        def __init__(self, base_url: str | None = None) -> None:
            if base_url:
                self.base_url = base_url

        def resolve_package(self, package_name, version):
            return {
                "id": "pkg-1",
                "package": package_name,
                "version": version,
                "package_type": "lab",
                "sha256": sha256,
            }

        def download_package(self, package_id):
            assert package_id == "pkg-1"
            return package_bytes

    monkeypatch.setattr(cli_main, "PublicRegistryClient", FakeRegistryClient)

    target = tmp_path / "pulled-lab"
    main(
        [
            "labs",
            "pull",
            "demo/immune@1.0.0",
            "--target",
            str(target),
            "--json",
        ],
        prog="biosimulant",
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["command"] == "labs.pull"
    assert payload["artifact"]["id"] == "pkg-1"
    assert Path(payload["path"]) == target
    assert (target / "lab.yaml").is_file()
    assert (target / ".biosimulant" / "lab.json").is_file()


def test_labs_run_auto_pulls_public_lab_ref(monkeypatch, tmp_path: Path, capsys) -> None:
    package_file = build_package(
        _write_lab_release_identity(
            _write_lab(tmp_path / "source-lab"),
            "demo/immune",
            "1.0.0",
        ),
        package_name="demo/immune",
        version="1.0.0",
    )
    package_bytes = package_file.read_bytes()
    sha256 = hashlib.sha256(package_bytes).hexdigest()
    cache_dir = tmp_path / "cache"
    calls = {"downloads": 0}

    class FakeRegistryClient:
        base_url = "https://registry.test/api"

        def __init__(self, base_url: str | None = None) -> None:
            if base_url:
                self.base_url = base_url

        def resolve_package(self, package_name, version):
            return {
                "id": "pkg-1",
                "package": package_name,
                "version": version,
                "package_type": "lab",
                "sha256": sha256,
            }

        def download_package(self, package_id):
            assert package_id == "pkg-1"
            calls["downloads"] += 1
            return package_bytes

    monkeypatch.setenv("BIOSIMULANT_LAB_CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(cli_main, "PublicRegistryClient", FakeRegistryClient)

    main(
        [
            "labs",
            "run",
            "demo/immune@1.0.0",
            "--no-install-deps",
            "--json",
        ],
        prog="biosimulant",
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["package"] == "demo/immune"
    assert payload["modules"][0]["alias"] == "counter"
    assert calls["downloads"] == 1
    assert list(cache_dir.rglob("lab.yaml"))

    main(
        [
            "labs",
            "run",
            "demo/immune@1.0.0",
            "--no-install-deps",
            "--json",
        ],
        prog="biosimulant",
    )
    json.loads(capsys.readouterr().out)
    assert calls["downloads"] == 1


def test_labs_serve_auto_pulls_public_lab_ref(monkeypatch, tmp_path: Path, capsys) -> None:
    package_file = build_package(
        _write_lab_release_identity(
            _write_lab(tmp_path / "source-lab"),
            "demo/immune",
            "1.0.0",
        ),
        package_name="demo/immune",
        version="1.0.0",
    )
    package_bytes = package_file.read_bytes()
    sha256 = hashlib.sha256(package_bytes).hexdigest()
    calls: list[dict[str, object]] = []

    class FakeRegistryClient:
        base_url = "https://registry.test/api"

        def __init__(self, base_url: str | None = None) -> None:
            if base_url:
                self.base_url = base_url

        def resolve_package(self, package_name, version):
            return {
                "id": "pkg-1",
                "package": package_name,
                "version": version,
                "package_type": "lab",
                "sha256": sha256,
            }

        def download_package(self, package_id):
            assert package_id == "pkg-1"
            return package_bytes

    def fake_run_simui(world, config, **kwargs):
        calls.append({"world": world, "config": config, "kwargs": kwargs})

    target = tmp_path / "served-lab"
    monkeypatch.setattr(cli_main, "PublicRegistryClient", FakeRegistryClient)
    monkeypatch.setattr(cli_main, "run_simui", fake_run_simui)

    main(
        [
            "labs",
            "serve",
            "demo/immune@1.0.0",
            "--target",
            str(target),
            "--port",
            "9999",
            "--no-install-deps",
            "--json",
        ],
        prog="biosimulant",
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["package"] == "demo/immune"
    assert (target / "lab.yaml").is_file()
    assert calls
    assert calls[0]["kwargs"]["port"] == 9999
    assert calls[0]["kwargs"]["config_path"] == target / "lab.yaml"
