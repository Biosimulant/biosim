from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .pack import (
    DEFAULT_PACKAGE_NAMESPACE,
    DEFAULT_PACKAGE_VERSION,
    PackageError,
    _default_package_name,
    _manifest_declared_package,
    _manifest_declared_version,
    _package_slug,
    _safe_yaml_dump,
    _safe_yaml_load,
    _validate_model_manifest,
    _validate_lab_manifest,
    _validate_version,
    build_package,
    validate_lab_source,
)

METADATA_DIR = ".biosimulant"
LAB_METADATA_FILE = "lab.json"
_SKIP_SCAN_DIRS = {
    ".biosimulant",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "venv",
}
_MISSING = object()


@dataclass(frozen=True)
class LabRecord:
    id: str
    path: Path
    manifest_path: Path
    title: str | None
    description: str | None
    package: str
    version: str
    managed: bool
    metadata: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": str(self.path),
            "manifest": str(self.manifest_path),
            "title": self.title,
            "description": self.description,
            "package": self.package,
            "version": self.version,
            "managed": self.managed,
            "metadata": self.metadata,
        }


def create_lab(
    path: str | Path = ".",
    *,
    name: str,
    description: str | None = None,
    force: bool = False,
    empty: bool = False,
    local_id: str | None = None,
) -> dict[str, Any]:
    target = Path(path).expanduser().resolve()
    if target.exists() and not target.is_dir():
        raise PackageError(f"Lab path must be a directory: {target}")
    if target.exists() and not force and any(target.iterdir()):
        raise PackageError(
            f"Lab path is not empty: {target}. Re-run with --force to write lab files."
        )
    target.mkdir(parents=True, exist_ok=True)

    slug = _slugify(name)
    if empty:
        models_block = "models: []\nchildren: []\nwiring: []"
        starter_model = None
    else:
        starter_model_path = target / "models" / "hello"
        _write_starter_model(starter_model_path)
        models_block = """models:
  - path: models/hello
    alias: hello
children: []
wiring: []"""
        starter_model = str(starter_model_path)

    lab_yaml = f"""schema_version: "2.0"
title: {_json_string(name)}
description: {_json_string(description) if description is not None else "null"}
package: {DEFAULT_PACKAGE_NAMESPACE}/{slug}
version: 0.1.0
{models_block}
runtime:
  communication_step: 1.0
  duration: 1.0
  initial_inputs: {{}}
"""
    (target / "lab.yaml").write_text(lab_yaml, encoding="utf-8")
    metadata = _ensure_lab_metadata(target, local_id=local_id)
    record = get_lab(target)
    return {
        "command": "labs.create",
        "created": True,
        "path": str(target),
        "manifest": str(target / "lab.yaml"),
        "starter_model": starter_model,
        "id": metadata["id"],
        "lab": record.to_dict(),
    }


def list_labs(root: str | Path = ".") -> list[dict[str, Any]]:
    return [get_lab(path).to_dict() for path in _iter_lab_dirs(Path(root))]


def get_lab(target: str | Path = ".", *, root: str | Path = ".") -> LabRecord:
    lab_path = _resolve_lab_target(target, root=root)
    manifest_path = _lab_manifest_path(lab_path)
    manifest = _safe_yaml_load(manifest_path.read_bytes())
    package_name = _manifest_declared_package(manifest) or _default_package_name(
        lab_path
    )
    version = _validate_version(
        _manifest_declared_version(manifest) or DEFAULT_PACKAGE_VERSION
    )
    metadata = _read_lab_metadata(lab_path)
    fallback_id = _package_slug(package_name)
    return LabRecord(
        id=str(metadata.get("id") if metadata else fallback_id),
        path=lab_path,
        manifest_path=manifest_path,
        title=_optional_string(manifest.get("title")),
        description=_optional_string(manifest.get("description")),
        package=package_name,
        version=version,
        managed=metadata is not None,
        metadata=metadata,
    )


