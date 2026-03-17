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


def _write_accumulator_model(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "model.yaml").write_text(
        """
schema_version: "2.0"
title: "Test: Accumulator"
description: "Accumulator model"
standard: other
tags: [test]
authors: ["Tests"]
biosim:
  entrypoint: "src.accumulator:Accumulator"
""".strip()
        + "\n",
        encoding="utf-8",
    )
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
    (path / "space.yaml").write_text(
        """
schema_version: "2.0"
title: "Test: Space"
description: "Reference based space"
models:
  - package: local/counter
    version: 1.0.0
    alias: counter
  - package: local/accumulator
    version: 1.0.0
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


def test_space_package_resolves_referenced_models_from_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    registry_dir = tmp_path / "registry"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("BIOSIM_PACKAGE_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setenv("BIOSIM_PACKAGE_CACHE_DIR", str(cache_dir))

    counter_pkg = build_package(_write_counter_model(tmp_path / "counter"), package_name="local/counter", version="1.0.0")
    acc_pkg = build_package(_write_accumulator_model(tmp_path / "acc"), package_name="local/accumulator", version="1.0.0")
    publish_package(counter_pkg)
    publish_package(acc_pkg)

    space_pkg = build_package(_write_space(tmp_path / "space"), package_name="local/reference-space", version="1.0.0")
    result = run_package(space_pkg, install_deps=False)
    assert result["package"] == "local/reference-space"
    assert [module["package"] for module in result["modules"]] == ["local/counter", "local/accumulator"]
    assert (cache_dir / "local" / "counter" / "1.0.0").exists()


def test_export_space_bundles_models(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    registry_dir = tmp_path / "registry"
    cache_dir = tmp_path / "cache"
    monkeypatch.setenv("BIOSIM_PACKAGE_REGISTRY_DIR", str(registry_dir))
    monkeypatch.setenv("BIOSIM_PACKAGE_CACHE_DIR", str(cache_dir))

    publish_package(build_package(_write_counter_model(tmp_path / "counter"), package_name="local/counter", version="1.0.0"))
    publish_package(build_package(_write_accumulator_model(tmp_path / "acc"), package_name="local/accumulator", version="1.0.0"))

    exported = export_space_package(_write_space(tmp_path / "space"), package_name="local/bundled-space", version="1.0.0")
    validation = validate_package(exported)
    assert validation.valid
    assert validation.metadata["bundle_mode"] == "bundled"

    shutil_env = os.environ.pop("BIOSIM_PACKAGE_REGISTRY_DIR")
    try:
        result = run_package(exported, install_deps=False)
    finally:
        os.environ["BIOSIM_PACKAGE_REGISTRY_DIR"] = shutil_env
    assert result["package"] == "local/bundled-space"


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
