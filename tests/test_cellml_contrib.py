# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Tests for optional CellML contrib helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest

from biosim.contrib import cellml as cellml_module
from biosim.contrib.cellml import (
    CellMLRuntimeError,
    GeneratedCellMLModel,
    LibCellMLBioModule,
    cellml_cache_key,
    normalise_cellml_for_codegen,
)
from biosim.signals import ScalarSignal


def _fake_generated_module(*, camel_case: bool = False) -> types.SimpleNamespace:
    module = types.SimpleNamespace()
    module.STATE_INFO = [{"name": "x", "component": "main", "units": "dimensionless"}]
    module.VARIABLE_INFO = [{"name": "y", "component": "main", "units": "dimensionless"}]
    module.STATE_COUNT = 1
    module.VARIABLE_COUNT = 1

    def create_states_array() -> list[float]:
        return [0.0]

    def create_variables_array() -> list[float]:
        return [0.0]

    def initialise_states_and_constants(states: list[float], variables: list[float]) -> None:
        states[0] = 1.0
        variables[0] = 2.0

    def compute_rates(t: float, states: list[float], rates: list[float], variables: list[float]) -> None:
        rates[0] = -float(states[0])

    def compute_variables(t: float, states: list[float], rates: list[float], variables: list[float]) -> None:
        variables[0] = float(states[0]) * 2.0

    if camel_case:
        module.createStatesArray = create_states_array
        module.createVariablesArray = create_variables_array
        module.initialiseStatesAndConstants = initialise_states_and_constants
        module.computeRates = compute_rates
        module.computeVariables = compute_variables
    else:
        module.create_states_array = create_states_array
        module.create_variables_array = create_variables_array
        module.initialise_states_and_constants = initialise_states_and_constants
        module.compute_rates = compute_rates
        module.compute_variables = compute_variables
    return module


class _FakeSolverResult:
    success = True
    t = [0.0, 0.5, 1.0]
    y = [[1.0, 0.5, 0.25]]


def _fake_solver(rhs, span, y0, *, t_eval):
    assert span == (0.0, 1.0)
    assert y0 == [1.0]
    assert t_eval == [0.0, 0.5, 1.0]
    assert rhs(0.0, [1.0]) == [-1.0]
    return _FakeSolverResult()


def _fake_generated_module_with_time_variable() -> types.SimpleNamespace:
    module = types.SimpleNamespace()
    module.STATE_INFO = [{"name": "x", "component": "main", "units": "dimensionless"}]
    module.VARIABLE_INFO = [{"name": "t", "component": "main", "units": "second"}]
    module.STATE_COUNT = 1
    module.VARIABLE_COUNT = 1

    def create_states_array() -> list[float]:
        return [0.0]

    def create_variables_array() -> list[float]:
        return [0.0]

    def initialise_states_and_constants(states: list[float], variables: list[float]) -> None:
        states[0] = 1.0
        variables[0] = 99.0

    def compute_rates(t: float, states: list[float], rates: list[float], variables: list[float]) -> None:
        rates[0] = -float(states[0])

    def compute_variables(t: float, states: list[float], rates: list[float], variables: list[float]) -> None:
        variables[0] = 10.0 + float(t)

    module.create_states_array = create_states_array
    module.create_variables_array = create_variables_array
    module.initialise_states_and_constants = initialise_states_and_constants
    module.compute_rates = compute_rates
    module.compute_variables = compute_variables
    return module


def test_importing_cellml_contrib_does_not_import_optional_dependencies(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "libcellml", raising=False)
    monkeypatch.delitem(sys.modules, "scipy", raising=False)

    __import__("biosim.contrib.cellml")

    assert "libcellml" not in sys.modules
    assert "scipy" not in sys.modules


def test_libcellml_module_resolves_model_path_relative_to_subclass_module(tmp_path, monkeypatch) -> None:
    model_root = tmp_path / "model"
    src_dir = model_root / "src"
    data_dir = model_root / "data"
    src_dir.mkdir(parents=True)
    data_dir.mkdir()
    model_file = data_dir / "model.cellml"
    model_file.write_text("<model />")

    module = types.ModuleType("fake_cellml_wrapper")
    module.__file__ = str(src_dir / "wrapper.py")
    monkeypatch.setitem(sys.modules, "fake_cellml_wrapper", module)

    class Wrapper(LibCellMLBioModule):
        pass

    Wrapper.__module__ = "fake_cellml_wrapper"

    wrapper = Wrapper("data/model.cellml", generated_module=_fake_generated_module(), solver=_fake_solver)

    assert Path(wrapper._model_path) == model_file.resolve()


