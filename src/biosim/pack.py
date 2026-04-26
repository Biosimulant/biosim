from __future__ import annotations

import hashlib
import json
import os
import posixpath
import shutil
import subprocess
import sys
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .modules import BioModule
from .wiring import WiringBuilder
from .world import BioWorld

PACKAGE_EXTENSION = ".bsimpkg"
PACKAGE_EXTENSIONS = (".bsimpkg", ".bsimodel", ".bsilab")
_TYPE_EXTENSION = {"model": ".bsimodel", "lab": ".bsilab"}
PACKAGE_SCHEMA_VERSION = "1.0"
DEFAULT_PACKAGE_VERSION = "0.1.0"
DEFAULT_PACKAGE_NAMESPACE = "local"
DEFAULT_REGISTRY_ENV = "BIOSIM_PACKAGE_REGISTRY_DIR"
DEFAULT_CACHE_ENV = "BIOSIM_PACKAGE_CACHE_DIR"
DEFAULT_CACHE_HOME = Path.home() / ".cache" / "biosim" / "packages"
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)
_FORBIDDEN_LEGACY_SOURCE_KEYS = frozenset({"repo", "manifest_path", "upstream_repo", "upstream_manifest_path"})


class PackageError(ValueError):
    """Raised when a package is invalid or cannot be handled."""


@dataclass
class PackageValidationResult:
    valid: bool
    metadata: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class _LoadedPackage:
    package_path: Path
    package_type: str
    package_yaml: dict[str, Any]
    manifest: dict[str, Any]
    unpacked_root: Path
    payload_root: Path


def _require_yaml():
    try:
        import yaml  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Package support requires PyYAML. Install with: pip install pyyaml") from exc
    return yaml


def _safe_yaml_dump(value: Any) -> bytes:
    yaml = _require_yaml()
    return yaml.safe_dump(value, sort_keys=False).encode("utf-8")


def _safe_yaml_load(data: bytes | str) -> dict[str, Any]:
    yaml = _require_yaml()
    loaded = yaml.safe_load(data) or {}
    if not isinstance(loaded, dict):
        raise PackageError("YAML document must be a mapping")
    return loaded


