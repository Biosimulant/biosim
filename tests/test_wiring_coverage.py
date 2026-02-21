"""Tests for biosim.wiring – cover all uncovered lines and error paths."""
import pytest
from pathlib import Path
from biosim.wiring import (
    _parse_ref,
    _import_from_string,
    WiringBuilder,
    build_from_spec,
    load_wiring,
    load_wiring_yaml,
)
from biosim.world import BioWorld


def _make_module(biosim, min_dt=0.1, inputs_set=None, outputs_set=None):
    class M(biosim.BioModule):
        def __init__(self):
            self.min_dt = min_dt

        def advance_to(self, t):
            pass

        def get_outputs(self):
            return {}

        def inputs(self):
            return inputs_set or set()

        def outputs(self):
            return outputs_set or set()

    return M()


def test_parse_ref_valid():
    name, port = _parse_ref("eye.visual_stream")
    assert name == "eye"
    assert port == "visual_stream"


def test_parse_ref_invalid():
    with pytest.raises(ValueError, match="Invalid reference"):
        _parse_ref("no_dot")


def test_import_from_string_valid():
    cls = _import_from_string("biosim.world.BioWorld")
    assert cls is BioWorld


def test_import_from_string_invalid():
    with pytest.raises(ValueError, match="Invalid import path"):
        _import_from_string("nomodule")


def test_wiring_builder_duplicate_name_different_module(biosim):
    world = BioWorld()
    builder = WiringBuilder(world)
    m1 = _make_module(biosim)
    m2 = _make_module(biosim)
    builder.add("m", m1)
    with pytest.raises(ValueError, match="already registered"):
        builder.add("m", m2)


def test_wiring_builder_unknown_source_on_apply(biosim):
    world = BioWorld()
    builder = WiringBuilder(world)
    builder._pending_connections.append(("unknown.port", ["m.port"]))
    with pytest.raises(KeyError, match="unknown module name"):
        builder.apply()


def test_wiring_builder_unknown_dst_on_apply(biosim):
    world = BioWorld()
    builder = WiringBuilder(world)
    m = _make_module(biosim)
    builder.add("src", m)
    builder.connect("src.x", ["unknown.y"])
    with pytest.raises(KeyError, match="unknown module"):
        builder.apply()


def test_wiring_builder_invalid_src_port(biosim):
    world = BioWorld()
    builder = WiringBuilder(world)
    m = _make_module(biosim, outputs_set={"valid_out"})
    builder.add("src", m)
    builder.add("dst", _make_module(biosim))
    builder.connect("src.bad_port", ["dst.x"])
    with pytest.raises(ValueError, match="no output port"):
        builder.apply()


def test_wiring_builder_invalid_dst_port(biosim):
    world = BioWorld()
    builder = WiringBuilder(world)
    builder.add("src", _make_module(biosim))
    builder.add("dst", _make_module(biosim, inputs_set={"valid_in"}))
    builder.connect("src.x", ["dst.bad_port"])
    with pytest.raises(ValueError, match="no input port"):
        builder.apply()


def test_build_from_spec_string_module(biosim):
    """Module entry can be a dotted string (shorthand)."""
    from examples.wiring_builder_demo import Eye

    world = BioWorld()
    spec = {
        "modules": {
            "eye": f"{Eye.__module__}.{Eye.__name__}",
        },
    }
    builder = build_from_spec(world, spec)
    assert "eye" in builder.registry


def test_build_from_spec_invalid_class(biosim):
    world = BioWorld()
    spec = {"modules": {"bad": {"class": 123}}}
    with pytest.raises(ValueError, match="Invalid class"):
        build_from_spec(world, spec)


def test_build_from_spec_invalid_args(biosim):
    from examples.wiring_builder_demo import Eye

    world = BioWorld()
    spec = {"modules": {"bad": {"class": f"{Eye.__module__}.{Eye.__name__}", "args": "not_a_dict"}}}
    with pytest.raises(ValueError, match="Invalid args"):
        build_from_spec(world, spec)


def test_build_from_spec_invalid_entry_type(biosim):
    world = BioWorld()
    spec = {"modules": {"bad": 42}}
    with pytest.raises(ValueError, match="Invalid module entry"):
        build_from_spec(world, spec)


def test_build_from_spec_not_biomodule(biosim):
    world = BioWorld()
    spec = {"modules": {"bad": "biosim.world.BioWorld"}}
    with pytest.raises(TypeError, match="not a BioModule"):
        build_from_spec(world, spec)


def test_build_from_spec_invalid_wiring_entry(biosim):
    from examples.wiring_builder_demo import Eye

    world = BioWorld()
    spec = {
        "modules": {"eye": f"{Eye.__module__}.{Eye.__name__}"},
        "wiring": ["not_a_dict"],
    }
    with pytest.raises(ValueError, match="Invalid wiring entry"):
        build_from_spec(world, spec)


def test_build_from_spec_wiring_missing_fields(biosim):
    from examples.wiring_builder_demo import Eye

    world = BioWorld()
    spec = {
        "modules": {"eye": f"{Eye.__module__}.{Eye.__name__}"},
        "wiring": [{"from": "eye.x"}],  # missing 'to'
    }
    with pytest.raises(ValueError, match="require 'from'"):
        build_from_spec(world, spec)


def test_build_from_spec_empty():
    """Empty/None spec should work fine."""
    world = BioWorld()
    builder = build_from_spec(world, {})
    assert len(builder.registry) == 0


def test_build_from_spec_non_mapping():
    """Non-mapping spec should still work (treated as no modules/wiring)."""
    world = BioWorld()
    builder = build_from_spec(world, [])
    assert len(builder.registry) == 0


def test_load_wiring_unsupported_suffix(biosim, tmp_path):
    world = BioWorld()
    path = tmp_path / "wiring.json"
    path.write_text("{}")
    with pytest.raises(ValueError, match="Unsupported"):
        load_wiring(world, path)


def test_load_wiring_yaml_non_mapping(biosim, tmp_path):
    world = BioWorld()
    path = tmp_path / "wiring.yaml"
    path.write_text("- item1\n- item2\n")
    with pytest.raises(ValueError, match="mapping"):
        load_wiring_yaml(world, path)


def test_build_from_spec_with_priority_and_min_dt(biosim):
    from examples.wiring_builder_demo import Eye

    world = BioWorld()
    spec = {
        "modules": {
            "eye": {
                "class": f"{Eye.__module__}.{Eye.__name__}",
                "min_dt": 0.5,
                "priority": 10,
            },
        },
    }
    builder = build_from_spec(world, spec)
    assert "eye" in builder.registry
