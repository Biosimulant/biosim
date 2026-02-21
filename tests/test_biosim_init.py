"""Tests for biosim.__init__ – lazy imports and __dir__."""
import importlib


def test_getattr_simui_lazy_import(biosim):
    """__getattr__ should lazily import simui (or raise ImportError if deps missing)."""
    try:
        mod = biosim.__getattr__("simui")
        assert mod is not None
    except ImportError:
        # SimUI deps (fastapi) not installed - that's fine, we covered the code path
        pass


def test_getattr_unknown_raises():
    """__getattr__ should raise AttributeError for unknown names."""
    import biosim

    try:
        biosim.__getattr__("no_such_attr_xyz")
        assert False, "Should have raised AttributeError"
    except AttributeError as e:
        assert "no_such_attr_xyz" in str(e)


def test_dir_includes_simui():
    """__dir__ should include 'simui' in its output."""
    import biosim

    names = biosim.__dir__()
    assert "simui" in names
    assert "__version__" in names
    assert names == sorted(names)
