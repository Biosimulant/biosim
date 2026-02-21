"""Tests for biosim.simui.registry – 100% coverage."""
import inspect
from typing import Optional

import pytest
from biosim.modules import BioModule
from biosim.simui.registry import (
    ArgSpec, ModuleSpec, _get_arg_type_str,
    introspect_module, discover_pack_modules,
    ModuleRegistry, get_default_registry,
)


class SimpleModule(BioModule):
    """A simple test module with documented behavior."""

    def __init__(self, rate: float = 0.1, name: str = "default"):
        self.min_dt = rate
        self._name = name

    def advance_to(self, t):
        pass

    def get_outputs(self):
        return {}

    def inputs(self):
        return {"signal_in"}

    def outputs(self):
        return {"signal_out"}


class NoArgsModule(BioModule):
    """Module with no constructor args."""

    def __init__(self):
        self.min_dt = 0.1

    def advance_to(self, t):
        pass

    def get_outputs(self):
        return {}


class FailingInitModule(BioModule):
    """Module that requires non-trivial args to instantiate."""

    def __init__(self, complex_arg):
        self.min_dt = 0.1
        if complex_arg is None:
            raise ValueError("Must provide complex_arg")

    def advance_to(self, t):
        pass

    def get_outputs(self):
        return {}

    def inputs(self):
        return {"port_a"}

    def outputs(self):
        return {"port_b"}


class TestGetArgTypeStr:
    def test_empty_annotation(self):
        assert _get_arg_type_str(inspect.Parameter.empty) == "any"

    def test_basic_type(self):
        assert _get_arg_type_str(float) == "float"
        assert _get_arg_type_str(str) == "str"
        assert _get_arg_type_str(int) == "int"

    def test_optional_type(self):
        result = _get_arg_type_str(Optional[float])
        assert result == "float"

    def test_generic_type(self):
        from typing import List
        result = _get_arg_type_str(List[int])
        assert result == "list"

    def test_string_annotation(self):
        result = _get_arg_type_str("some_annotation")
        assert result == "some_annotation"


class TestIntrospectModule:
    def test_simple_module(self):
        spec = introspect_module(SimpleModule, "test.SimpleModule", "test")
        assert spec.name == "SimpleModule"
        assert spec.class_path == "test.SimpleModule"
        assert spec.category == "test"
        assert "signal_in" in spec.inputs
        assert "signal_out" in spec.outputs
        assert len(spec.args) == 2
        rate_arg = next(a for a in spec.args if a.name == "rate")
        assert rate_arg.type == "float"
        assert rate_arg.default == 0.1
        assert rate_arg.required is False

    def test_no_args_module(self):
        spec = introspect_module(NoArgsModule, "test.NoArgs", "test")
        assert spec.name == "NoArgsModule"
        assert len(spec.args) == 0

    def test_failing_init_module(self):
        """Module that can't be instantiated should still get some port info."""
        spec = introspect_module(FailingInitModule, "test.Failing", "test")
        assert spec.name == "FailingInitModule"
        # Should still extract args
        assert len(spec.args) == 1
        assert spec.args[0].name == "complex_arg"
        assert spec.args[0].required is True

    def test_description_from_docstring(self):
        spec = introspect_module(SimpleModule, "test.Simple", "test")
        assert spec.description is not None
        assert "simple test module" in spec.description.lower()


class TestModuleRegistry:
    def test_register_module(self):
        reg = ModuleRegistry()
        reg.register_module(SimpleModule, "test.Simple", "custom")
        assert reg.get("test.Simple") is not None
        assert reg.get("test.Simple").name == "SimpleModule"

    def test_all_modules(self):
        reg = ModuleRegistry()
        reg.register_module(SimpleModule, "test.Simple", "custom")
        reg.register_module(NoArgsModule, "test.NoArgs", "custom")
        all_mods = reg.all_modules()
        assert len(all_mods) == 2

    def test_by_category(self):
        reg = ModuleRegistry()
        reg.register_module(SimpleModule, "test.Simple", "cat_a")
        reg.register_module(NoArgsModule, "test.NoArgs", "cat_b")
        cats = reg.by_category()
        assert "cat_a" in cats
        assert "cat_b" in cats
        assert len(cats["cat_a"]) == 1

    def test_to_json(self):
        reg = ModuleRegistry()
        reg.register_module(SimpleModule, "test.Simple", "test")
        j = reg.to_json()
        assert "modules" in j
        assert "categories" in j
        assert "test.Simple" in j["modules"]
        mod_data = j["modules"]["test.Simple"]
        assert mod_data["name"] == "SimpleModule"
        assert "args" in mod_data

    def test_get_missing(self):
        reg = ModuleRegistry()
        assert reg.get("nonexistent") is None

    def test_register_pack_import_error(self):
        reg = ModuleRegistry()
        reg.register_pack("definitely.not.a.real.package", "missing")
        assert len(reg.all_modules()) == 0


class TestDiscoverPackModules:
    def test_nonexistent_pack(self):
        result = discover_pack_modules("fake.pack.xxx", "test")
        assert result == {}


class TestGetDefaultRegistry:
    def test_returns_instance(self):
        reg = get_default_registry()
        assert isinstance(reg, ModuleRegistry)

    def test_singleton(self):
        r1 = get_default_registry()
        r2 = get_default_registry()
        assert r1 is r2
