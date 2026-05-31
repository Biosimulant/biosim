"""Tests for optional SBML contrib helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import numpy as np
import pytest

from biosim.contrib.sbml import (
    TelluriumSBMLBioModule,
    patch_uninitialised_parameters,
    read_sbml_text,
)
from biosim.signals import RecordSignal, ScalarSignal


def test_importing_sbml_contrib_does_not_import_tellurium(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "tellurium", raising=False)

    __import__("biosim.contrib.sbml")

    assert "tellurium" not in sys.modules


def test_patch_uninitialised_parameters_adds_safe_defaults() -> None:
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core" level="3" version="1">
  <model id="m">
    <listOfParameters>
      <parameter id="t" name="time"/>
      <parameter id="x"/>
      <parameter id="z"/>
      <parameter id="already" value="1"/>
    </listOfParameters>
    <listOfRules>
      <rateRule variable="z"><math xmlns="http://www.w3.org/1998/Math/MathML"/></rateRule>
    </listOfRules>
  </model>
</sbml>
"""

    patched, patches = patch_uninitialised_parameters(xml)

    assert ("t", "assignmentRule->symbolic time") in patches
    assert ("x", "value=0") in patches
    assert all(item[0] != "z" for item in patches)
    assert 'id="x" value="0"' in patched
    assert 'variable="t"' in patched


def test_tellurium_module_resolves_model_path_relative_to_subclass_module(tmp_path, monkeypatch) -> None:
    model_root = tmp_path / "model"
    src_dir = model_root / "src"
    data_dir = model_root / "data"
    src_dir.mkdir(parents=True)
    data_dir.mkdir()
    model_file = data_dir / "model.xml"
    model_file.write_text("<xml />")

    module = types.ModuleType("fake_sbml_wrapper")
    module.__file__ = str(src_dir / "wrapper.py")
    monkeypatch.setitem(sys.modules, "fake_sbml_wrapper", module)

    class Wrapper(TelluriumSBMLBioModule):
        pass

    Wrapper.__module__ = "fake_sbml_wrapper"

    wrapper = Wrapper("data/model.xml")

    assert Path(wrapper._model_path) == model_file.resolve()


