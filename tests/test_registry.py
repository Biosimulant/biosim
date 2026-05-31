from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from biosim import registry
from biosim.registry import (
    PublicRegistryClient,
    RegistryError,
    cached_lab_destination_for_reference,
    lab_cache_dir,
    lab_destination_for_reference,
    parse_package_reference,
)


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_public_registry_client_builds_urls_and_decodes_json(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response(
            json.dumps({"items": [{"id": "lab-1"}], "ok": True}).encode("utf-8")
        )

    monkeypatch.setattr(registry, "urlopen", fake_urlopen)

    client = PublicRegistryClient("https://registry.test/api/")
    payload = client.search_labs(
        "immune",
        page=2,
        page_size=5,
        tags=["demo", "public"],
    )

    assert payload["items"] == [{"id": "lab-1"}]
    request, timeout = requests[0]
    assert timeout == 60
    assert request.method == "GET"
    assert request.full_url.startswith("https://registry.test/api/labs?")
    assert "scope=discover" in request.full_url
    assert "search=immune" in request.full_url
    assert "tags=demo" in request.full_url
    assert "tags=public" in request.full_url


def test_public_registry_client_resolves_and_downloads_packages(monkeypatch) -> None:
    seen_urls: list[str] = []

    def fake_urlopen(request, timeout):
        seen_urls.append(request.full_url)
        if "/download" in request.full_url:
            return _Response(b"package-bytes")
        return _Response(json.dumps({"id": "pkg-1"}).encode("utf-8"))

    monkeypatch.setattr(registry, "urlopen", fake_urlopen)
    client = PublicRegistryClient("https://registry.test/api")

    assert client.resolve_package("demo/immune", "1.2.3") == {"id": "pkg-1"}
    assert client.download_package("pkg-1") == b"package-bytes"

    assert seen_urls[0] == "https://registry.test/api/packages/resolve/demo/immune?version=1.2.3"
    assert seen_urls[1] == "https://registry.test/api/packages/pkg-1/download"


def test_lab_info_and_versions_handle_package_and_lab_refs(monkeypatch) -> None:
    client = PublicRegistryClient("https://registry.test/api")
    monkeypatch.setattr(
        client,
        "resolve_package",
        lambda package, version: {"id": "pkg-1", "lab_id": "lab-1"},
    )
    monkeypatch.setattr(client, "get_lab", lambda lab_id: {"id": lab_id})

    info = client.lab_info("demo/immune@1.0.0")
    assert info["kind"] == "lab_package"
    assert info["artifact"]["id"] == "pkg-1"
    assert info["lab"] == {"id": "lab-1"}

    lab_info = client.lab_info("lab-raw-id")
    assert lab_info == {
        "kind": "lab",
        "reference": "lab-raw-id",
        "lab": {"id": "lab-raw-id"},
    }

    calls = []
    monkeypatch.setattr(
        client,
        "_json",
        lambda method, path, params=None: calls.append((method, path, params))
        or {"items": []},
    )
    assert client.lab_versions("demo/immune", page=3, page_size=4) == {"items": []}
    assert calls[-1] == (
        "GET",
        "/labs/lab-1/versions",
        [("page", 3), ("page_size", 4)],
    )


def test_lab_info_suppresses_missing_linked_lab(monkeypatch) -> None:
    client = PublicRegistryClient("https://registry.test/api")
    monkeypatch.setattr(
        client,
        "resolve_package",
        lambda package, version: {"id": "pkg-1", "lab_id": "private-lab"},
    )

    def missing_lab(lab_id):
        raise RegistryError("not visible")

    monkeypatch.setattr(client, "get_lab", missing_lab)

    payload = client.lab_info("demo/private")
    assert payload["artifact"]["id"] == "pkg-1"
    assert payload["lab"] is None


def test_lab_versions_requires_package_to_link_to_lab(monkeypatch) -> None:
    client = PublicRegistryClient("https://registry.test/api")
    monkeypatch.setattr(client, "resolve_package", lambda package, version: {"id": "pkg-1"})

    with pytest.raises(RegistryError, match="not linked"):
        client.lab_versions("demo/unlinked")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("demo/immune@1.0.0", ("demo/immune", "1.0.0")),
        ("demo/immune", ("demo/immune", None)),
        ("./demo/immune", None),
        ("/demo/immune", None),
        ("demo/immune/extra", None),
        ("Demo/immune", None),
        (r"demo\\immune", None),
    ],
)
def test_parse_package_reference(value, expected) -> None:
    parsed = parse_package_reference(value, allow_missing_version=True)
    if expected is None:
        assert parsed is None
    else:
        assert parsed is not None
        assert (parsed.package_name, parsed.version) == expected


def test_parse_package_reference_requires_version_when_configured() -> None:
    with pytest.raises(RegistryError, match="namespace/name@version"):
        parse_package_reference("demo/immune")

    with pytest.raises(RegistryError, match="namespace/name@version"):
        parse_package_reference("demo/immune@")


def test_lab_destination_and_cache_paths(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BIOSIMULANT_LAB_CACHE_DIR", str(tmp_path / "cache"))

    assert lab_destination_for_reference("demo/immune@1.0.0", None) == (
        tmp_path / "immune"
    ).resolve()
    assert lab_destination_for_reference("demo/immune", tmp_path / "target") == (
        tmp_path / "target"
    ).resolve()
    assert lab_cache_dir() == (tmp_path / "cache").resolve()

    cached = cached_lab_destination_for_reference(
        "demo/immune",
        {"id": "artifact-1234567890", "version": "1.0.0"},
    )
    assert cached == (tmp_path / "cache" / "demo-immune-1-0-0-artifact-123").resolve()

    with pytest.raises(RegistryError, match="namespace/name"):
        cached_lab_destination_for_reference("immune", {})


@pytest.mark.parametrize(
    ("code", "message"),
    [
        (401, "requires authentication"),
        (403, "private or access is forbidden"),
        (404, "not found"),
        (500, "HTTP 500"),
    ],
)
def test_registry_http_errors_are_actionable(monkeypatch, code, message) -> None:
    def fake_urlopen(request, timeout):
        raise HTTPError(
            request.full_url,
            code,
            "error",
            hdrs={},
            fp=BytesIO(b'{"detail":"bad"}'),
        )

    monkeypatch.setattr(registry, "urlopen", fake_urlopen)

    with pytest.raises(RegistryError, match=message):
        PublicRegistryClient("https://registry.test/api").get_lab("lab-1")


def test_registry_transport_and_payload_errors(monkeypatch) -> None:
    def url_error(request, timeout):
        raise URLError("offline")

    monkeypatch.setattr(registry, "urlopen", url_error)
    with pytest.raises(RegistryError, match="offline"):
        PublicRegistryClient("https://registry.test/api").get_lab("lab-1")

    monkeypatch.setattr(registry, "urlopen", lambda request, timeout: _Response(b"{"))
    with pytest.raises(RegistryError, match="invalid JSON"):
        PublicRegistryClient("https://registry.test/api").get_lab("lab-1")

    monkeypatch.setattr(registry, "urlopen", lambda request, timeout: _Response(b"[]"))
    with pytest.raises(RegistryError, match="non-object"):
        PublicRegistryClient("https://registry.test/api").get_lab("lab-1")
