from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

from .pack import PackageError


DEFAULT_REGISTRY_URL = "https://prod-api.biosimulant.com/api"
REGISTRY_URL_ENV = "BIOSIMULANT_REGISTRY_URL"
LEGACY_API_BASE_ENV = "BIOSIMULANT_API_BASE_URL"
LAB_CACHE_DIR_ENV = "BIOSIMULANT_LAB_CACHE_DIR"
_PACKAGE_NAME_RE = re.compile(
    r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*(?:@[A-Za-z0-9][A-Za-z0-9.+_-]*)?$"
)


@dataclass(frozen=True)
class PackageReference:
    package_name: str
    version: str | None


class RegistryError(PackageError):
    """Raised when the public Biosimulant registry cannot satisfy a request."""


class PublicRegistryClient:
    def __init__(self, base_url: str | None = None) -> None:
        value = (
            base_url
            or os.environ.get(REGISTRY_URL_ENV)
            or os.environ.get(LEGACY_API_BASE_ENV)
            or DEFAULT_REGISTRY_URL
        )
        self.base_url = value.rstrip("/")

    def search_labs(
        self,
        query: str | None = None,
        *,
        page: int = 1,
        page_size: int = 20,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        params: list[tuple[str, str | int]] = [
            ("scope", "discover"),
            ("page", page),
            ("page_size", page_size),
        ]
        if query:
            params.append(("search", query))
        for tag in tags or []:
            params.append(("tags", tag))
        return self._json("GET", "/labs", params=params)

    def lab_info(self, reference: str) -> dict[str, Any]:
        parsed = parse_package_reference(reference, allow_missing_version=True)
        if parsed is not None:
            artifact = self.resolve_package(parsed.package_name, parsed.version)
            payload: dict[str, Any] = {
                "kind": "lab_package",
                "reference": reference,
                "artifact": artifact,
            }
            lab_id = artifact.get("lab_id")
            if lab_id:
                try:
                    payload["lab"] = self.get_lab(str(lab_id))
                except RegistryError:
                    payload["lab"] = None
            return payload
        return {
            "kind": "lab",
            "reference": reference,
            "lab": self.get_lab(reference),
        }

    def lab_versions(
        self,
        reference: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        parsed = parse_package_reference(reference, allow_missing_version=True)
        lab_id = reference
        if parsed is not None:
            artifact = self.resolve_package(parsed.package_name, parsed.version)
            lab_id = str(artifact.get("lab_id") or "")
            if not lab_id:
                raise RegistryError(
                    f"Package {reference} is not linked to a downloadable lab"
                )
        return self._json(
            "GET",
            f"/labs/{quote(lab_id, safe='')}/versions",
            params=[("page", page), ("page_size", page_size)],
        )

    def resolve_package(
        self, package_name: str, version: str | None = None
    ) -> dict[str, Any]:
        path = f"/packages/resolve/{quote(package_name, safe='/')}"
        params = [("version", version)] if version else None
        return self._json("GET", path, params=params)

    def get_lab(self, lab_id: str) -> dict[str, Any]:
        return self._json("GET", f"/labs/{quote(lab_id, safe='')}")

    def download_package(self, artifact_id: str) -> bytes:
        return self._bytes("GET", f"/packages/{quote(artifact_id, safe='')}/download")

    def _url(
        self, path: str, *, params: list[tuple[str, str | int | None]] | None = None
    ) -> str:
        url = f"{self.base_url}{path}"
        clean = [(key, value) for key, value in params or [] if value is not None]
        if clean:
            url = f"{url}?{urlencode(clean, doseq=True)}"
        return url

    def _json(
        self,
        method: str,
        path: str,
        *,
        params: list[tuple[str, str | int | None]] | None = None,
    ) -> dict[str, Any]:
        data = self._bytes(method, path, params=params)
        try:
            value = json.loads(data.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RegistryError(f"Registry returned invalid JSON for {path}") from exc
        if not isinstance(value, dict):
            raise RegistryError(f"Registry returned non-object JSON for {path}")
        return value

    def _bytes(
        self,
        method: str,
        path: str,
        *,
        params: list[tuple[str, str | int | None]] | None = None,
    ) -> bytes:
        request = Request(self._url(path, params=params), method=method)
        request.add_header("accept", "application/json")
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 401:
                raise RegistryError(
                    "Registry item requires authentication (HTTP 401)"
                ) from exc
            if exc.code == 403:
                raise RegistryError(
                    "Registry item is private or access is forbidden (HTTP 403)"
                ) from exc
            if exc.code == 404:
                raise RegistryError("Registry item was not found (HTTP 404)") from exc
            raise RegistryError(f"Registry request failed with HTTP {exc.code}: {body}") from exc
        except URLError as exc:
            raise RegistryError(f"Registry request failed: {exc.reason}") from exc


def parse_package_reference(
    value: str, *, allow_missing_version: bool = False
) -> PackageReference | None:
    raw = value.strip()
    if "/" not in raw or "\\" in raw:
        return None
    if raw.startswith((".", "/", "~")):
        return None
    if "@" in raw:
        package_name, _sep, version = raw.rpartition("@")
        if not package_name or not version:
            raise RegistryError("Package reference must use namespace/name@version")
    if not _PACKAGE_NAME_RE.match(raw):
        return None
    package_name, sep, version = raw.rpartition("@")
    if not sep:
        if allow_missing_version:
            return PackageReference(raw, None)
        raise RegistryError("Package reference must use namespace/name@version")
    if not package_name or not version:
        raise RegistryError("Package reference must use namespace/name@version")
    return PackageReference(package_name, version)


def lab_destination_for_reference(reference: str, target: str | Path | None) -> Path:
    if target is not None:
        return Path(target).expanduser().resolve()
    parsed = parse_package_reference(reference, allow_missing_version=True)
    name = reference
    if parsed is not None:
        name = parsed.package_name.rsplit("/", 1)[-1]
    return Path.cwd().joinpath(name).resolve()


def lab_cache_dir() -> Path:
    configured = os.environ.get(LAB_CACHE_DIR_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home().joinpath(".cache", "biosimulant", "labs").resolve()


def cached_lab_destination_for_reference(
    reference: str,
    artifact: dict[str, Any],
    *,
    cache_dir: str | Path | None = None,
) -> Path:
    parsed = parse_package_reference(reference, allow_missing_version=True)
    if parsed is None:
        raise RegistryError("Lab reference must use namespace/name[@version]")
    version = parsed.version or str(artifact.get("version") or "latest")
    artifact_id = str(artifact.get("id") or artifact.get("sha256") or "")[:12]
    raw = f"{parsed.package_name}@{version}"
    if artifact_id:
        raw = f"{raw}-{artifact_id}"
    slug = "".join(char.lower() if char.isalnum() else "-" for char in raw)
    slug = "-".join(part for part in slug.split("-") if part)
    root = Path(cache_dir).expanduser().resolve() if cache_dir else lab_cache_dir()
    return root / (slug or "lab")
