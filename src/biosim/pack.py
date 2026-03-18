from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
PACKAGE_EXTENSIONS = (".bsimpkg", ".bsimodel", ".bsispace")
_TYPE_EXTENSION = {"model": ".bsimodel", "space": ".bsispace"}
PACKAGE_SCHEMA_VERSION = "1.0"
DEFAULT_PACKAGE_VERSION = "0.1.0"
DEFAULT_PACKAGE_NAMESPACE = "local"
DEFAULT_REGISTRY_ENV = "BIOSIM_PACKAGE_REGISTRY_DIR"
DEFAULT_CACHE_ENV = "BIOSIM_PACKAGE_CACHE_DIR"
DEFAULT_CACHE_HOME = Path.home() / ".cache" / "biosim" / "packages"
FIXED_ZIP_TIME = (2020, 1, 1, 0, 0, 0)


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


def _collect_space_entries(source_dir: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    manifest_path = source_dir / "space.yaml"
    if not manifest_path.exists():
        raise PackageError(f"Space package source is missing {manifest_path}")
    manifest, manifest_bytes = _normalized_manifest_bytes(manifest_path)
    _validate_space_manifest(manifest)

    entries: dict[str, bytes] = {"payload/space.yaml": manifest_bytes}
    for name in ("wiring.yaml", "run_local.py", "simui_local.py"):
        file_path = source_dir / name
        if file_path.exists() and file_path.is_file():
            entries[f"payload/{name}"] = file_path.read_bytes()
    for name in ("tests",):
        entries.update(_collect_tree(source_dir, name))
    entries.update(_collect_glob_files(source_dir, ("README*", "*.md")))
    return manifest, entries


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
            if path.name in {"model.yaml", "space.yaml", "package.yaml"}:
                continue
            out[f"payload/{path.name}"] = path.read_bytes()
    return out


def _space_model_refs(manifest: Mapping[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    models = manifest.get("models")
    if not isinstance(models, list):
        return refs
    for entry in models:
        if not isinstance(entry, Mapping):
            continue
        package_name = entry.get("package")
        version = entry.get("version")
        alias = entry.get("alias")
        if isinstance(package_name, str) and isinstance(version, str):
            ref = {"package": package_name, "version": version}
            if isinstance(alias, str) and alias.strip():
                ref["alias"] = alias
            refs.append(ref)
    return refs


def _build_package_yaml(
    *,
    package_type: str,
    package_name: str,
    version: str,
    visibility: str,
    manifest: Mapping[str, Any],
    entry_manifest: str,
    source: Mapping[str, Any] | None,
    bundle_mode: str | None = None,
    model_refs: list[dict[str, str]] | None = None,
    logical_sha256: str,
) -> dict[str, Any]:
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
        "source": dict(source or {}),
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    if package_type == "model":
        runtime = manifest.get("runtime") if isinstance(manifest.get("runtime"), Mapping) else {}
        package_yaml["runtime"] = {"dependencies": dict(runtime.get("dependencies") or {})} if isinstance(runtime, Mapping) else {"dependencies": {}}
        package_yaml["manifest_fingerprint"] = _manifest_fingerprint(manifest)
        provenance = package_yaml.get("source") if isinstance(package_yaml.get("source"), dict) else {}
        package_yaml["provenance"] = {
            "repo": provenance.get("repo"),
            "manifest_path": provenance.get("manifest_path"),
            "commit": provenance.get("commit"),
        }
    else:
        package_yaml["model_refs"] = model_refs or []
        package_yaml["bundle_mode"] = bundle_mode or "reference"
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
        bundle_mode = None
        model_refs = None
    elif (source_path / "space.yaml").exists():
        package_type = "space"
        manifest, entries = _collect_space_entries(source_path)
        bundle_mode = "reference"
        model_refs = _space_model_refs(manifest)
    else:
        raise PackageError(f"Could not find model.yaml or space.yaml in {source_path}")

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
        bundle_mode=bundle_mode,
        model_refs=model_refs,
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


def export_space_package(
    source_dir: str | Path,
    *,
    output_path: str | Path | None = None,
    package_name: str | None = None,
    version: str = DEFAULT_PACKAGE_VERSION,
    visibility: str = "private",
) -> Path:
    source_path = Path(source_dir).expanduser().resolve()
    manifest, entries = _collect_space_entries(source_path)
    refs = _space_model_refs(manifest)
    if not refs:
        raise PackageError("Bundled space export requires models[].package and models[].version references")

    for ref in refs:
        bundled_path = fetch_package(ref["package"], ref["version"])
        bundled_name = f"{_package_slug(ref['package'])}-{ref['version']}.bsimodel"
        entries[f"bundled-models/{bundled_name}"] = bundled_path.read_bytes()
    package_name = package_name or _manifest_declared_package(manifest) or _default_package_name(source_path)
    version = _validate_version(_manifest_declared_version(manifest) or version)
    logical_sha256 = _logical_hash(entries)
    package_yaml = _build_package_yaml(
        package_type="space",
        package_name=package_name,
        version=version,
        visibility=visibility,
        manifest=manifest,
        entry_manifest="payload/space.yaml",
        source=None,
        bundle_mode="bundled",
        model_refs=refs,
        logical_sha256=logical_sha256,
    )
    entries["package.yaml"] = _safe_yaml_dump(package_yaml)
    entries["integrity/sha256sums.txt"] = _checksums_text(entries).encode("utf-8")

    if output_path is None:
        file_name = f"{_package_slug(package_name)}-{version}.bsispace"
        output_path = source_path / "dist" / file_name
    target = Path(output_path).expanduser().resolve()
    _write_zip(target, entries)
    return target


def _validate_paths(names: Iterable[str]) -> None:
    for name in names:
        if name.startswith("/") or ".." in Path(name).parts:
            raise PackageError(f"Invalid archive path: {name}")


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
            elif package_type == "space":
                _validate_space_manifest(manifest)
                if package_yaml.get("bundle_mode") == "bundled":
                    _validate_bundled_model_refs(entries, package_yaml)
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


def _validate_bundled_model_refs(entries: Mapping[str, bytes], package_yaml: Mapping[str, Any]) -> None:
    refs = package_yaml.get("model_refs")
    if not isinstance(refs, list):
        raise PackageError("Bundled space package requires model_refs")
    for ref in refs:
        if not isinstance(ref, Mapping):
            raise PackageError("Bundled model_refs entries must be mappings")
        package_name = ref.get("package")
        version = ref.get("version")
        if not isinstance(package_name, str) or not isinstance(version, str):
            raise PackageError("Bundled model_refs entries require package and version")
        bundled_base = f"bundled-models/{_package_slug(package_name)}-{version}"
        if not any(f"{bundled_base}{ext}" in entries for ext in (".bsimodel", PACKAGE_EXTENSION)):
            raise PackageError(f"Missing bundled model package for {package_name}@{version}")


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
        "min_dt": bsim_block.get("min_dt"),
        "priority": int(bsim_block.get("priority") or 0),
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


def _run_model_loaded_package(loaded: _LoadedPackage, *, install_deps: bool = True) -> dict[str, Any]:
    if install_deps:
        _install_declared_dependencies(loaded.manifest)
    module, meta = _instantiate_model_from_package(loaded)
    module.setup(meta["setup"])
    min_dt = float(meta["min_dt"]) if meta["min_dt"] is not None else float(getattr(module, "min_dt", 0.1) or 0.1)
    module.advance_to(min_dt)
    outputs = module.get_outputs()
    return {
        "package": loaded.package_yaml["package"],
        "version": loaded.package_yaml["version"],
        "outputs": sorted(outputs.keys()),
        "state": module.get_state(),
    }


def _run_space_loaded_package(loaded: _LoadedPackage, *, install_deps: bool = True) -> dict[str, Any]:
    if loaded.package_yaml.get("bundle_mode") == "bundled":
        bundled_dir = loaded.unpacked_root / "bundled-models"
    else:
        bundled_dir = None
    manifest = loaded.manifest
    models = manifest.get("models")
    wiring = manifest.get("wiring")
    runtime = manifest.get("runtime")
    if not isinstance(models, list) or not isinstance(wiring, list) or not isinstance(runtime, Mapping):
        raise PackageError("Space manifest must contain models, wiring, and runtime")

    world = BioWorld()
    builder = WiringBuilder(world)
    resolved_models: list[dict[str, Any]] = []
    setup_config: dict[str, dict[str, Any]] = {}

    for entry in models:
        if not isinstance(entry, Mapping):
            raise PackageError("Space model entries must be mappings")
        alias = entry.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            raise PackageError("Space model entries require a non-empty alias")
        package_name = entry.get("package")
        version = entry.get("version")
        if not isinstance(package_name, str) or not isinstance(version, str):
            raise PackageError("Space model entries require package and version references")
        package_path = _resolve_model_package_file(package_name, version, bundled_dir=bundled_dir)
        loaded_model = _loaded_package_from_path(package_path)
        if loaded_model.package_type != "model":
            raise PackageError(f"Referenced package {package_name}@{version} is not a model package")
        if install_deps:
            _install_declared_dependencies(loaded_model.manifest)
        parameters = entry.get("parameters") if isinstance(entry.get("parameters"), Mapping) else {}
        module, meta = _instantiate_model_from_package(loaded_model, parameters=parameters)
        builder.add(alias, module, min_dt=meta["min_dt"], priority=meta["priority"])
        if meta["setup"]:
            setup_config[alias] = dict(meta["setup"])
        resolved_models.append({"alias": alias, "package": package_name, "version": version})

    for edge in wiring:
        if not isinstance(edge, Mapping):
            raise PackageError("Wiring entries must be mappings")
        src = edge.get("from")
        dst = edge.get("to")
        if not isinstance(src, str) or not isinstance(dst, list):
            raise PackageError("Wiring entries require from/to")
        builder.connect(src, dst)
    builder.apply()

    duration = float(runtime.get("duration", 1.0))
    tick_dt = runtime.get("tick_dt")
    tick = float(tick_dt) if tick_dt is not None else None
    world.setup(setup_config)
    world.run(duration=duration, tick_dt=tick)
    return {
        "package": loaded.package_yaml["package"],
        "version": loaded.package_yaml["version"],
        "duration": duration,
        "modules": resolved_models,
        "visuals": world.collect_visuals(),
    }


def _resolve_model_package_file(package_name: str, version: str, *, bundled_dir: Path | None) -> Path:
    if bundled_dir is not None:
        for ext in (".bsimodel", PACKAGE_EXTENSION):
            candidate = bundled_dir / f"{_package_slug(package_name)}-{version}{ext}"
            if candidate.exists():
                return candidate
    return fetch_package(package_name, version)


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
    if loaded.package_type == "space":
        return _run_space_loaded_package(loaded, install_deps=install_deps)
    raise PackageError(f"Unsupported package type: {loaded.package_type}")


def _validate_model_manifest(manifest: Mapping[str, Any]) -> None:
    bsim = manifest.get("biosim")
    if not isinstance(bsim, Mapping):
        raise PackageError("Model manifest must contain a biosim block")
    entrypoint = bsim.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        raise PackageError("Model manifest must contain biosim.entrypoint")


def _validate_space_manifest(manifest: Mapping[str, Any]) -> None:
    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        raise PackageError("Space manifest must contain a non-empty models list")
    aliases: set[str] = set()
    for entry in models:
        if not isinstance(entry, Mapping):
            raise PackageError("Space model entries must be mappings")
        alias = entry.get("alias")
        if not isinstance(alias, str) or not alias.strip():
            raise PackageError("Space model entries must define alias")
        if alias in aliases:
            raise PackageError(f"Duplicate space model alias: {alias}")
        aliases.add(alias)
        has_repo_ref = isinstance(entry.get("repo"), str)
        has_package_ref = isinstance(entry.get("package"), str) and isinstance(entry.get("version"), str)
        if not has_repo_ref and not has_package_ref:
            raise PackageError(f"Space model '{alias}' must use repo or package/version reference")

    wiring = manifest.get("wiring")
    if not isinstance(wiring, list):
        raise PackageError("Space manifest must contain a wiring list")
    runtime = manifest.get("runtime")
    if not isinstance(runtime, Mapping):
        raise PackageError("Space manifest must contain a runtime mapping")


__all__ = [
    "PACKAGE_EXTENSION",
    "PACKAGE_EXTENSIONS",
    "PackageError",
    "PackageValidationResult",
    "build_package",
    "export_space_package",
    "fetch_package",
    "publish_package",
    "run_package",
    "unpack_package",
    "validate_package",
]
