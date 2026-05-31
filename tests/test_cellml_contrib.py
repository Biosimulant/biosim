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
from biosim.signals import RecordSignal, ScalarSignal


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
    assert outputs["trajectory"].value["payload"]["series"][0]["name"] == "state_x"
    assert len(outputs["trajectory"].value["payload"]["series"][0]["points"]) == 3
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

    with pytest.raises(CellMLRuntimeError, match=r"pip install 'biosimulant\[cellml\]'"):
        wrapper.setup()


def test_cellml_issue_helpers_cache_roots_and_generated_module_loading(tmp_path, monkeypatch) -> None:
    class Issue:
        def __init__(self, description: str, level: int = 0) -> None:
            self._description = description
            self._level = level

        def level(self):
            return self._level

        def description(self):
            return self._description

    class IssueContainer:
        def issueCount(self):
            return 3

        def issue(self, index):
            if index == 0:
                return Issue("fatal")
            if index == 1:
                return Issue("warning", level=1)
            raise RuntimeError("missing issue")

    assert cellml_module._call_issues(IssueContainer()) == ["fatal", "warning", "issue 2"]
    assert cellml_module._call_issues(IssueContainer(), fatal_only=True) == ["fatal", "issue 2"]
    with pytest.raises(CellMLRuntimeError, match="CellML parse failed: fatal"):
        cellml_module._raise_on_issues("parse", IssueContainer())

    monkeypatch.setenv("BIOSIM_CELLML_CACHE", str(tmp_path / "cache"))
    assert cellml_module._cache_root() == tmp_path / "cache"
    monkeypatch.delenv("BIOSIM_CELLML_CACHE")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert cellml_module._cache_root() == tmp_path / "xdg" / "biosim" / "cellml"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert cellml_module._cache_root().name == "cellml"

    generated = tmp_path / "generated.py"
    generated.write_text("ANSWER = 42\n", encoding="utf-8")
    module = cellml_module._load_generated_module(generated, "_test_generated_cellml")
    assert module.ANSWER == 42

    with pytest.raises(CellMLRuntimeError, match="failed to import"):
        cellml_module._load_generated_module(tmp_path / "missing.py", "_test_missing_cellml")


def test_cellml_nlasolver_existing_module_and_failure(monkeypatch) -> None:
    existing = types.ModuleType("nlasolver")
    monkeypatch.setitem(sys.modules, "nlasolver", existing)
    cellml_module._ensure_nlasolver_module()
    assert sys.modules["nlasolver"] is existing

    monkeypatch.delitem(sys.modules, "nlasolver", raising=False)
    scipy_module = types.ModuleType("scipy")
    optimize_module = types.ModuleType("scipy.optimize")

    class Failed:
        success = False
        message = "did not converge"
        x = [0.0]

    optimize_module.root = lambda residual, guess: Failed()
    monkeypatch.setitem(sys.modules, "scipy", scipy_module)
    monkeypatch.setitem(sys.modules, "scipy.optimize", optimize_module)

    cellml_module._ensure_nlasolver_module()
    from nlasolver import nla_solve

    with pytest.raises(CellMLRuntimeError, match="did not converge"):
        nla_solve(lambda u, f, data: None, [0.0], 1, None)


def test_cellml_normalisation_noop_and_nonzero_voi_cases() -> None:
    assert normalise_cellml_for_codegen("<not xml") == "<not xml"
    assert normalise_cellml_for_codegen("<model name='plain'/>") == "<model name='plain'/>"

    cellml = """<model xmlns="http://www.cellml.org/cellml/1.1#" name="m">
      <component name="main">
        <variable name="t" units="second" initial_value="5"/>
        <variable name="x" units="dimensionless"/>
        <math xmlns="http://www.w3.org/1998/Math/MathML">
          <apply><eq/><apply><diff/><bvar><ci>t</ci></bvar><ci>x</ci></apply><cn>0</cn></apply>
        </math>
      </component>
    </model>"""
    assert 'initial_value="5"' in normalise_cellml_for_codegen(cellml)


def test_generated_cellml_model_attribute_metadata_and_constants() -> None:
    class Info:
        def __init__(self, name: str, component: str, units: str) -> None:
            self.name = name
            self.component = component
            self.units = units

    module = types.SimpleNamespace()
    module.STATE_INFO = [Info("x", "main", "u")]
    module.VARIABLE_INFO = [Info("y", "aux", "v")]
    module.STATE_COUNT = 1
    module.VARIABLE_COUNT = 1

    def initialise(states, rates, variables):
        states[0] = 2.0
        variables[0] = 4.0

    def compute_constants(variables):
        variables[0] = 5.0

    def compute_rates(_t, states, rates, _variables):
        rates[0] = states[0] + 1.0

    def compute_variables(_t, states, rates, variables):
        variables[0] = states[0] + rates[0]

    module.initialise_variables = initialise
    module.compute_computed_constants = compute_constants
    module.compute_rates = compute_rates
    module.compute_variables = compute_variables

    adapter = GeneratedCellMLModel(module)

    assert adapter.labels() == {"x": "main.x", "y": "aux.y"}
    assert adapter.units() == {"x": "u", "y": "v"}
    assert adapter.initialise_state() == ([2.0], [3.0], [5.0])
    assert cellml_module._to_list(None) == []