def save_lab(
    target: str | Path = ".",
    *,
    root: str | Path = ".",
    manifest: Mapping[str, Any] | None = None,
    wiring_layout: Any = _MISSING,
    allow_draft: bool = False,
) -> dict[str, Any]:
    lab_path = _resolve_lab_save_target(target, root=root, can_create=manifest is not None)
    if manifest is not None:
        if allow_draft:
            _validate_draft_lab_manifest(manifest)
        else:
            _validate_lab_manifest(manifest)
        _write_yaml(_lab_manifest_path_or_default(lab_path), manifest)
    if wiring_layout is not _MISSING:
        _write_wiring_layout(lab_path, wiring_layout)
    result = validate_lab_source(lab_path)
    if not result.valid:
        if not allow_draft:
            raise PackageError("; ".join(result.errors))
        _, draft_manifest = _load_lab_manifest(lab_path)
        _validate_draft_lab_manifest(draft_manifest)
    metadata = _ensure_lab_metadata(lab_path)
    metadata["updated_at"] = _now()
    _write_lab_metadata(lab_path, metadata)
    return {
        "command": "labs.save",
        "saved": True,
        "lab": get_lab(lab_path).to_dict(),
        "warnings": result.warnings if result.valid else result.errors,
    }


def rename_lab(
    target: str | Path = ".",
    *,
    name: str,
    root: str | Path = ".",
) -> dict[str, Any]:
    lab_path = _resolve_lab_target(target, root=root)
    manifest_path = _lab_manifest_path(lab_path)
    manifest = _safe_yaml_load(manifest_path.read_bytes())
    manifest["title"] = name
    if "name" in manifest:
        manifest["name"] = name
    _write_yaml(manifest_path, manifest)
    metadata = _ensure_lab_metadata(lab_path)
    metadata["updated_at"] = _now()
    _write_lab_metadata(lab_path, metadata)
    return {
        "command": "labs.rename",
        "renamed": True,
        "lab": get_lab(lab_path).to_dict(),
    }


def delete_lab(
    target: str | Path = ".",
    *,
    yes: bool = False,
    root: str | Path = ".",
) -> dict[str, Any]:
    lab_path = _resolve_lab_target(target, root=root)
    _lab_manifest_path(lab_path)
    if not yes:
        raise PackageError("Refusing to delete a lab source tree without --yes")
    shutil.rmtree(lab_path)
    return {"command": "labs.delete", "deleted": True, "path": str(lab_path)}


def export_lab(
    target: str | Path = ".",
    *,
    output: str | Path | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    lab_path = _resolve_lab_target(target, root=root)
    result = validate_lab_source(lab_path)
    if not result.valid:
        raise PackageError("; ".join(result.errors))
    _ensure_lab_metadata(lab_path)
    output_path = _resolve_export_output(lab_path, output)
    package_file = build_package(lab_path, output_path=output_path)
    return {
        "command": "labs.export",
        "exported": True,
        "path": str(package_file),
        "lab": get_lab(lab_path).to_dict(),
    }


def add_model(
    model_path: str | Path,
    *,
    lab: str | Path = ".",
    alias: str | None = None,
    root: str | Path = ".",
) -> dict[str, Any]:
    lab_path = _resolve_lab_target(lab, root=root)
    model_dir = _resolve_existing_model_dir(model_path, lab_path=lab_path)
    model_alias = alias or model_dir.name
    manifest_path, manifest = _load_lab_manifest(lab_path)
    models = _models_list(manifest)
    if _find_model(models, model_alias) is not None:
        raise PackageError(f"Lab already has a model alias: {model_alias}")
    models.append({"path": _relative_path(model_dir, lab_path), "alias": model_alias})
    _write_yaml(manifest_path, manifest)
    _touch_managed_lab(lab_path)
    return {
        "command": "labs.add-model",
        "added": True,
        "alias": model_alias,
        "lab": get_lab(lab_path).to_dict(),
    }


def change_model(
    alias: str,
    model_path: str | Path,
    *,
    lab: str | Path = ".",
    root: str | Path = ".",
) -> dict[str, Any]:
    lab_path = _resolve_lab_target(lab, root=root)
    model_dir = _resolve_existing_model_dir(model_path, lab_path=lab_path)
    manifest_path, manifest = _load_lab_manifest(lab_path)
    models = _models_list(manifest)
    entry = _find_model(models, alias)
    if entry is None:
        raise PackageError(f"Lab model alias not found: {alias}")
    entry["path"] = _relative_path(model_dir, lab_path)
    _write_yaml(manifest_path, manifest)
    _touch_managed_lab(lab_path)
    return {
        "command": "labs.change-model",
        "changed": True,
        "alias": alias,
        "lab": get_lab(lab_path).to_dict(),
    }


def vendor_model(
    model_path: str | Path,
    *,
    lab: str | Path = ".",
    alias: str | None = None,
    replace: bool = False,
    root: str | Path = ".",
) -> dict[str, Any]:
    lab_path = _resolve_lab_target(lab, root=root)
    source_dir = Path(model_path).expanduser().resolve()
    _validate_model_source(source_dir)
    model_alias = alias or source_dir.name
    dest_dir = lab_path / "models" / model_alias
    if dest_dir.exists():
        if not replace:
            raise PackageError(
                f"Vendored model already exists at {dest_dir}; re-run with --replace"
            )
        shutil.rmtree(dest_dir)
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_dir, dest_dir, ignore=_copy_ignore)

    manifest_path, manifest = _load_lab_manifest(lab_path)
    models = _models_list(manifest)
    entry = _find_model(models, model_alias)
    relative = _relative_path(dest_dir, lab_path)
    if entry is None:
        models.append({"path": relative, "alias": model_alias})
    else:
        entry["path"] = relative
    _write_yaml(manifest_path, manifest)
    _touch_managed_lab(lab_path)
    return {
        "command": "labs.vendor-model",
        "vendored": True,
        "alias": model_alias,
        "path": str(dest_dir),
        "lab": get_lab(lab_path).to_dict(),
    }


