from __future__ import annotations

from pathlib import Path

import pytest

from biosim.runtime import load_entrypoint
from biosim.runtime.entrypoint import flush_package_cache


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


def test_load_entrypoint_supports_dotted_entrypoint_without_model_path() -> None:
    assert load_entrypoint("json.loads").__name__ == "loads"


def test_load_entrypoint_reports_invalid_and_import_errors(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Invalid entrypoint"):
        load_entrypoint("invalid", error_cls=ValueError)

    with pytest.raises(ValueError, match="Failed to import module"):
        load_entrypoint("missing.module:Factory", error_cls=ValueError)

    broken_src = tmp_path / "src"
    broken_src.mkdir()
    (broken_src / "broken.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Failed to import module"):
        load_entrypoint("src.broken:Factory", model_path=tmp_path, error_cls=ValueError)


def test_load_entrypoint_can_reraise_original_cause_when_error_cls_is_none() -> None:
    with pytest.raises(ModuleNotFoundError):
        load_entrypoint("missing_module:Factory", error_cls=None)


def test_flush_package_cache_removes_package_and_children(monkeypatch) -> None:
    import sys
    import types

    monkeypatch.setitem(sys.modules, "temporary_pkg", types.ModuleType("temporary_pkg"))
    monkeypatch.setitem(sys.modules, "temporary_pkg.child", types.ModuleType("temporary_pkg.child"))
    monkeypatch.setitem(sys.modules, "temporary_pkg_extra", types.ModuleType("temporary_pkg_extra"))

    flush_package_cache("temporary_pkg")

    assert "temporary_pkg" not in sys.modules
    assert "temporary_pkg.child" not in sys.modules
    assert "temporary_pkg_extra" in sys.modules
