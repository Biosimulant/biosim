"""Tests for optional SBML contrib helpers."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

from biosim.contrib.sbml import TelluriumSBMLBioModule, patch_uninitialised_parameters


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