def inspect_owned(target: str | Path = ".", *, root: str | Path = ".") -> dict[str, Any]:
    lab_path = _resolve_lab_target(target, root=root)
    _, manifest = _load_lab_manifest(lab_path)
    models = []
    for entry in _models_list(manifest):
        alias = _optional_string(entry.get("alias"))
        path_value = _optional_string(entry.get("path"))
        model_dir = (lab_path / path_value).resolve() if path_value else None
        model_manifest = None
        exists = bool(model_dir and model_dir.is_dir())
        if model_dir and exists:
            try:
                parsed = _validate_model_source(model_dir)
                model_manifest = {
                    "title": parsed.get("title"),
                    "package": parsed.get("package"),
                    "version": parsed.get("version"),
                }
            except PackageError:
                model_manifest = None
        models.append(
            {
                "alias": alias,
                "path": path_value,
                "absolute_path": str(model_dir) if model_dir else None,
                "exists": exists,
                "owned": bool(model_dir and _is_relative_to(model_dir, lab_path)),
                "manifest": model_manifest,
            }
        )
    return {
        "command": "labs.inspect-owned",
        "lab": get_lab(lab_path).to_dict(),
        "models": models,
    }


def _iter_lab_dirs(root: Path) -> Iterable[Path]:
    target = root.expanduser().resolve()
    if not target.exists():
        raise PackageError(f"Lab scan root not found: {target}")
    if target.is_file():
        raise PackageError(f"Lab scan root must be a directory: {target}")
    if _is_lab_dir(target):
        yield target
    for manifest in sorted(target.rglob("lab.yaml")):
        if _should_skip(manifest):
            continue
        lab_dir = manifest.parent
        if lab_dir == target:
            continue
        yield lab_dir
    for manifest in sorted(target.rglob("lab.yml")):
        if _should_skip(manifest):
            continue
        lab_dir = manifest.parent
        if lab_dir == target:
            continue
        yield lab_dir


