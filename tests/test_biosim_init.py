"""Tests for biosim.__init__ – lazy imports and __dir__."""
import importlib

import pytest


def test_getattr_simui_removed(biosim):
    """The old public SimUI API is removed; labs serve owns the local UI."""
    with pytest.raises(AttributeError):
        biosim.__getattr__("simui")


def test_getattr_onnx_module_lazy_import(biosim):
    cls = biosim.__getattr__("OnnxClassifierModule")
    assert cls is not None
    assert cls.__name__ == "OnnxClassifierModule"


def test_getattr_unknown_raises():
    """__getattr__ should raise AttributeError for unknown names."""
    import biosim

    try:
        biosim.__getattr__("no_such_attr_xyz")
        assert False, "Should have raised AttributeError"
    except AttributeError as e:
        assert "no_such_attr_xyz" in str(e)


def test_dir_excludes_simui():
    """__dir__ should include lazy namespaces and exported helpers."""
    import biosim

    names = biosim.__dir__()
    assert "simui" not in names
    assert "onnx" in names
    assert "OnnxClassifierModule" in names
    assert "__version__" in names
    assert names == sorted(names)