def test_libcellml_module_resolves_path_when_loader_does_not_register_module(tmp_path) -> None:
    model_root = tmp_path / "model"
    src_dir = model_root / "src"
    data_dir = model_root / "data"
    src_dir.mkdir(parents=True)
    data_dir.mkdir()
    model_file = data_dir / "model.cellml"
    model_file.write_text("<model />")
    wrapper_file = src_dir / "wrapper.py"
    wrapper_file.write_text(
        "from biosim.contrib.cellml import LibCellMLBioModule\n"
        "class Wrapper(LibCellMLBioModule):\n"
        "    pass\n"
    )

    spec = importlib.util.spec_from_file_location("unregistered_cellml_wrapper", wrapper_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    wrapper = module.Wrapper("data/model.cellml", generated_module=_fake_generated_module(), solver=_fake_solver)

    assert "unregistered_cellml_wrapper" not in sys.modules
    assert Path(wrapper._model_path) == model_file.resolve()


def test_cellml_cache_key_changes_when_content_or_libcellml_version_changes() -> None:
    original = cellml_cache_key("<model name='a'/>", libcellml_version="0.6.3")

    assert original != cellml_cache_key("<model name='b'/>", libcellml_version="0.6.3")
    assert original != cellml_cache_key("<model name='a'/>", libcellml_version="0.6.4")


def test_normalise_cellml_for_codegen_removes_zero_voi_initial_value() -> None:
    cellml = """<?xml version="1.0"?>
<model xmlns="http://www.cellml.org/cellml/1.1#" name="m">
  <component name="main">
    <variable name="t" units="second" initial_value="0"/>
    <variable name="x" units="dimensionless" initial_value="1"/>
    <math xmlns="http://www.w3.org/1998/Math/MathML">
      <apply><eq/><apply><diff/><bvar><ci>t</ci></bvar><ci>x</ci></apply><cn>0</cn></apply>
    </math>
  </component>
</model>
"""

    normalised = normalise_cellml_for_codegen(cellml)

    assert 'name="t"' in normalised
    assert 'name="x"' in normalised
    assert 'name="t" units="second" initial_value="0"' not in normalised
    assert 'name="x" units="dimensionless" initial_value="1"' in normalised


def test_normalise_cellml_for_codegen_removes_legacy_metadata_ids() -> None:
    cellml = """<?xml version="1.0"?>
<model xmlns="http://www.cellml.org/cellml/1.1#" name="m" cmeta:id="legacy_model">
  <component name="main" id="duplicate id">
    <variable name="x" units="dimensionless" initial_value="1"/>
    <math xmlns="http://www.w3.org/1998/Math/MathML" cmeta:id="bad math id">
      <apply id="bad apply id"><eq/><ci>x</ci><cn>1</cn></apply>
    </math>
  </component>
</model>
"""

    normalised = normalise_cellml_for_codegen(cellml)

    assert "cmeta:id" not in normalised
    assert ' id="' not in normalised
    assert 'name="main"' in normalised
    assert 'name="x"' in normalised


def test_normalise_cellml_for_codegen_sanitises_invalid_root_model_name() -> None:
    cellml = """<?xml version="1.0"?>
<model xmlns="http://www.cellml.org/cellml/1.1#" name="goldbeter_1990_1.1">
  <component name="main"/>
</model>
"""

    normalised = normalise_cellml_for_codegen(cellml)

    assert 'name="goldbeter_1990_1_1"' in normalised


def test_generated_python_normaliser_repairs_bad_scientific_literals() -> None:
    implementation = "variables[0] = 6E7.0\nstates[2] = 2E-5.0\nx = 1.0\n"

    normalised = cellml_module._normalise_generated_python_code(implementation)

    assert "6E7.0" not in normalised
    assert "2E-5.0" not in normalised
    assert "6E7" in normalised
    assert "2E-5" in normalised
    assert "1.0" in normalised


def test_generated_code_nlasolver_shim_is_lazy_and_solves(monkeypatch) -> None:
    scipy_module = types.ModuleType("scipy")
    optimize_module = types.ModuleType("scipy.optimize")

    class Result:
        success = True
        message = "ok"
        x = [2.0]

    def fake_root(residual, guess):
        assert guess == [0.0]
        assert residual([2.0]) == [0.0]
        return Result()

    optimize_module.root = fake_root
    monkeypatch.setitem(sys.modules, "scipy", scipy_module)
    monkeypatch.setitem(sys.modules, "scipy.optimize", optimize_module)
    monkeypatch.delitem(sys.modules, "nlasolver", raising=False)

    cellml_module._ensure_nlasolver_module()
    from nlasolver import nla_solve

    def objective(u, f, data):
        f[0] = u[0] - data["target"]

    assert nla_solve(objective, [float("nan")], 1, {"target": 2.0}) == [2.0]


@pytest.mark.parametrize("camel_case", [False, True])
def test_generated_code_adapter_supports_libcellml_function_name_styles(camel_case: bool) -> None:
    adapter = GeneratedCellMLModel(_fake_generated_module(camel_case=camel_case))

    states, rates, variables = adapter.initialise_state()

    assert states == [1.0]
    assert rates == [-1.0]
    assert variables == [2.0]
    assert adapter.rates(0.0, [3.0], variables) == [-3.0]
    assert adapter.variables_at(0.0, [4.0], variables) == [8.0]


def test_generated_code_adapter_reports_missing_required_functions() -> None:
    with pytest.raises(CellMLRuntimeError, match="missing required functions"):
        GeneratedCellMLModel(types.SimpleNamespace())


def test_declared_cellml_observables_shape_outputs_before_setup(tmp_path) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model />")

    class Wrapper(LibCellMLBioModule):
        _OBSERVABLES = ["x", "y"]
        _STATE_OUTPUT_ALIASES = {"x": "state_x"}

    wrapper = Wrapper(str(model_file), generated_module=_fake_generated_module(), solver=_fake_solver)

    assert wrapper.outputs()["state"].schema == {"state_x": "float", "y": "float"}
    assert wrapper.outputs()["variable_labels"].schema == {"state_x": "str", "y": "str"}


def test_advance_window_publishes_typed_cellml_signals(tmp_path) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model />")

    class Wrapper(LibCellMLBioModule):
        _OBSERVABLES = ["x", "y"]
        _STATE_OUTPUT_ALIASES = {"x": "state_x"}
        _HEADLINE_OUTPUTS = {
            "mean_state_x": (
                "x",
                "dimensionless",
                "Mean x over the recent simulation window.",
            )
        }

    wrapper = Wrapper(str(model_file), integration_step=0.5, generated_module=_fake_generated_module(), solver=_fake_solver)
    wrapper.advance_window(0.0, 1.0)

    outputs = wrapper.get_outputs()

    assert outputs["state"].value == {"state_x": 0.25, "y": 0.5}
    assert outputs["summary"].value["observable_count"] == 2
    assert outputs["summary"].value["largest_change_observable"] == "y"
    assert outputs["variable_labels"].value == {"state_x": "main.x", "y": "main.y"}
    assert outputs["mean_state_x"].value == pytest.approx((1.0 + 0.5 + 0.25) / 3.0)


def test_source_variable_named_t_does_not_clobber_simulation_time(tmp_path) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model />")

    class Wrapper(LibCellMLBioModule):
        _OBSERVABLES = ["x", "t"]

    wrapper = Wrapper(
        str(model_file),
        integration_step=0.5,
        generated_module=_fake_generated_module_with_time_variable(),
        solver=_fake_solver,
    )
    wrapper.advance_window(0.0, 1.0)

    outputs = wrapper.get_outputs()

    assert outputs["state"].emitted_at == 1.0
    assert outputs["summary"].value["duration_simulated"] == 1.0
    assert outputs["state"].value == {"x": 0.25, "t": 11.0}
    assert wrapper._history[-1]["t"] == 1.0
    assert wrapper._history[-1]["cellml:t"] == 11.0


def test_parameter_and_initial_condition_inputs_apply_before_integration(tmp_path) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model />")

    class Wrapper(LibCellMLBioModule):
        _OBSERVABLES = ["x", "y"]
        _PARAMETER_INPUTS = {
            "y_parameter": (
                "y",
                2.0,
                "dimensionless",
                "Override y before generated variable recomputation.",
            )
        }
        _INITIAL_CONDITION_INPUTS = {
            "initial_x": (
                "x",
                1.0,
                "dimensionless",
                "Initial x state.",
            )
        }

    wrapper = Wrapper(str(model_file), generated_module=_fake_generated_module(), solver=_fake_solver)
    specs = wrapper.inputs()
    wrapper.set_inputs(
        {
            "initial_x": ScalarSignal(
                source="test",
                name="initial_x",
                value=3.0,
                emitted_at=0.0,
                spec=specs["initial_x"],
            ),
            "y_parameter": ScalarSignal(
                source="test",
                name="y_parameter",
                value=9.0,
                emitted_at=0.0,
                spec=specs["y_parameter"],
            ),
        }
    )
    wrapper.setup()

    assert wrapper._states == [3.0]
    assert wrapper.get_outputs()["state"].value == {"x": 3.0, "y": 6.0}


def test_missing_libcellml_dependency_error_is_actionable(tmp_path, monkeypatch) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model />")
    monkeypatch.setitem(sys.modules, "libcellml", None)

    wrapper = LibCellMLBioModule(str(model_file))

    with pytest.raises(CellMLRuntimeError, match=r"pip install 'biosim\[cellml\]'"):
        wrapper.setup()