def _resolve_lab_target(target: str | Path = ".", *, root: str | Path = ".") -> Path:
    raw = Path(target).expanduser()
    if raw.exists():
        lab_path = raw.resolve()
        if lab_path.is_file():
            lab_path = lab_path.parent
        _lab_manifest_path(lab_path)
        return lab_path

    root_path = Path(root).expanduser().resolve()
    matches = [
        lab_dir
        for lab_dir in _iter_lab_dirs(root_path)
        if _lab_identifier_matches(lab_dir, str(target))
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise PackageError(f"Multiple labs match {target!s}; pass a path instead")
    raise PackageError(f"Lab not found: {target}")


def _resolve_lab_save_target(
    target: str | Path = ".",
    *,
    root: str | Path = ".",
    can_create: bool,
) -> Path:
    try:
        return _resolve_lab_target(target, root=root)
    except PackageError:
        if not can_create:
            raise
    raw = Path(target).expanduser()
    if raw.exists() and raw.is_dir():
        return raw.resolve()
    if raw.exists():
        raise PackageError(f"Lab path must be a directory: {raw}")
    if raw.is_absolute() or len(raw.parts) > 1 or str(raw) in {".", ".."}:
        raw.mkdir(parents=True, exist_ok=True)
        return raw.resolve()
    raise PackageError(f"Lab not found: {target}")


def _lab_identifier_matches(lab_dir: Path, value: str) -> bool:
    record = get_lab(lab_dir)
    return value in {record.id, record.path.name, record.package}


def _is_lab_dir(path: Path) -> bool:
    return (path / "lab.yaml").is_file() or (path / "lab.yml").is_file()


def _lab_manifest_path(path: Path) -> Path:
    target = path.expanduser().resolve()
    for name in ("lab.yaml", "lab.yml"):
        manifest = target / name
        if manifest.is_file():
            return manifest
    raise PackageError(f"Could not find lab.yaml or lab.yml in {target}")


def _lab_manifest_path_or_default(path: Path) -> Path:
    try:
        return _lab_manifest_path(path)
    except PackageError:
        return path.expanduser().resolve() / "lab.yaml"


def _load_lab_manifest(path: Path) -> tuple[Path, dict[str, Any]]:
    manifest_path = _lab_manifest_path(path)
    return manifest_path, _safe_yaml_load(manifest_path.read_bytes())


def _metadata_path(path: Path) -> Path:
    return path / METADATA_DIR / LAB_METADATA_FILE


def _read_lab_metadata(path: Path) -> dict[str, Any] | None:
    metadata_path = _metadata_path(path)
    if metadata_path.is_file():
        loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        loaded = _read_legacy_project_metadata(path)
        if loaded is None:
            return None
    if not isinstance(loaded, dict):
        raise PackageError(f"Lab metadata must be a mapping: {metadata_path}")
    return loaded


def _ensure_lab_metadata(path: Path, *, local_id: str | None = None) -> dict[str, Any]:
    metadata = _read_lab_metadata(path)
    if metadata is not None and isinstance(metadata.get("id"), str):
        if not _metadata_path(path).is_file():
            _write_lab_metadata(path, metadata)
        return metadata
    now = _now()
    metadata = dict(metadata or {})
    metadata["id"] = local_id or f"lab_{uuid.uuid4().hex}"
    metadata.setdefault("created_at", now)
    metadata["updated_at"] = now
    _write_lab_metadata(path, metadata)
    return metadata


def _touch_managed_lab(path: Path) -> None:
    metadata = _ensure_lab_metadata(path)
    metadata["updated_at"] = _now()
    _write_lab_metadata(path, metadata)


def _write_lab_metadata(path: Path, metadata: Mapping[str, Any]) -> None:
    metadata_path = _metadata_path(path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(dict(metadata), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_legacy_project_metadata(path: Path) -> dict[str, Any] | None:
    metadata_path = path / ".biosimulant-project.json"
    if not metadata_path.is_file():
        return None
    loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return None
    if loaded.get("kind") != "lab" or not isinstance(loaded.get("local_id"), str):
        return None
    metadata: dict[str, Any] = {"id": loaded["local_id"]}
    if isinstance(loaded.get("created_at"), str):
        metadata["created_at"] = loaded["created_at"]
    if isinstance(loaded.get("updated_at"), str):
        metadata["updated_at"] = loaded["updated_at"]
    return metadata


def _validate_draft_lab_manifest(manifest: Mapping[str, Any]) -> None:
    if not isinstance(manifest, Mapping):
        raise PackageError("Lab manifest must be a mapping")

    models = manifest.get("models", [])
    if not isinstance(models, list):
        raise PackageError("Draft lab manifest models must be a list")
    aliases: set[str] = set()
    for entry in models:
        if not isinstance(entry, Mapping):
            raise PackageError("Draft lab model entries must be mappings")
        alias = entry.get("alias")
        if alias is not None:
            if not isinstance(alias, str) or not alias.strip():
                raise PackageError("Draft lab model alias must be a non-empty string")
            if alias in aliases:
                raise PackageError(f"Duplicate lab model alias: {alias}")
            aliases.add(alias)

    children = manifest.get("children", [])
    if not isinstance(children, list):
        raise PackageError("Draft lab manifest children must be a list")
    wiring = manifest.get("wiring", [])
    if not isinstance(wiring, list):
        raise PackageError("Draft lab manifest wiring must be a list")
    runtime = manifest.get("runtime", {})
    if runtime is not None and not isinstance(runtime, Mapping):
        raise PackageError("Draft lab manifest runtime must be a mapping")


def _models_list(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    models = manifest.setdefault("models", [])
    if not isinstance(models, list):
        raise PackageError("Lab manifest models must be a list")
    for entry in models:
        if not isinstance(entry, dict):
            raise PackageError("Lab manifest model entries must be mappings")
    return models


def _find_model(
    models: list[dict[str, Any]],
    alias: str,
) -> dict[str, Any] | None:
    for entry in models:
        if entry.get("alias") == alias:
            return entry
    return None


def _resolve_existing_model_dir(model_path: str | Path, *, lab_path: Path) -> Path:
    candidate = Path(model_path).expanduser()
    if not candidate.is_absolute():
        candidate = lab_path / candidate
    model_dir = candidate.resolve()
    _validate_model_source(model_dir)
    if not _is_relative_to(model_dir, lab_path):
        raise PackageError(
            "Model path must be inside the lab source tree; use vendor-model to copy "
            "external models into the lab"
        )
    return model_dir


def _validate_model_source(path: Path) -> dict[str, Any]:
    if not path.is_dir():
        raise PackageError(f"Model source path not found: {path}")
    manifest_path = None
    for name in ("model.yaml", "model.yml", "biosim.yaml", "biosim.yml"):
        candidate = path / name
        if candidate.is_file():
            manifest_path = candidate
            break
    if manifest_path is None:
        raise PackageError(f"Could not find model.yaml or model.yml in {path}")
    manifest = _safe_yaml_load(manifest_path.read_bytes())
    _validate_model_manifest(manifest)
    return manifest


def _resolve_export_output(lab_path: Path, output: str | Path | None) -> Path | None:
    if output is None:
        return None
    target = Path(output).expanduser().resolve()
    if target.suffix == ".bsilab":
        return target
    target.mkdir(parents=True, exist_ok=True)
    _, manifest = _load_lab_manifest(lab_path)
    package_name = _manifest_declared_package(manifest) or _default_package_name(
        lab_path
    )
    version = _validate_version(
        _manifest_declared_version(manifest) or DEFAULT_PACKAGE_VERSION
    )
    return target / f"{_package_slug(package_name)}-{version}.bsilab"


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _should_skip(path: Path) -> bool:
    return any(part in _SKIP_SCAN_DIRS for part in path.parts)


def _copy_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in _SKIP_SCAN_DIRS}


def _write_yaml(path: Path, value: Mapping[str, Any]) -> None:
    path.write_bytes(_safe_yaml_dump(dict(value)))


def _write_wiring_layout(path: Path, value: Any) -> None:
    layout_path = path / "wiring-layout.json"
    if value is None:
        if layout_path.exists():
            layout_path.unlink()
        return
    layout_path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _slugify(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value)
    slug = "-".join(part for part in slug.split("-") if part)
    return slug or "lab"


def _json_string(value: str) -> str:
    return json.dumps(value)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_starter_model(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "model.yaml").write_text(
        """schema_version: "2.0"
title: "Hello Model"
description: "Starter local Biosimulant model"
standard: other
tags: [starter]
authors: ["Biosimulant"]
package: local/hello
version: 0.1.0
biosim:
  entrypoint: "src.hello:HelloModule"
  communication_step: 1.0
""",
        encoding="utf-8",
    )
    src_dir = path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "hello.py").write_text(
        '''from biosim import BioModule, ScalarSignal, SignalSpec


class HelloModule(BioModule):
    def __init__(self):
        self.time = 0.0

    def outputs(self):
        return {"time": SignalSpec.scalar(dtype="float64")}

    def advance_window(self, _start, end):
        self.time = float(end)

    def get_outputs(self):
        spec = self.outputs()["time"]
        return {
            "time": ScalarSignal(
                source="hello",
                name="time",
                value=self.time,
                emitted_at=self.time,
                spec=spec,
            )
        }

    def snapshot(self):
        return {"time": self.time}
''',
        encoding="utf-8",
    )


__all__ = [
    "LabRecord",
    "add_model",
    "change_model",
    "create_lab",
    "delete_lab",
    "export_lab",
    "get_lab",
    "inspect_owned",
    "list_labs",
    "rename_lab",
    "save_lab",
    "vendor_model",
]