def _package_cache_dir() -> Path:
    raw = os.getenv(DEFAULT_CACHE_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return DEFAULT_CACHE_HOME


def _package_registry_dir() -> Path | None:
    raw = os.getenv(DEFAULT_REGISTRY_ENV)
    if not raw:
        return None
    return Path(raw).expanduser().resolve()


def _package_to_parts(package_name: str) -> list[str]:
    parts = [part.strip() for part in package_name.split("/") if part.strip()]
    if not parts:
        raise PackageError("Package name must not be empty")
    return parts


def _package_slug(package_name: str) -> str:
    return "__".join(_package_to_parts(package_name))


def _default_package_name(path: Path) -> str:
    return f"{DEFAULT_PACKAGE_NAMESPACE}/{path.name}"


def _validate_version(version: str) -> str:
    clean = version.strip()
    if not clean:
        raise PackageError("Package version must not be empty")
    return clean


def _is_exact_pin(dep: str) -> bool:
    if "==" not in dep:
        return False
    left, right = dep.split("==", 1)
    return bool(left.strip()) and bool(right.strip()) and all(op not in dep for op in (">=", "<=", "~=", "!=", ">", "<"))


def _validate_dependencies(manifest: Mapping[str, Any]) -> None:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        return
    dependencies = runtime.get("dependencies")
    if not isinstance(dependencies, Mapping):
        return
    packages = dependencies.get("packages")
    if not isinstance(packages, list):
        return
    for dep in packages:
        if not isinstance(dep, str) or not _is_exact_pin(dep):
            raise PackageError(f"Dependency '{dep}' must be pinned with == only")


def _manifest_fingerprint(manifest: Mapping[str, Any]) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _logical_hash(entries: Mapping[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(entries):
        if name in {"package.yaml", "integrity/sha256sums.txt"}:
            continue
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(entries[name])
        digest.update(b"\0")
    return digest.hexdigest()


def _checksums_text(entries: Mapping[str, bytes]) -> str:
    lines: list[str] = []
    for name in sorted(entries):
        if name == "integrity/sha256sums.txt":
            continue
        lines.append(f"{hashlib.sha256(entries[name]).hexdigest()}  {name}")
    return "\n".join(lines) + "\n"


def _normalized_manifest_bytes(path: Path) -> tuple[dict[str, Any], bytes]:
    manifest = _safe_yaml_load(path.read_bytes())
    return manifest, _safe_yaml_dump(manifest)


def _manifest_declared_package(manifest: Mapping[str, Any]) -> str | None:
    value = manifest.get("package")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _manifest_declared_version(manifest: Mapping[str, Any]) -> str | None:
    value = manifest.get("version")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _collect_model_entries(source_dir: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    manifest_path = source_dir / "model.yaml"
    if not manifest_path.exists():
        raise PackageError(f"Model package source is missing {manifest_path}")
    manifest, manifest_bytes = _normalized_manifest_bytes(manifest_path)
    _validate_model_manifest(manifest)
    _validate_dependencies(manifest)

    entries: dict[str, bytes] = {"payload/model.yaml": manifest_bytes}
    for name in ("src", "artifacts", "data", "tests"):
        entries.update(_collect_tree(source_dir, name))
    entries.update(_collect_glob_files(source_dir, ("README*", "*.md")))
    return manifest, entries


def _collect_lab_entries(source_dir: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    manifest_path = source_dir / "lab.yaml"
    if not manifest_path.exists():
        raise PackageError(f"Lab package source is missing {manifest_path}")
    manifest, manifest_bytes = _normalized_manifest_bytes(manifest_path)
    _validate_lab_manifest(manifest)

    entries: dict[str, bytes] = {"payload/lab.yaml": manifest_bytes}
    for path in sorted(source_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(source_dir).as_posix()
        if rel in {"lab.yaml", "lab.yml", "package.yaml"}:
            continue
        if _should_ignore_lab_source_file(path.relative_to(source_dir)):
            continue
        entries[f"payload/{rel}"] = path.read_bytes()
    return manifest, entries


_IGNORED_LAB_SOURCE_DIRS = frozenset(
    {
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "dist",
    }
)
_IGNORED_LAB_SOURCE_FILES = frozenset({".DS_Store"})
_IGNORED_LAB_SOURCE_SUFFIXES = (".pyc", ".pyo")


def _should_ignore_lab_source_file(relative_path: Path) -> bool:
    for part in relative_path.parts[:-1]:
        if part in _IGNORED_LAB_SOURCE_DIRS:
            return True
    name = relative_path.name
    if name in _IGNORED_LAB_SOURCE_FILES:
        return True
    return name.endswith(_IGNORED_LAB_SOURCE_SUFFIXES)


def _collect_tree(root: Path, name: str) -> dict[str, bytes]:
    base = root / name
    if not base.exists():
        return {}
    if not base.is_dir():
        raise PackageError(f"Expected directory at {base}")
    out: dict[str, bytes] = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        out[f"payload/{rel}"] = path.read_bytes()
    return out


def _collect_glob_files(root: Path, patterns: Iterable[str]) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            if path.name in {"model.yaml", "lab.yaml", "package.yaml"}:
                continue
            out[f"payload/{path.name}"] = path.read_bytes()
    return out


def _sanitize_package_source(source: Mapping[str, Any] | None) -> dict[str, Any]:
    if source is None:
        return {}
    if not isinstance(source, Mapping):
        raise PackageError("Package source metadata must be a mapping")
    forbidden = sorted(key for key in _FORBIDDEN_LEGACY_SOURCE_KEYS if key in source and source.get(key) is not None)
    if forbidden:
        raise PackageError(
            "Package source metadata must not include legacy source keys "
            f"({', '.join(forbidden)}). Use path/package/version provenance instead."
        )
    return {str(key): deepcopy(value) for key, value in source.items() if value is not None}


def _build_package_yaml(
    *,
    package_type: str,
    package_name: str,
    version: str,
    visibility: str,
    manifest: Mapping[str, Any],
    entry_manifest: str,
    source: Mapping[str, Any] | None,
    logical_sha256: str,
) -> dict[str, Any]:
    sanitized_source = _sanitize_package_source(source)
    package_yaml: dict[str, Any] = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_type": package_type,
        "package": package_name,
        "version": version,
        "title": manifest.get("title") or package_name,
        "description": manifest.get("description"),
        "entry_manifest": entry_manifest,
        "visibility": visibility,
        "sha256": logical_sha256,
        "source": sanitized_source,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    provenance = {}
    for key in ("path", "commit"):
        value = sanitized_source.get(key)
        if value is not None:
            provenance[key] = value
    if provenance:
        package_yaml["provenance"] = provenance
    if package_type == "model":
        runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), Mapping) else {}
        package_yaml["runtime"] = {"dependencies": dict(runtime.get("dependencies") or {})} if isinstance(runtime, Mapping) else {"dependencies": {}}
        package_yaml["manifest_fingerprint"] = _manifest_fingerprint(manifest)
    return package_yaml


def _write_zip(target: Path, entries: Mapping[str, bytes]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as zipf:
        for name in sorted(entries):
            info = ZipInfo(name, date_time=FIXED_ZIP_TIME)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zipf.writestr(info, entries[name])


def build_package(
    source_dir: str | Path,
    *,
    output_path: str | Path | None = None,
    package_name: str | None = None,
    version: str = DEFAULT_PACKAGE_VERSION,
    visibility: str = "private",
    source: Mapping[str, Any] | None = None,
) -> Path:
    source_path = Path(source_dir).expanduser().resolve()
    if not source_path.is_dir():
        raise PackageError(f"Package source must be a directory: {source_path}")

    if (source_path / "model.yaml").exists():
        package_type = "model"
        manifest, entries = _collect_model_entries(source_path)
    elif (source_path / "lab.yaml").exists():
        return export_lab_package(
            source_path,
            output_path=output_path,
            package_name=package_name,
            version=version,
            visibility=visibility,
            source=source,
        )
    else:
        raise PackageError(f"Could not find model.yaml or lab.yaml in {source_path}")

    package_name = package_name or _manifest_declared_package(manifest) or _default_package_name(source_path)
    version = _validate_version(_manifest_declared_version(manifest) or version)

    logical_sha256 = _logical_hash(entries)
    package_yaml = _build_package_yaml(
        package_type=package_type,
        package_name=package_name,
        version=version,
        visibility=visibility,
        manifest=manifest,
        entry_manifest=f"payload/{package_type}.yaml",
        source=source,
        logical_sha256=logical_sha256,
    )
    entries["package.yaml"] = _safe_yaml_dump(package_yaml)
    entries["integrity/sha256sums.txt"] = _checksums_text(entries).encode("utf-8")

    if output_path is None:
        ext = _TYPE_EXTENSION.get(package_type, PACKAGE_EXTENSION)
        file_name = f"{_package_slug(package_name)}-{version}{ext}"
        output_path = source_path / "dist" / file_name
    target = Path(output_path).expanduser().resolve()
    _write_zip(target, entries)
    return target


def export_lab_package(
    source_dir: str | Path,
    *,
    output_path: str | Path | None = None,
    package_name: str | None = None,
    version: str = DEFAULT_PACKAGE_VERSION,
    visibility: str = "private",
    source: Mapping[str, Any] | None = None,
) -> Path:
    source_path = Path(source_dir).expanduser().resolve()
    manifest, entries = _collect_lab_entries(source_path)
    package_name = package_name or _manifest_declared_package(manifest) or _default_package_name(source_path)
    version = _validate_version(_manifest_declared_version(manifest) or version)
    logical_sha256 = _logical_hash(entries)
    package_yaml = _build_package_yaml(
        package_type="lab",
        package_name=package_name,
        version=version,
        visibility=visibility,
        manifest=manifest,
        entry_manifest="payload/lab.yaml",
        source=source,
        logical_sha256=logical_sha256,
    )
    entries["package.yaml"] = _safe_yaml_dump(package_yaml)
    entries["integrity/sha256sums.txt"] = _checksums_text(entries).encode("utf-8")

    if output_path is None:
        file_name = f"{_package_slug(package_name)}-{version}.bsilab"
        output_path = source_path / "dist" / file_name
    target = Path(output_path).expanduser().resolve()
    _write_zip(target, entries)
    return target


def _validate_paths(names: Iterable[str]) -> None:
    for name in names:
        if name.startswith("/") or ".." in Path(name).parts:
            raise PackageError(f"Invalid archive path: {name}")


def _resolve_embedded_archive_dir(*, package_root: str, current_dir: str, dependency_path: str) -> str:
    relative = _normalize_embedded_path(dependency_path)
    resolved = posixpath.normpath(posixpath.join(current_dir, relative))
    if package_root:
        if resolved != package_root and not resolved.startswith(f"{package_root}/"):
            raise PackageError(f"Embedded dependency escapes package root: {dependency_path}")
    elif resolved.startswith("../") or resolved == "..":
        raise PackageError(f"Embedded dependency escapes package root: {dependency_path}")
    return resolved


def _find_archive_manifest(entries: Mapping[str, bytes], directory: str, candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        archive_path = posixpath.join(directory, candidate) if directory else candidate
        if archive_path in entries:
            return archive_path
    raise PackageError(f"Expected one of {', '.join(candidates)} inside {directory or '<root>'}")


def _normalize_embedded_path(path: str) -> str:
    normalized = posixpath.normpath(path.replace("\\", "/").lstrip("/"))
    if normalized in {"", ".", ".."} or normalized.startswith("../"):
        raise PackageError(f"Invalid embedded dependency path: {path}")
    return normalized


def validate_package(path: str | Path) -> PackageValidationResult:
    package_path = Path(path).expanduser().resolve()
    result = PackageValidationResult(valid=False)
    if package_path.suffix not in PACKAGE_EXTENSIONS:
        result.errors.append(f"Package file must use one of {', '.join(PACKAGE_EXTENSIONS)}")
        return result
    if not package_path.exists():
        result.errors.append(f"Package file not found: {package_path}")
        return result

    try:
        with ZipFile(package_path, "r") as zipf:
            names = zipf.namelist()
            _validate_paths(names)
            if "package.yaml" not in names:
                raise PackageError("Archive is missing package.yaml")
            if "integrity/sha256sums.txt" not in names:
                raise PackageError("Archive is missing integrity/sha256sums.txt")

            entries = {name: zipf.read(name) for name in names}
            package_yaml = _safe_yaml_load(entries["package.yaml"])
            entry_manifest = package_yaml.get("entry_manifest")
            if not isinstance(entry_manifest, str) or entry_manifest not in entries:
                raise PackageError("package.yaml entry_manifest must point to a file in the archive")

            expected_checksums = _parse_checksums(entries["integrity/sha256sums.txt"].decode("utf-8"))
            for name, expected in expected_checksums.items():
                if name not in entries:
                    raise PackageError(f"Checksum entry references missing file: {name}")
                actual = hashlib.sha256(entries[name]).hexdigest()
                if actual != expected:
                    raise PackageError(f"Checksum mismatch for {name}")

            actual_logical_hash = _logical_hash(entries)
            declared_hash = package_yaml.get("sha256")
            if declared_hash and declared_hash != actual_logical_hash:
                raise PackageError("Logical package hash does not match package.yaml sha256")

            manifest = _safe_yaml_load(entries[entry_manifest])
            package_type = package_yaml.get("package_type")
            if package_type == "model":
                _validate_model_manifest(manifest)
                _validate_dependencies(manifest)
            elif package_type == "lab":
                _validate_lab_manifest(manifest)
                _validate_embedded_lab_package(entries, manifest, entry_manifest)
            else:
                raise PackageError(f"Unsupported package_type: {package_type}")

            result.valid = True
            result.metadata = package_yaml
            if not declared_hash:
                result.warnings.append("package.yaml sha256 is missing")
            return result
    except Exception as exc:
        result.errors.append(str(exc))
        return result


def _parse_checksums(text: str) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        digest, _, name = line.partition("  ")
        if not digest or not name:
            raise PackageError(f"Invalid checksum entry: {line}")
        checksums[name] = digest
    return checksums


def unpack_package(path: str | Path, *, dest: str | Path | None = None) -> Path:
    validation = validate_package(path)
    if not validation.valid:
        raise PackageError("; ".join(validation.errors))
    package_path = Path(path).expanduser().resolve()
    if dest is None:
        dest_path = Path(tempfile.mkdtemp(prefix="biosim-pack-"))
    else:
        dest_path = Path(dest).expanduser().resolve()
        dest_path.mkdir(parents=True, exist_ok=True)
    with ZipFile(package_path, "r") as zipf:
        zipf.extractall(dest_path)
    return dest_path


def publish_package(path: str | Path, *, registry_dir: str | Path | None = None) -> Path:
    validation = validate_package(path)
    if not validation.valid or not validation.metadata:
        raise PackageError("; ".join(validation.errors))
    registry = Path(registry_dir).expanduser().resolve() if registry_dir else _package_registry_dir()
    if registry is None:
        raise PackageError(f"Set {DEFAULT_REGISTRY_ENV} or pass registry_dir to publish packages")
    package_name = str(validation.metadata["package"])
    version = str(validation.metadata["version"])
    target_dir = registry.joinpath(*_package_to_parts(package_name), version)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{_package_slug(package_name)}-{version}{PACKAGE_EXTENSION}"
    shutil.copy2(Path(path), target)
    return target


def fetch_package(package_name: str, version: str, *, registry_dir: str | Path | None = None, cache_dir: str | Path | None = None) -> Path:
    version = _validate_version(version)
    registry = Path(registry_dir).expanduser().resolve() if registry_dir else _package_registry_dir()
    cache = Path(cache_dir).expanduser().resolve() if cache_dir else _package_cache_dir()
    cache_target_dir = cache.joinpath(*_package_to_parts(package_name), version)
    cache_target_dir.mkdir(parents=True, exist_ok=True)
    cache_target = cache_target_dir / f"{_package_slug(package_name)}-{version}{PACKAGE_EXTENSION}"
    if cache_target.exists():
        return cache_target
    if registry is None:
        raise PackageError(f"Package {package_name}@{version} is not in cache and no registry is configured")
    registry_target = registry.joinpath(*_package_to_parts(package_name), version, f"{_package_slug(package_name)}-{version}{PACKAGE_EXTENSION}")
    if not registry_target.exists():
        raise PackageError(f"Package {package_name}@{version} was not found in registry {registry}")
    shutil.copy2(registry_target, cache_target)
    return cache_target


def _load_entrypoint(entrypoint: str):
    if ":" in entrypoint:
        module_name, _, attr_name = entrypoint.partition(":")
    else:
        module_name, _, attr_name = entrypoint.rpartition(".")
    if not module_name or not attr_name:
        raise PackageError(f"Invalid entrypoint: {entrypoint}")
    module = import_module(module_name)
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise PackageError(f"Entrypoint attribute not found: {entrypoint}") from exc


def _module_paths_for_payload(payload_root: Path) -> list[str]:
    return [str(payload_root)]


def _instantiate_model_from_package(loaded: _LoadedPackage, parameters: Mapping[str, Any] | None = None) -> tuple[BioModule, dict[str, Any]]:
    manifest = loaded.manifest
    bsim_block = manifest.get("biosim") if isinstance(manifest.get("biosim"), Mapping) else {}
    entrypoint = bsim_block.get("entrypoint")
    if not isinstance(entrypoint, str):
        raise PackageError("Model manifest is missing biosim.entrypoint")

    init_kwargs = {}
    if isinstance(bsim_block.get("init_kwargs"), Mapping):
        init_kwargs.update(dict(bsim_block.get("init_kwargs") or {}))
    if parameters:
        init_kwargs.update(dict(parameters))

    original_sys_path = list(sys.path)
    try:
        for item in reversed(_module_paths_for_payload(loaded.payload_root)):
            if item not in sys.path:
                sys.path.insert(0, item)
        factory = _load_entrypoint(entrypoint)
        module = factory(**init_kwargs)
    finally:
        sys.path[:] = original_sys_path
    if not isinstance(module, BioModule):
        raise PackageError(f"Entrypoint {entrypoint} did not construct a BioModule")
    return module, {
        "communication_step": bsim_block.get("communication_step"),
        "setup": dict(bsim_block.get("setup") or {}) if isinstance(bsim_block.get("setup"), Mapping) else {},
    }


def _loaded_package_from_path(package_path: Path, unpack_root: Path | None = None) -> _LoadedPackage:
    unpacked_root = unpack_package(package_path, dest=unpack_root)
    package_yaml = _safe_yaml_load((unpacked_root / "package.yaml").read_bytes())
    entry_manifest = package_yaml["entry_manifest"]
    manifest = _safe_yaml_load((unpacked_root / entry_manifest).read_bytes())
    payload_root = unpacked_root / "payload"
    return _LoadedPackage(
        package_path=package_path,
        package_type=str(package_yaml["package_type"]),
        package_yaml=package_yaml,
        manifest=manifest,
        unpacked_root=unpacked_root,
        payload_root=payload_root,
    )


def _find_manifest_in_dir(directory: Path, candidates: tuple[str, ...]) -> Path:
    for candidate in candidates:
        manifest_path = directory / candidate
        if manifest_path.is_file():
            return manifest_path
    raise PackageError(
        f"Expected one of {', '.join(candidates)} inside {directory}"
    )


def _load_lab_manifest_from_dir(directory: Path) -> dict[str, Any]:
    manifest_path = _find_manifest_in_dir(directory, ("lab.yaml", "lab.yml"))
    manifest = _safe_yaml_load(manifest_path.read_bytes())
    try:
        _validate_lab_manifest(manifest)
    except PackageError as exc:
        raise PackageError(f"Invalid embedded lab manifest at {manifest_path}: {exc}") from exc
    return manifest


def _load_model_manifest_from_dir(directory: Path) -> dict[str, Any]:
    manifest_path = _find_manifest_in_dir(directory, ("model.yaml", "model.yml", "biosim.yaml", "biosim.yml"))
    manifest = _safe_yaml_load(manifest_path.read_bytes())
    try:
        _validate_model_manifest(manifest)
        _validate_dependencies(manifest)
    except PackageError as exc:
        raise PackageError(f"Invalid embedded model manifest at {manifest_path}: {exc}") from exc
    return manifest


def _resolve_embedded_dir(payload_root: Path, current_lab_dir: Path, dependency_path: str) -> Path:
    normalized = _normalize_embedded_path(dependency_path)
    resolved = (current_lab_dir / normalized).resolve()
    root = payload_root.resolve()
    if resolved != root and root not in resolved.parents:
        raise PackageError(f"Embedded dependency escapes package root: {dependency_path}")
    if not resolved.exists():
        raise PackageError(f"Embedded dependency path not found: {dependency_path}")
    return resolved


def _instantiate_model_from_dir(
    model_dir: Path,
    *,
    manifest: Mapping[str, Any] | None = None,
    parameters: Mapping[str, Any] | None = None,
) -> tuple[BioModule, dict[str, Any]]:
    manifest = dict(manifest or _load_model_manifest_from_dir(model_dir))
    bsim_block = manifest.get("biosim") if isinstance(manifest.get("biosim"), Mapping) else {}
    entrypoint = bsim_block.get("entrypoint")
    if not isinstance(entrypoint, str):
        raise PackageError("Model manifest is missing biosim.entrypoint")

    init_kwargs = {}
    if isinstance(bsim_block.get("init_kwargs"), Mapping):
        init_kwargs.update(dict(bsim_block.get("init_kwargs") or {}))
    if parameters:
        init_kwargs.update(dict(parameters))

    original_sys_path = list(sys.path)
    try:
        model_sys_path = str(model_dir.resolve())
        if model_sys_path not in sys.path:
            sys.path.insert(0, model_sys_path)
        factory = _load_entrypoint(entrypoint)
        module = factory(**init_kwargs)
    finally:
        sys.path[:] = original_sys_path
    if not isinstance(module, BioModule):
        raise PackageError(f"Entrypoint {entrypoint} did not construct a BioModule")
    return module, {
        "communication_step": bsim_block.get("communication_step"),
        "setup": dict(bsim_block.get("setup") or {}) if isinstance(bsim_block.get("setup"), Mapping) else {},
    }


def _validate_embedded_lab_package(
    entries: Mapping[str, bytes],
    parsed_manifest: Mapping[str, Any],
    entry_manifest: str,
) -> None:
    package_root = posixpath.dirname(entry_manifest)
    _validate_embedded_lab_package_dir(
        entries=entries,
        parsed_manifest=parsed_manifest,
        package_root=package_root,
        current_dir=package_root,
        visited=set(),
    )


def _validate_embedded_lab_package_dir(
    *,
    entries: Mapping[str, bytes],
    parsed_manifest: Mapping[str, Any],
    package_root: str,
    current_dir: str,
    visited: set[str],
) -> None:
    if current_dir in visited:
        raise PackageError(f"Circular embedded child lab reference detected at {current_dir}")
    visited = visited | {current_dir}

    models = parsed_manifest.get("models")
    if isinstance(models, list):
        for entry in models:
            if not isinstance(entry, Mapping):
                continue
            embedded_path = entry.get("path")
            if not isinstance(embedded_path, str):
                continue
            model_dir = _resolve_embedded_archive_dir(
                package_root=package_root,
                current_dir=current_dir,
                dependency_path=embedded_path,
            )
            manifest_path = _find_archive_manifest(
                entries,
                model_dir,
                ("model.yaml", "model.yml", "biosim.yaml", "biosim.yml"),
            )
            try:
                parsed_model = _safe_yaml_load(entries[manifest_path])
                _validate_model_manifest(parsed_model)
                _validate_dependencies(parsed_model)
            except PackageError as exc:
                raise PackageError(f"Invalid embedded model manifest at {manifest_path}: {exc}") from exc

    children = parsed_manifest.get("children")
    if not isinstance(children, list):
        return
    for entry in children:
        if not isinstance(entry, Mapping):
            continue
        embedded_path = entry.get("path")
        if not isinstance(embedded_path, str):
            continue
        child_dir = _resolve_embedded_archive_dir(
            package_root=package_root,
            current_dir=current_dir,
            dependency_path=embedded_path,
        )
        manifest_path = _find_archive_manifest(entries, child_dir, ("lab.yaml", "lab.yml"))
        try:
            parsed_child = _safe_yaml_load(entries[manifest_path])
            _validate_lab_manifest(parsed_child)
        except PackageError as exc:
            raise PackageError(f"Invalid embedded child lab manifest at {manifest_path}: {exc}") from exc
        _validate_embedded_lab_package_dir(
            entries=entries,
            parsed_manifest=parsed_child,
            package_root=package_root,
            current_dir=child_dir,
            visited=visited,
        )


def _run_model_loaded_package(loaded: _LoadedPackage, *, install_deps: bool = True) -> dict[str, Any]:
    if install_deps:
        _install_declared_dependencies(loaded.manifest)
    module, meta = _instantiate_model_from_package(loaded)
    module.setup(meta["setup"])
    communication_step = meta["communication_step"]
    if communication_step is None:
        raise PackageError("Model package biosim.communication_step is required")
    module.advance_window(0.0, float(communication_step))
    outputs = module.get_outputs()
    return {
        "package": loaded.package_yaml["package"],
        "version": loaded.package_yaml["version"],
        "outputs": sorted(outputs.keys()),
        "state": module.snapshot(),
    }


def _flatten_embedded_lab_dir(
    *,
    payload_root: Path,
    current_lab_dir: Path,
    prefix: str = "",
    visited: set[Path] | None = None,
    depth: int = 0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if depth > 5:
        raise PackageError("Lab nesting exceeds maximum depth of 5")

    current_key = current_lab_dir.resolve()
    visited_paths = set(visited or set())
    if current_key in visited_paths:
        raise PackageError(f"Circular embedded child lab reference detected at {current_lab_dir}")
    visited_paths.add(current_key)

    parsed_lab = _load_lab_manifest_from_dir(current_lab_dir)
    models = parsed_lab.get("models")
    wiring = parsed_lab.get("wiring")
    if not isinstance(models, list) or not isinstance(wiring, list):
        raise PackageError("Lab manifest must contain models and wiring")

    flat_models: list[dict[str, Any]] = []
    flat_wiring: list[dict[str, Any]] = []
    port_remap: dict[str, str] = {}

    for entry in models:
        if not isinstance(entry, Mapping):
            raise PackageError("Lab model entries must be mappings")
        alias = entry.get("alias")
        embedded_path = entry.get("path")
        if not isinstance(alias, str) or not alias.strip():
            raise PackageError("Lab model entries require a non-empty alias")
        if not isinstance(embedded_path, str) or not embedded_path.strip():
            raise PackageError("Lab model entries require a path reference")
        model_dir = _resolve_embedded_dir(payload_root, current_lab_dir, embedded_path)
        _load_model_manifest_from_dir(model_dir)
        model_entry: dict[str, Any] = {
            "alias": _scoped_ref(prefix, alias),
            "model_dir": str(model_dir),
        }
        for key in ("parameters", "module_config"):
            value = entry.get(key)
            if value is not None:
                model_entry[key] = value
        flat_models.append(model_entry)

    children = parsed_lab.get("children")
    if isinstance(children, list):
        for entry in children:
            if not isinstance(entry, Mapping):
                raise PackageError("Lab child entries must be mappings")
            alias = entry.get("alias")
            embedded_path = entry.get("path")
            if not isinstance(alias, str) or not alias.strip():
                raise PackageError("Lab child entries require alias")
            if not isinstance(embedded_path, str) or not embedded_path.strip():
                raise PackageError("Lab child entries require a path reference")
            child_dir = _resolve_embedded_dir(payload_root, current_lab_dir, embedded_path)
            child_models, child_wiring, child_manifest = _flatten_embedded_lab_dir(
                payload_root=payload_root,
                current_lab_dir=child_dir,
                prefix=_scoped_ref(prefix, f"{alias}."),
                visited=visited_paths,
                depth=depth + 1,
            )
            flat_models.extend(child_models)
            flat_wiring.extend(child_wiring)
            port_remap.update(_port_remap_for_child(prefix=prefix, child_alias=alias, child_manifest=child_manifest))

    for entry in wiring:
        if not isinstance(entry, Mapping):
            raise PackageError("Wiring entries must be mappings")
        from_ref = entry.get("from")
        to_refs = entry.get("to")
        if not isinstance(from_ref, str) or not isinstance(to_refs, list):
            raise PackageError("Wiring entries require from/to")
        scoped_from = _scoped_ref(prefix, from_ref)
        normalized_targets: list[str] = []
        for ref in to_refs:
            if not isinstance(ref, str):
                raise PackageError("Wiring targets must be strings")
            scoped_to = _scoped_ref(prefix, ref)
            normalized_targets.append(port_remap.get(scoped_to, scoped_to))
        flat_wiring.append({"from": port_remap.get(scoped_from, scoped_from), "to": normalized_targets})

    return flat_models, flat_wiring, parsed_lab


def _run_lab_loaded_package(loaded: _LoadedPackage, *, install_deps: bool = True) -> dict[str, Any]:
    runtime = loaded.manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise PackageError("Lab manifest must contain models, wiring, and runtime")
    models, wiring, parsed_lab = _flatten_embedded_lab_dir(
        payload_root=loaded.payload_root,
        current_lab_dir=loaded.payload_root,
    )

    communication_step = runtime.get("communication_step")
    if communication_step is None:
        raise PackageError("Lab manifest runtime.communication_step is required")
    world = BioWorld(communication_step=float(communication_step))
    builder = WiringBuilder(world)
    resolved_models: list[dict[str, Any]] = []
    setup_config: dict[str, dict[str, Any]] = {}

    for entry in models:
        if not isinstance(entry, Mapping):
            raise PackageError("Lab model entries must be mappings")
        alias = entry.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            raise PackageError("Lab model entries require a non-empty alias")
        model_dir = entry.get("model_dir")
        if not isinstance(model_dir, str) or not model_dir:
            raise PackageError("Lab model entries require a resolved model_dir")
        model_path = Path(model_dir)
        manifest = _load_model_manifest_from_dir(model_path)
        if install_deps:
            _install_declared_dependencies(manifest)
        parameters = entry.get("parameters") if isinstance(entry.get("parameters"), Mapping) else {}
        module, meta = _instantiate_model_from_dir(model_path, manifest=manifest, parameters=parameters)
        if entry.get("min_dt") is not None or entry.get("priority") is not None:
            raise PackageError("Lab model entries cannot declare min_dt or priority")
        builder.add(alias, module)
        if meta["setup"]:
            setup_config[alias] = dict(meta["setup"])
        relative_model_dir = model_path.resolve().relative_to(loaded.payload_root.resolve()).as_posix()
        resolved_entry: dict[str, Any] = {
            "alias": alias,
            "path": relative_model_dir,
        }
        model_package_name = manifest.get("package")
        model_version = manifest.get("version")
        if isinstance(model_package_name, str) and model_package_name:
            resolved_entry["package"] = model_package_name
        if isinstance(model_version, str) and model_version:
            resolved_entry["version"] = model_version
        resolved_models.append(resolved_entry)

    for edge in wiring:
        if not isinstance(edge, Mapping):
            raise PackageError("Wiring entries must be mappings")
        src = edge.get("from")
        dst = edge.get("to")
        if not isinstance(src, str) or not isinstance(dst, list):
            raise PackageError("Wiring entries require from/to")
        builder.connect(src, dst)
    builder.apply()

    effective_runtime = parsed_lab.get("runtime") if isinstance(parsed_lab.get("runtime"), Mapping) else runtime
    duration = float(effective_runtime.get("duration", 1.0))
    world.setup(setup_config)
    world.run(duration=duration)
    return {
        "package": loaded.package_yaml["package"],
        "version": loaded.package_yaml["version"],
        "duration": duration,
        "modules": resolved_models,
        "visuals": world.collect_visuals(),
    }


def _scoped_ref(prefix: str, ref: str) -> str:
    return f"{prefix}{ref}" if prefix else ref


def _port_remap_for_child(*, prefix: str, child_alias: str, child_manifest: Mapping[str, Any]) -> dict[str, str]:
    remap: dict[str, str] = {}
    io_block = child_manifest.get("io")
    if not isinstance(io_block, Mapping):
        return remap
    external_prefix = _scoped_ref(prefix, f"{child_alias}.")
    child_prefix = _scoped_ref(prefix, f"{child_alias}.")
    for section in ("inputs", "outputs"):
        ports = io_block.get(section)
        if not isinstance(ports, list):
            continue
        for entry in ports:
            if not isinstance(entry, Mapping):
                continue
            name = entry.get("name")
            maps_to = entry.get("maps_to")
            if not isinstance(name, str) or not isinstance(maps_to, str):
                continue
            remap[f"{external_prefix}{name}"] = f"{child_prefix}{maps_to}"
    return remap


def _install_declared_dependencies(manifest: Mapping[str, Any]) -> None:
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        return
    dependencies = runtime.get("dependencies")
    if not isinstance(dependencies, Mapping):
        return
    packages = dependencies.get("packages")
    if not isinstance(packages, list) or not packages:
        return
    bad = [dep for dep in packages if not isinstance(dep, str) or not _is_exact_pin(dep)]
    if bad:
        raise PackageError(f"All dependencies must use exact pins: {bad}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", *packages],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def run_package(path: str | Path, *, install_deps: bool = True) -> dict[str, Any]:
    loaded = _loaded_package_from_path(Path(path).expanduser().resolve())
    if loaded.package_type == "model":
        return _run_model_loaded_package(loaded, install_deps=install_deps)
    if loaded.package_type == "lab":
        return _run_lab_loaded_package(loaded, install_deps=install_deps)
    raise PackageError(f"Unsupported package type: {loaded.package_type}")


def _validate_model_manifest(manifest: Mapping[str, Any]) -> None:
    bsim = manifest.get("biosim")
    if not isinstance(bsim, Mapping):
        raise PackageError("Model manifest must contain a biosim block")
    entrypoint = bsim.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        raise PackageError("Model manifest must contain biosim.entrypoint")


def _validate_lab_manifest(manifest: Mapping[str, Any]) -> None:
    models = manifest.get("models")
    children = manifest.get("children")
    has_children = isinstance(children, list) and len(children) > 0
    if not isinstance(models, list):
        if has_children:
            models = []
        else:
            raise PackageError("Lab manifest must contain a non-empty models list")
    if not models and not has_children:
        raise PackageError("Lab manifest must contain a non-empty models list or children list")
    aliases: set[str] = set()
    for entry in models:
        if not isinstance(entry, Mapping):
            raise PackageError("Lab model entries must be mappings")
        alias = entry.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            raise PackageError("Lab model entries must define alias")
        if alias in aliases:
            raise PackageError(f"Duplicate lab model alias: {alias}")
        aliases.add(alias)
        if entry.get("repo") is not None or entry.get("manifest_path") is not None:
            raise PackageError(f"Lab model '{alias}' must not use repo or manifest_path")
        if entry.get("package") is not None or entry.get("version") is not None:
            raise PackageError(f"Lab model '{alias}' must use path references only")
        has_path_ref = isinstance(entry.get("path"), str)
        if not has_path_ref:
            raise PackageError(f"Lab model '{alias}' must use a path reference")

    child_aliases: set[str] = set()
    if children is not None:
        if not isinstance(children, list):
            raise PackageError("Lab children entries must be a list")
        for entry in children:
            if not isinstance(entry, Mapping):
                raise PackageError("Lab child entries must be mappings")
            alias = entry.get("alias")
            if not isinstance(alias, str) or not alias.strip():
                raise PackageError("Lab child entries must define alias")
            if alias in child_aliases:
                raise PackageError(f"Duplicate lab child alias: {alias}")
            child_aliases.add(alias)
            if entry.get("repo") is not None or entry.get("manifest_path") is not None:
                raise PackageError(f"Lab child '{alias}' must not use repo or manifest_path")
            if (
                entry.get("lab_id") is not None
                or entry.get("package") is not None
                or entry.get("version") is not None
            ):
                raise PackageError(f"Lab child '{alias}' must use path references only")
            has_path_ref = isinstance(entry.get("path"), str)
            if not has_path_ref:
                raise PackageError(f"Lab child '{alias}' must use a path reference")

    wiring = manifest.get("wiring")
    if not isinstance(wiring, list):
        raise PackageError("Lab manifest must contain a wiring list")
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise PackageError("Lab manifest must contain a runtime mapping")
    if "tick_dt" in runtime:
        raise PackageError("Lab manifest runtime.tick_dt is not supported")
    communication_step = runtime.get("communication_step")
    if communication_step is None:
        raise PackageError("Lab manifest must contain runtime.communication_step")
    try:
        if float(communication_step) <= 0:
            raise PackageError("Lab manifest runtime.communication_step must be positive")
    except (TypeError, ValueError) as exc:
        raise PackageError("Lab manifest runtime.communication_step must be numeric") from exc


__all__ = [
    "PACKAGE_EXTENSION",
    "PACKAGE_EXTENSIONS",
    "PackageError",
    "PackageValidationResult",
    "build_package",
    "export_lab_package",
    "fetch_package",
    "publish_package",
    "run_package",
    "unpack_package",
    "validate_package",
]