def test_libcellml_codegen_pipeline_and_cache(tmp_path, monkeypatch) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model name='m'/>", encoding="utf-8")
    calls: list[str] = []

    class NoIssues:
        def issueCount(self):
            return 0

    class Parser(NoIssues):
        def setStrict(self, value):
            calls.append(f"parser-strict:{value}")

        def parseModel(self, text):
            calls.append("parse")
            return {"text": text}

    class Importer(NoIssues):
        def setStrict(self, value):
            calls.append(f"importer-strict:{value}")

        def resolveImports(self, model, directory):
            calls.append(f"resolve:{Path(directory).name}")

        def flattenModel(self, model):
            calls.append("flatten")
            return {"flat": model}

    class Validator(NoIssues):
        def validateModel(self, model):
            calls.append("validate")

    class Analyser(NoIssues):
        def analyseModel(self, model):
            calls.append("analyse")

        def model(self):
            return "analysed"

    class Generator(NoIssues):
        def setProfile(self, profile):
            calls.append("profile")

        def processModel(self, model):
            calls.append(f"process:{model}")

        def implementationCode(self):
            return "VALUE = 6E7.0\n"

    class GeneratorProfile:
        class Profile:
            PYTHON = "python"

        def __init__(self, profile):
            self.profile = profile

    fake_libcellml = types.SimpleNamespace(
        versionString=lambda: "0.6.3",
        Parser=Parser,
        Importer=Importer,
        Validator=Validator,
        Analyser=Analyser,
        Generator=Generator,
        GeneratorProfile=GeneratorProfile,
    )
    monkeypatch.setitem(sys.modules, "libcellml", fake_libcellml)

    wrapper = LibCellMLBioModule(str(model_file), cache_dir=tmp_path / "cache")
    implementation = wrapper._generate_python_code(fake_libcellml, model_file.read_text(encoding="utf-8"))
    assert "6E7.0" not in implementation
    assert calls == [
        "parser-strict:False",
        "parse",
        "importer-strict:False",
        f"resolve:{tmp_path.name}",
        "flatten",
        "validate",
        "analyse",
        "profile",
        "process:analysed",
    ]

    module = wrapper._prepare_generated_module()
    assert module.VALUE == 6e7
    cache_files = list((tmp_path / "cache").glob("*.py"))
    assert len(cache_files) == 1

    cache_files[0].write_text("VALUE = 9\n", encoding="utf-8")
    module = wrapper._prepare_generated_module()
    assert module.VALUE == 9

    class EmptyGenerator(Generator):
        def implementationCode(self):
            return ""

    fake_empty = types.SimpleNamespace(
        Parser=Parser,
        Importer=None,
        Validator=Validator,
        Analyser=Analyser,
        Generator=EmptyGenerator,
        GeneratorProfile=GeneratorProfile,
    )
    with pytest.raises(CellMLRuntimeError, match="produced no Python implementation"):
        wrapper._generate_python_code(fake_empty, "<model />")


def test_libcellml_wrapper_overrides_reset_failure_and_no_state_paths(tmp_path) -> None:
    model_file = tmp_path / "model.cellml"
    model_file.write_text("<model />", encoding="utf-8")

    module = types.SimpleNamespace()
    module.STATE_INFO = []
    module.VARIABLE_INFO = [{"name": "y", "component": "", "units": "dimensionless"}]
    module.STATE_COUNT = 0
    module.VARIABLE_COUNT = 1
    module.create_variables_array = lambda: [2.0]
    module.initialise_variables = lambda states, variables: variables.__setitem__(0, 2.0)
    module.compute_rates = lambda t, states, rates, variables: None
    module.compute_variables = lambda t, states, rates, variables: variables.__setitem__(0, 4.0 + float(t))

    class FailedSolver:
        success = False
        message = "bad integration"
        t = []
        y = []

    def failing_solver(rhs, span, y0, *, t_eval):
        assert rhs(0.0, []) == []
        return FailedSolver()

    class Wrapper(LibCellMLBioModule):
        _PARAMETER_INPUTS = {"y_param": ("y", 2.0, "u", "Set y.")}
        _INITIAL_CONDITION_INPUTS = {"y_initial": ("y", 2.0, "u", "Set y initially.")}
        _ENABLE_PARAMETER_OVERRIDES = True
        _ENABLE_INITIAL_CONDITIONS = True
        _EMIT_VARIABLE_LABELS = False
        _HEADLINE_OUTPUTS = {"mean_y": ("y", "u", "Mean y.")}

    wrapper = Wrapper(str(model_file), generated_module=module, solver=failing_solver)
    specs = wrapper.inputs()
    wrapper.set_inputs(
        {
            "y_param": ScalarSignal("test", "y_param", 8.0, 0.0, spec=specs["y_param"]),
            "y_initial": ScalarSignal("test", "y_initial", 9.0, 0.0, spec=specs["y_initial"]),
            "parameter_overrides": RecordSignal(
                "test",
                "parameter_overrides",
                {"payload": {"y": 10.0}},
                0.0,
                spec=specs["parameter_overrides"],
            ),
            "initial_conditions": RecordSignal(
                "test",
                "initial_conditions",
                {"payload": {"y": 11.0}},
                0.0,
                spec=specs["initial_conditions"],
            ),
        }
    )
    wrapper.setup()
    assert wrapper._observables == ["y"]
    assert "variable_labels" not in wrapper.outputs()
    wrapper.publish_outputs(0.0)
    assert wrapper.get_outputs()["mean_y"].value == 4.0

    with pytest.raises(CellMLRuntimeError, match="bad integration"):
        wrapper.advance_window(0.0, 1.0)

    wrapper.reset()
    assert wrapper.get_outputs()["state"].value == {"y": 4.0}