def test_tellurium_module_resolves_path_when_loader_does_not_register_module(tmp_path) -> None:
    model_root = tmp_path / "model"
    src_dir = model_root / "src"
    data_dir = model_root / "data"
    src_dir.mkdir(parents=True)
    data_dir.mkdir()
    model_file = data_dir / "model.xml"
    model_file.write_text("<xml />")
    wrapper_file = src_dir / "wrapper.py"
    wrapper_file.write_text(
        "from biosim.contrib.sbml import TelluriumSBMLBioModule\n"
        "class Wrapper(TelluriumSBMLBioModule):\n"
        "    pass\n"
    )

    spec = importlib.util.spec_from_file_location("unregistered_sbml_wrapper", wrapper_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    wrapper = module.Wrapper("data/model.xml")

    assert "unregistered_sbml_wrapper" not in sys.modules
    assert Path(wrapper._model_path) == model_file.resolve()


def test_visualisation_aux_is_opt_in_wrapper_hook(tmp_path) -> None:
    model_file = tmp_path / "model.xml"
    model_file.write_text("<xml />")

    class AuxWrapper(TelluriumSBMLBioModule):
        def visualisation_aux_schema(self):
            return {"phase": "float"}

        def visualisation_aux_payload(self, t, latest):
            return {"phase": latest["x"] + t}

    wrapper = AuxWrapper(str(model_file))
    wrapper._observables = ["x"]
    wrapper._history = [{"t": 1.0, "x": 2.0}]

    wrapper.publish_outputs(1.0)

    assert "visualisation_aux" in wrapper.outputs()
    assert wrapper.get_outputs()["visualisation_aux"].value == {"phase": 3.0}


def test_tellurium_module_supports_configurable_diagnostic_output_names(tmp_path) -> None:
    model_file = tmp_path / "model.xml"
    model_file.write_text("<xml />")

    class FriendlyWrapper(TelluriumSBMLBioModule):
        _OBSERVABLES = ["raw_x"]
        _SPECIES_LABELS = {"raw_x": "Readable observable"}
        _STATE_OUTPUT_ALIASES = {"raw_x": "readable_observable"}
        _STATE_OUTPUT_NAME = "observable_values"
        _SUMMARY_OUTPUT_NAME = "run_summary"
        _SPECIES_LABELS_OUTPUT_NAME = "observable_labels"

    wrapper = FriendlyWrapper(str(model_file))
    wrapper._observables = ["raw_x"]
    wrapper._history = [{"t": 0.0, "raw_x": 1.0}, {"t": 1.0, "raw_x": 3.0}]

    specs = wrapper.outputs()
    wrapper.publish_outputs(1.0)
    outputs = wrapper.get_outputs()

    assert {"observable_values", "run_summary", "observable_labels"} <= set(specs)
    assert {"state", "summary", "species_labels"}.isdisjoint(specs)
    assert outputs["observable_values"].value == {"readable_observable": 3.0}
    assert outputs["observable_labels"].value == {"readable_observable": "Readable observable"}
    assert outputs["run_summary"].value["largest_change_observable"] == "readable_observable"


def test_tellurium_module_named_initial_condition_inputs_apply_at_start(tmp_path) -> None:
    model_file = tmp_path / "model.xml"
    model_file.write_text("<xml />")

    class InitialWrapper(TelluriumSBMLBioModule):
        _OBSERVABLES = ["raw_x"]
        _STATE_OUTPUT_ALIASES = {"raw_x": "readable_observable"}
        _INITIAL_CONDITION_INPUTS = {
            "initial_readable_observable": (
                "raw_x",
                1.0,
                "native SBML value",
                "Initial condition for readable observable.",
            )
        }

    wrapper = InitialWrapper(str(model_file))

    class FakeRunner(dict):
        pass

    wrapper._runner = FakeRunner(raw_x=1.0)
    wrapper._observables = ["raw_x"]
    wrapper._history = [{"t": 0.0, "raw_x": 1.0}]
    wrapper.set_inputs(
        {
            "initial_readable_observable": ScalarSignal(
                source="test",
                name="initial_readable_observable",
                value=7.0,
                emitted_at=0.0,
                spec=wrapper.inputs()["initial_readable_observable"],
            )
        }
    )
    wrapper.publish_outputs(0.0)

    assert wrapper._runner["raw_x"] == 7.0
    assert wrapper.get_outputs()["state"].value == {"readable_observable": 7.0}


def test_read_sbml_text_falls_back_to_latin_1(tmp_path) -> None:
    path = tmp_path / "legacy.xml"
    path.write_bytes("<sbml><model name='caf\xe9'/></sbml>".encode("latin-1"))

    assert "café" in read_sbml_text(path)


@pytest.mark.parametrize(
    "xml",
    [
        "<not xml",
        "<sbml><model /></sbml>",
        '<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"/>',
        """<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"><model>
        <listOfParameters><parameter id="fixed" value="1"/></listOfParameters>
        </model></sbml>""",
    ],
)
def test_patch_uninitialised_parameters_noop_cases(xml: str) -> None:
    patched, patches = patch_uninitialised_parameters(xml)

    assert patched == xml
    assert patches == []


def test_patch_uninitialised_time_parameter_without_existing_rules() -> None:
    xml = """<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"><model>
    <listOfParameters><parameter id="time_seconds" name="time"/></listOfParameters>
    </model></sbml>"""

    patched, patches = patch_uninitialised_parameters(xml)

    assert patches == [("time_seconds", "assignmentRule->symbolic time")]
    assert "listOfRules" in patched


class _FakeTelluriumRunner(dict):
    def __init__(self) -> None:
        super().__init__(raw_x=1.0, raw_y=2.0, p=2.0, aux=3.0)
        self.reset_called = False

    def reset(self) -> None:
        self.reset_called = True

    def simulate(self, start, end, n_steps, *, selections):
        rows = []
        for index in range(n_steps):
            t = float(start) + (float(end) - float(start)) * index / max(n_steps - 1, 1)
            row = []
            for name in selections:
                if name == "time":
                    row.append(t)
                elif name == "raw_x":
                    row.append(t + 10.0)
                elif name == "raw_y":
                    row.append(t + 20.0)
                elif name == "aux":
                    row.append(t + 30.0)
                else:
                    row.append(0.0)
            rows.append(row)
        return np.asarray(rows, dtype=float)


def test_tellurium_sbml_wrapper_runs_with_fake_runner_and_overrides(tmp_path, monkeypatch) -> None:
    model_file = tmp_path / "model.xml"
    model_file.write_text(
        """<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"><model>
        <listOfSpecies>
          <species id="raw_x" name="Raw X" substanceUnits="mole"/>
          <species id="dummy"/>
          <species id="boundary" sboTerm="SBO:0000291"/>
        </listOfSpecies>
        <listOfParameters><parameter id="p" value="2"/><parameter id="raw_y" name="Raw Y"/></listOfParameters>
        <listOfRules><rateRule variable="raw_y"/></listOfRules>
        </model></sbml>""",
        encoding="utf-8",
    )
    fake_runner = _FakeTelluriumRunner()
    tellurium = types.ModuleType("tellurium")
    tellurium.loadSBMLModel = lambda _source: fake_runner
    monkeypatch.setitem(sys.modules, "tellurium", tellurium)

    class Wrapper(TelluriumSBMLBioModule):
        _OBSERVABLES = ["raw_x", "raw_y"]
        _STATE_OUTPUT_ALIASES = {"raw_x": "x", "raw_y": "y"}
        _STATE_OUTPUT_AS_PAYLOAD = True
        _SPECIES_LABELS = {"raw_x": "Readable X", "raw_y": "Readable Y"}
        _SPECIES_LABELS_OUTPUT_AS_PAYLOAD = True
        _PARAMETER_INPUTS = {"p_input": ("p", 2.0, "u", "Parameter p.")}
        _INITIAL_CONDITION_INPUTS = {"x0": ("raw_x", 1.0, "u", "Initial x.")}
        _MULTIPLIER_INPUTS = {"p_multiplier": (["p", "missing"], 1.0, "x", "Scale p.")}
        _ENABLE_PARAMETER_OVERRIDES = True
        _ENABLE_INITIAL_CONDITIONS = True
        _HEADLINE_OUTPUTS = {"mean_x": ("raw_x", "mole", "Mean X.")}
        _HEADLINE_EMIT_UNITS = True

        def visualisation_extra_selections(self):
            return ["aux", "raw_x"]

        def visualisation_aux_schema(self):
            return {"aux": "float"}

        def visualisation_aux_payload(self, t, latest):
            return {"aux": latest.get("aux", 0.0) + t}

    wrapper = Wrapper(str(model_file), integration_step=0.5)
    specs = wrapper.inputs()
    wrapper.set_inputs(
        {
            "integration_step": ScalarSignal("test", "integration_step", 0.25, 0.0, spec=specs["integration_step"]),
            "p_input": ScalarSignal("test", "p_input", 3.0, 0.0, spec=specs["p_input"]),
            "x0": ScalarSignal("test", "x0", 7.0, 0.0, spec=specs["x0"]),
            "p_multiplier": ScalarSignal("test", "p_multiplier", 10.0, 0.0, spec=specs["p_multiplier"]),
            "parameter_overrides": RecordSignal(
                "test",
                "parameter_overrides",
                {"payload": {"p": 5.0, "bad": "nan"}},
                0.0,
                spec=specs["parameter_overrides"],
            ),
            "initial_conditions": RecordSignal(
                "test",
                "initial_conditions",
                {"payload": {"raw_x": 9.0}},
                0.0,
                spec=specs["initial_conditions"],
            ),
        }
    )

    wrapper.setup()
    wrapper.advance_window(0.0, 1.0)
    wrapper.advance_window(1.0, 0.5)
    outputs = wrapper.get_outputs()

    assert wrapper.integration_step == 0.25
    assert fake_runner["p"] == 5.0
    assert outputs["state"].value["payload"] == {"x": 11.0, "y": 21.0}
    assert outputs["species_labels"].value == {"payload": {"x": "Readable X", "y": "Readable Y"}}
    assert outputs["visualisation_aux"].value == {"aux": 32.0}
    assert outputs["mean_x"].spec.emitted_unit == "mole"
    assert outputs["trajectory"].value["payload"]["series"][0]["name"] == "x"

    wrapper.reset()
    assert fake_runner.reset_called is True
    assert wrapper.get_outputs()["summary"].value["observable_count"] == 2


def test_tellurium_sbml_rule_observable_discovery_and_error_fallbacks(tmp_path) -> None:
    broken = tmp_path / "broken.xml"
    broken.write_text("<not xml", encoding="utf-8")
    assert TelluriumSBMLBioModule(str(broken))._discover_observables_from_xml() == ([], {}, {})

    model_file = tmp_path / "rules.xml"
    model_file.write_text(
        """<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"><model>
        <listOfParameters><parameter id="x" name="Readable X"/><parameter id="y" name="Readable Y"/></listOfParameters>
        <listOfRules><rateRule variable="x"/><assignmentRule variable="y"/></listOfRules>
        </model></sbml>""",
        encoding="utf-8",
    )

    class RuleWrapper(TelluriumSBMLBioModule):
        _OBSERVABLE_STRATEGY = "rules"

    wrapper = RuleWrapper(str(model_file))
    observables, units, display = wrapper._discover_observables_from_xml()

    assert observables == ["x"]
    assert units == {"x": None}
    assert display == {"x": "Readable X"}

    assignment_file = tmp_path / "assignment.xml"
    assignment_file.write_text(
        """<sbml xmlns="http://www.sbml.org/sbml/level3/version1/core"><model>
        <listOfParameters><parameter id="y" name="Readable Y"/></listOfParameters>
        <listOfRules><assignmentRule variable="y"/></listOfRules>
        </model></sbml>""",
        encoding="utf-8",
    )
    assignment = RuleWrapper(str(assignment_file))
    assert assignment._discover_observables_from_xml()[0] == ["y"]
