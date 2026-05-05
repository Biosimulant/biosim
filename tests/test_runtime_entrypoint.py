from __future__ import annotations

from pathlib import Path

import pytest

from biosim.runtime import load_entrypoint


def _write_model(root: Path, module: str, class_name: str, marker: str) -> None:
    src = root / "src"
    src.mkdir(parents=True)
    (src / f"{module}.py").write_text(
        f"class {class_name}:\n    marker = {marker!r}\n",
        encoding="utf-8",
    )


def test_load_entrypoint_flushes_namespace_package_cache(tmp_path: Path) -> None:
    model_a = tmp_path / "a"
    model_b = tmp_path / "b"
    _write_model(model_a, "model", "Model", "a")
    _write_model(model_b, "model", "Model", "b")

    cls_a = load_entrypoint("src.model:Model", model_path=model_a)
    cls_b = load_entrypoint("src.model:Model", model_path=model_b)

    assert cls_a.marker == "a"
    assert cls_b.marker == "b"


def test_load_entrypoint_falls_back_to_import_module() -> None:
    assert load_entrypoint("json:loads", model_path="/missing/path").__name__ == "loads"


def test_load_entrypoint_wraps_errors_with_requested_type(tmp_path: Path) -> None:
    _write_model(tmp_path, "model", "Model", "x")

    with pytest.raises(ValueError, match="Entrypoint attribute not found"):
        load_entrypoint("src.model:Missing", model_path=tmp_path, error_cls=ValueError)
