from __future__ import annotations

import os
from pathlib import Path

import pytest

from biosim.pack import (
    PackageError,
    build_package,
    export_space_package,
    publish_package,
    run_package,
    unpack_package,
    validate_package,
)


def _write_counter_model(path: Path, *, package_name: str | None = None, version: str | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    model_yaml = [
        'schema_version: "2.0"',
        'title: "Test: Counter"',
        'description: "Counter model"',
        "standard: other",
        "tags: [test]",
        'authors: ["Tests"]',
        "biosim:",
        '  entrypoint: "src.counter:Counter"',
    ]
    if package_name:
        model_yaml.append(f"package: {package_name}")
    if version:
        model_yaml.append(f"version: {version}")
    (path / "model.yaml").write_text("\n".join(model_yaml) + "\n", encoding="utf-8")
    src_dir = path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "counter.py").write_text(
        """
from biosim import BioModule, BioSignal


class Counter(BioModule):
    def __init__(self, step: float = 1.0):
        self.min_dt = 0.1
        self.value = 0.0
        self.step = step

    def outputs(self):
        return {"count"}

    def advance_to(self, t: float) -> None:
        self.value += self.step

    def get_outputs(self):
        return {"count": BioSignal(source="counter", name="count", value=self.value, time=0.1)}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_accumulator_model(path: Path, *, package_name: str | None = None, version: str | None = None) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    model_yaml = [
        'schema_version: "2.0"',
        'title: "Test: Accumulator"',
        'description: "Accumulator model"',
        "standard: other",
        "tags: [test]",
        'authors: ["Tests"]',
        "biosim:",
        '  entrypoint: "src.accumulator:Accumulator"',
    ]
    if package_name:
        model_yaml.append(f"package: {package_name}")
    if version:
        model_yaml.append(f"version: {version}")
    (path / "model.yaml").write_text("\n".join(model_yaml) + "\n", encoding="utf-8")
    src_dir = path / "src"
    src_dir.mkdir(exist_ok=True)
    (src_dir / "accumulator.py").write_text(
        """
from biosim import BioModule, BioSignal


class Accumulator(BioModule):
    def __init__(self):
        self.min_dt = 0.1
        self.total = 0.0

    def inputs(self):
        return {"value"}

    def outputs(self):
        return {"total"}

    def set_inputs(self, signals):
        signal = signals.get("value")
        if signal is not None:
            self.total += float(signal.value)

    def advance_to(self, t: float) -> None:
        return

    def get_outputs(self):
        return {"total": BioSignal(source="acc", name="total", value=self.total, time=0.1)}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_space(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _write_counter_model(
        path / "models" / "counter",
        package_name="local/counter",
        version="1.0.0",
    )
    _write_accumulator_model(
        path / "models" / "accumulator",
        package_name="local/accumulator",
        version="1.0.0",
    )
    (path / "space.yaml").write_text(
        """
schema_version: "2.0"
title: "Test: Space"
description: "Self-contained source-tree space"
models:
  - path: models/counter
    alias: counter
  - path: models/accumulator
    alias: accumulator
runtime:
  duration: 0.2
  tick_dt: 0.1
  initial_inputs: {}
wiring:
  - from: counter.count
    to: [accumulator.value]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_path_manifest_space(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _write_counter_model(path / "models" / "counter")
    (path / "space.yaml").write_text(
        """
schema_version: "2.0"
title: "Test: Source Space"
description: "Source-style space refs"
models:
  - path: models/counter
    alias: counter
runtime:
  duration: 0.2
  tick_dt: 0.1
  initial_inputs: {}
wiring: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_child_output_space(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _write_counter_model(
        path / "models" / "counter",
        package_name="local/counter",
        version="1.0.0",
    )
    (path / "space.yaml").write_text(
        """
schema_version: "2.0"
title: "Test: Child Space"
description: "Embedded child space"
models:
  - path: models/counter
    alias: counter
io:
  outputs:
    - name: count
      maps_to: counter.count
runtime:
  duration: 0.2
  tick_dt: 0.1
  initial_inputs: {}
wiring: []
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def _write_parent_space_with_child(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _write_accumulator_model(
        path / "models" / "accumulator",
        package_name="local/accumulator",
        version="1.0.0",
    )
    _write_child_output_space(path / "spaces" / "child-space")
    (path / "space.yaml").write_text(
        """
schema_version: "2.0"
title: "Test: Parent Space"
description: "Embedded child-space refs"
models:
  - path: models/accumulator
    alias: accumulator
children:
  - path: spaces/child-space
    alias: nested
runtime:
  duration: 0.2
  tick_dt: 0.1
  initial_inputs: {}
wiring:
  - from: nested.count
    to: [accumulator.value]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return path


def test_build_validate_and_unpack_model_package(tmp_path: Path):
    model_dir = _write_counter_model(tmp_path / "counter")
    package_path = build_package(model_dir, package_name="local/counter", version="1.0.0")

    validation = validate_package(package_path)
    assert validation.valid
    assert validation.metadata["package"] == "local/counter"
    assert validation.metadata["package_type"] == "model"

    unpacked = unpack_package(package_path, dest=tmp_path / "unpacked")
    assert (unpacked / "payload" / "model.yaml").exists()
    assert (unpacked / "payload" / "src" / "counter.py").exists()


def test_build_uses_manifest_declared_package_and_version(tmp_path: Path):
    model_dir = _write_counter_model(
        tmp_path / "counter",
        package_name="manifest/counter",
        version="2.3.4",
    )
    package_path = build_package(model_dir)

    validation = validate_package(package_path)
    assert validation.valid
    assert validation.metadata["package"] == "manifest/counter"
    assert validation.metadata["version"] == "2.3.4"


def test_model_package_run_smoke(tmp_path: Path):
    model_dir = _write_counter_model(tmp_path / "counter")
    package_path = build_package(model_dir, package_name="local/counter", version="1.0.0")
    result = run_package(package_path, install_deps=False)
    assert result["package"] == "local/counter"
    assert "count" in result["outputs"]


def test_space_build_embeds_models_and_runs_without_registry(tmp_path: Path):
    space_pkg = build_package(_write_space(tmp_path / "space"), package_name="local/source-space", version="1.0.0")
    validation = validate_package(space_pkg)
    assert validation.valid
    unpacked = unpack_package(space_pkg, dest=tmp_path / "unpacked-space")
    assert (unpacked / "payload" / "models" / "counter" / "model.yaml").exists()
    assert (unpacked / "payload" / "models" / "accumulator" / "model.yaml").exists()
    result = run_package(space_pkg, install_deps=False)
    assert result["package"] == "local/source-space"
    assert result["modules"] == [
        {"alias": "counter", "path": "models/counter", "package": "local/counter", "version": "1.0.0"},
        {"alias": "accumulator", "path": "models/accumulator", "package": "local/accumulator", "version": "1.0.0"},
    ]


def test_export_space_alias_embeds_models(tmp_path: Path):
    exported = export_space_package(_write_space(tmp_path / "space"), package_name="local/source-space", version="1.0.0")
    validation = validate_package(exported)
    assert validation.valid
    result = run_package(exported, install_deps=False)
    assert result["package"] == "local/source-space"


def test_build_space_from_source_path_refs(tmp_path: Path):
    space_dir = _write_path_manifest_space(tmp_path / "source-space")

    package_path = build_package(space_dir, package_name="local/source-space", version="1.0.0")

    validation = validate_package(package_path)
    assert validation.valid

    unpacked = unpack_package(package_path, dest=tmp_path / "source-space-unpacked")
    assert (unpacked / "payload" / "models" / "counter" / "model.yaml").exists()
    result = run_package(package_path, install_deps=False)
    assert result["package"] == "local/source-space"
    assert result["modules"] == [
        {
            "alias": "counter",
            "path": "models/counter",
        }
    ]


def test_build_space_from_source_path_refs_does_not_require_nested_package_identity(tmp_path: Path):
    space_dir = _write_path_manifest_space(tmp_path / "source-space")
    package_path = build_package(space_dir, package_name="local/source-space", version="1.0.0")
    validation = validate_package(package_path)
    assert validation.valid


def test_space_build_preserves_source_provenance(tmp_path: Path):
    source = {"path": "spaces/demo/space.yaml", "commit": "abc123"}
    space_pkg = build_package(
        _write_space(tmp_path / "space"),
        package_name="local/provenance-space",
        version="1.0.0",
        source=source,
    )

    validation = validate_package(space_pkg)
    assert validation.valid
    assert validation.metadata["source"] == source
    assert validation.metadata["provenance"] == source


def test_build_rejects_legacy_source_provenance(tmp_path: Path):
    model_dir = _write_counter_model(tmp_path / "counter", package_name="local/counter", version="1.0.0")

    with pytest.raises(PackageError, match="must not include legacy source keys"):
        build_package(
            model_dir,
            package_name="local/counter",
            version="1.0.0",
            source={"repo": "Biosimulant/models-demo", "manifest_path": "models/counter/model.yaml"},
        )


def test_space_build_embeds_child_spaces_and_runs_without_registry(tmp_path: Path):
    parent_pkg = build_package(
        _write_parent_space_with_child(tmp_path / "parent-space"),
        package_name="local/parent-space",
        version="1.0.0",
    )

    validation = validate_package(parent_pkg)
    assert validation.valid
    unpacked = unpack_package(parent_pkg, dest=tmp_path / "parent-space-unpacked")
    assert (unpacked / "payload" / "spaces" / "child-space" / "space.yaml").exists()
    result = run_package(parent_pkg, install_deps=False)
    assert result["package"] == "local/parent-space"
    assert result["modules"] == [
        {"alias": "accumulator", "path": "models/accumulator", "package": "local/accumulator", "version": "1.0.0"},
        {"alias": "nested.counter", "path": "spaces/child-space/models/counter", "package": "local/counter", "version": "1.0.0"},
    ]


def test_space_build_rejects_nested_package_refs(tmp_path: Path):
    path = tmp_path / "legacy-space"
    path.mkdir(parents=True, exist_ok=True)
    (path / "space.yaml").write_text(
        """
schema_version: "2.0"
title: "Legacy Space"
models:
  - package: local/counter
    version: 1.0.0
    alias: counter
runtime:
  duration: 0.2
  tick_dt: 0.1
  initial_inputs: {}
wiring: []
""".strip()
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(PackageError, match="must use path references only"):
        build_package(path, package_name="local/legacy-space", version="1.0.0")


def test_invalid_dependency_pin_fails(tmp_path: Path):
    model_dir = tmp_path / "bad-model"
    model_dir.mkdir()
    (model_dir / "model.yaml").write_text(
        """
schema_version: "2.0"
title: "Bad"
description: "Bad"
standard: other
tags: [test]
authors: ["Tests"]
biosim:
  entrypoint: "src.bad:Bad"
runtime:
  dependencies:
    packages:
      - numpy>=1.0
""".strip()
        + "\n",
        encoding="utf-8",
    )
    src_dir = model_dir / "src"
    src_dir.mkdir()
    (src_dir / "bad.py").write_text(
        """
from biosim import BioModule


class Bad(BioModule):
    def advance_to(self, t): return
    def get_outputs(self): return {}
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PackageError):
        build_package(model_dir)
