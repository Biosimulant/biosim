"""Optional Tellurium-backed SBML BioModule base classes."""

from __future__ import annotations

import math
from pathlib import Path
import sys
from typing import Any, Mapping, Optional
import xml.etree.ElementTree as ET

from biosim.modules import StatefulBioModule
from biosim.signals import (
    AcceptedSignalProfile,
    BioSignal,
    RecordSignal,
    ScalarSignal,
    SignalSpec,
    coerce_float,
    scalar_or_record_input,
    unwrap_payload,
)


ParameterInput = tuple[str, float, str, str]
MultiplierInput = tuple[list[str], float, str, str]
HeadlineOutput = tuple[str, str, str]


def read_sbml_text(path: Path) -> str:
    """Read SBML XML with a conservative fallback for legacy BioModels files."""

    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def patch_uninitialised_parameters(xml_text: str) -> tuple[str, list[tuple[str, str]]]:
    """Repair SBML parameters without initial values before Tellurium loads them."""

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return xml_text, []

    if "}" not in root.tag:
        return xml_text, []
    sbml_ns = root.tag.split("}", 1)[0].lstrip("{")
    mathml_ns = "http://www.w3.org/1998/Math/MathML"

    model_el = next((child for child in root if child.tag.endswith("}model")), None)
    if model_el is None:
        return xml_text, []

    def by_local(parent: ET.Element, local_name: str) -> list[ET.Element]:
        suffix = "}" + local_name
        return [element for element in parent.iter() if element.tag.endswith(suffix)]

    determined: set[str] = set()
    for tag in ("assignmentRule", "rateRule"):
        for element in by_local(model_el, tag):
            variable = element.attrib.get("variable")
            if variable:
                determined.add(variable)
    for element in by_local(model_el, "initialAssignment"):
        symbol = element.attrib.get("symbol")
        if symbol:
            determined.add(symbol)

    list_of_rules = next((child for child in model_el if child.tag.endswith("}listOfRules")), None)
    patches: list[tuple[str, str]] = []
    for param_el in by_local(model_el, "parameter"):
        param_id = param_el.attrib.get("id")
        if not param_id or "value" in param_el.attrib or param_id in determined:
            continue
        name_attr = param_el.attrib.get("name", "")
        looks_like_time = (
            name_attr.lower() == "time"
            or param_id == "t"
            or param_id.lower().startswith("time")
        )
        if looks_like_time:
            if list_of_rules is None:
                list_of_rules = ET.SubElement(model_el, "{" + sbml_ns + "}listOfRules")
            rule = ET.SubElement(list_of_rules, "{" + sbml_ns + "}assignmentRule", {"variable": param_id})
            math_el = ET.SubElement(rule, "{" + mathml_ns + "}math")
            csym = ET.SubElement(
                math_el,
                "{" + mathml_ns + "}csymbol",
                {"encoding": "text", "definitionURL": "http://www.sbml.org/sbml/symbols/time"},
            )
            csym.text = "t"
            patches.append((param_id, "assignmentRule->symbolic time"))
        else:
            param_el.set("value", "0")
            patches.append((param_id, "value=0"))

    if not patches:
        return xml_text, []

    ET.register_namespace("", sbml_ns)
    ET.register_namespace("math", mathml_ns)
    return ET.tostring(root, encoding="unicode"), patches


class TelluriumSBMLBioModule(StatefulBioModule):
    """Base class for generated Tellurium-backed SBML wrappers.

    Subclasses declare only metadata: SBML path/id/title, exposed parameters,
    headline outputs, observable strategy, and optional visualization payload
    mapping. Tellurium is imported lazily from ``setup()``.
    """

    _SBML_ID = ""
    _TITLE = "Tellurium SBML Model"
    _PARAMETER_INPUTS: Mapping[str, ParameterInput] = {}
    _INITIAL_CONDITION_INPUTS: Mapping[str, ParameterInput] = {}
    _MULTIPLIER_INPUTS: Mapping[str, MultiplierInput] = {}
    _HEADLINE_OUTPUTS: Mapping[str, HeadlineOutput] = {}
    _TIME_UNIT = "s"
    _HEADLINE_WINDOW_S = 60.0
    _OBSERVABLE_STRATEGY = "species"
    _NON_BIOLOGICAL_OBSERVABLES: set[str] = {"dummy"}
    _HEADLINE_EMIT_UNITS = False
    _BIOSIM_SUBCLASS_FILE: str | None = None
    _OBSERVABLES: list[str] | None = None
    _SPECIES_LABELS: Mapping[str, str] = {}
    _STATE_OUTPUT_ALIASES: Mapping[str, str] = {}
    _ENABLE_PARAMETER_OVERRIDES = False
    _ENABLE_INITIAL_CONDITIONS = False
    _STATE_OUTPUT_AS_PAYLOAD = False
    _SPECIES_LABELS_OUTPUT_AS_PAYLOAD = False
    _EXPOSE_INTEGRATION_STEP_INPUT = True
    _STATE_OUTPUT_NAME = "state"
    _SUMMARY_OUTPUT_NAME = "summary"
    _SPECIES_LABELS_OUTPUT_NAME = "species_labels"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        for depth in range(1, 12):
            try:
                frame = sys._getframe(depth)
            except ValueError:
                break
            if frame.f_globals.get("__name__") != cls.__module__:
                continue
            subclass_file = frame.f_globals.get("__file__")
            if isinstance(subclass_file, str):
                cls._BIOSIM_SUBCLASS_FILE = subclass_file
                break

    def __init__(self, model_path: str, integration_step: float = 1.0) -> None:
        super().__init__(integration_step=integration_step)
        subclass_module = sys.modules.get(self.__class__.__module__)
        subclass_file = getattr(subclass_module, "__file__", None)
        if not subclass_file:
            subclass_file = self._BIOSIM_SUBCLASS_FILE
        base_dir = Path(subclass_file).resolve().parent.parent if subclass_file else Path.cwd()
        self._model_path = (base_dir / model_path).resolve()
        self._runner: Any = None
        self._observables, _, _ = self._discover_observables_from_xml()
        if self._OBSERVABLES is not None:
            self._observables = list(self._OBSERVABLES)
        self._initial_values: dict[str, float] = {}
        self._history: list[dict[str, float]] = []
        self._patches_applied: list[tuple[str, str]] = []
        self._param_baselines: dict[str, float] = {}

    def setup(self, config: Optional[dict[str, Any]] = None) -> None:
        import tellurium as te

        xml_text = read_sbml_text(self._model_path)
        patched_text, self._patches_applied = patch_uninitialised_parameters(xml_text)
        self._runner = te.loadSBMLModel(patched_text if self._patches_applied else str(self._model_path))
        self._capture_multiplier_baselines()
        observables, _, _ = self._discover_observables_from_xml()
        if observables:
            self._observables = observables
        if self._OBSERVABLES is not None:
            self._observables = list(self._OBSERVABLES)
        self.apply_overrides(reset_initial_state=True)
        self._initial_values = self._read_observables()
        self._time = 0.0
        self._history = [{"t": 0.0, **self._initial_values}]
        self.publish_outputs(0.0)

    def reset(self) -> None:
        if self._runner is not None and hasattr(self._runner, "reset"):
            self._runner.reset()
        self._time = 0.0
        self._history = []
        self.clear_outputs()
        if self._runner is not None:
            self._capture_multiplier_baselines()
            self.apply_overrides(reset_initial_state=True)
            self._initial_values = self._read_observables()
            self._history = [{"t": 0.0, **self._initial_values}]
            self.publish_outputs(0.0)

    def inputs(self) -> dict[str, SignalSpec]:
        specs = {}
        if self._EXPOSE_INTEGRATION_STEP_INPUT:
            specs["integration_step"] = scalar_or_record_input(
                self._TIME_UNIT,
                "Output sampling step for the tellurium simulator.",
            )
        for name, (_sbml, _default, units, description) in self._PARAMETER_INPUTS.items():
            specs[name] = scalar_or_record_input(units, description)
        for name, (_sbml, _default, units, description) in self._INITIAL_CONDITION_INPUTS.items():
            specs[name] = scalar_or_record_input(units, description)
        for name, (_targets, _default, units, description) in self._MULTIPLIER_INPUTS.items():
            specs[name] = scalar_or_record_input(units, description)
        if self._ENABLE_PARAMETER_OVERRIDES:
            specs["parameter_overrides"] = SignalSpec.record(
                schema={"payload": "json"},
                accepted_profiles=(
                    AcceptedSignalProfile(signal_type="record", schema={"payload": "json"}),
                ),
                description="Map of SBML global parameter name to override value.",
            )
        if self._ENABLE_INITIAL_CONDITIONS:
            specs["initial_conditions"] = SignalSpec.record(
                schema={"payload": "json"},
                accepted_profiles=(
                    AcceptedSignalProfile(signal_type="record", schema={"payload": "json"}),
                ),
                description="Map of SBML species or state variable ID to initial value override.",
            )
        return specs

    def outputs(self) -> dict[str, SignalSpec]:
        state_names = [self._public_observable_name(name) for name in self._observables]
        state_schema = (
            {"payload": "json"}
            if self._STATE_OUTPUT_AS_PAYLOAD
            else ({name: "float" for name in state_names} or {"payload": "json"})
        )
        summary_schema = {
            "duration_simulated": "float",
            "observable_count": "int",
            "largest_change_observable": "str",
            "largest_change_magnitude": "float",
            "peak_observable": "str",
            "peak_value": "float",
        }
        specs = {
            self._STATE_OUTPUT_NAME: SignalSpec.record(
                schema=state_schema,
                description=f"Latest value of every observable ({self._OBSERVABLE_STRATEGY} variables).",
            ),
            self._SUMMARY_OUTPUT_NAME: SignalSpec.record(
                schema=summary_schema,
                description="Final, peak, and minimum value per observable plus simulated duration.",
            ),
        }
        if self._SPECIES_LABELS:
            specs[self._SPECIES_LABELS_OUTPUT_NAME] = SignalSpec.record(
                schema=(
                    {"payload": "json"}
                    if self._SPECIES_LABELS_OUTPUT_AS_PAYLOAD
                    else {self._public_observable_name(name): "str" for name in self._SPECIES_LABELS}
                ),
                description="Static map of public observable key to human-friendly label.",
            )
        aux_schema = self.visualisation_aux_schema()
        if aux_schema is not None:
            specs["visualisation_aux"] = SignalSpec.record(
                schema=dict(aux_schema),
                description=self.visualisation_aux_description(),
            )
        for name, (_src, units, description) in self._HEADLINE_OUTPUTS.items():
            kwargs: dict[str, Any] = {
                "dtype": "float64",
                "description": description + f" Units: {units}.",
            }
            if self._HEADLINE_EMIT_UNITS:
                kwargs["emitted_unit"] = units
            specs[name] = SignalSpec.scalar(**kwargs)
        return specs

    def set_inputs(self, inputs: dict[str, BioSignal]) -> None:
        self._input_overrides = dict(inputs or {})
        self.apply_overrides(reset_initial_state=False)

    def advance_window(
        self,
        start: float,
        end: float,
        inputs: Optional[dict[str, BioSignal]] = None,
    ) -> None:
        if inputs:
            self.set_inputs(inputs)
        else:
            self.apply_overrides(reset_initial_state=False)

        if self._runner is None:
            self.setup()
            self.apply_overrides(reset_initial_state=False)

        target = float(end)
        if target <= self._time:
            return

        rows = self._simulate_window(self._time, target)
        if rows:
            self._history.extend(rows)
            self._time = float(rows[-1]["t"])
        else:
            self._time = target
        self.publish_outputs(self._time)

    def publish_outputs(self, t: float, payloads: Mapping[str, Any] | None = None) -> None:
        if not self._history:
            self._outputs = {}
            return
        latest = self._history[-1]
        source = self.source_name()
        specs = self.outputs()
        state_output_name = self._STATE_OUTPUT_NAME
        summary_output_name = self._SUMMARY_OUTPUT_NAME
        species_labels_output_name = self._SPECIES_LABELS_OUTPUT_NAME
        outputs: dict[str, BioSignal] = {
            state_output_name: RecordSignal(
                source=source,
                name=state_output_name,
                value=(
                    {"payload": self._public_state_values(latest)}
                    if self._STATE_OUTPUT_AS_PAYLOAD
                    else self._public_state_values(latest)
                ),
                emitted_at=float(t),
                spec=specs[state_output_name],
            ),
            summary_output_name: RecordSignal(
                source=source,
                name=summary_output_name,
                value=self._compute_summary(t),
                emitted_at=float(t),
                spec=specs[summary_output_name],
            ),
        }
        if self._SPECIES_LABELS and species_labels_output_name in specs:
            outputs[species_labels_output_name] = RecordSignal(
                source=source,
                name=species_labels_output_name,
                value=(
                    {"payload": self._public_species_labels()}
                    if self._SPECIES_LABELS_OUTPUT_AS_PAYLOAD
                    else self._public_species_labels()
                ),
                emitted_at=float(t),
                spec=specs[species_labels_output_name],
            )
        aux_payload = self.visualisation_aux_payload(t, latest)
        if aux_payload is not None and "visualisation_aux" in specs:
            outputs["visualisation_aux"] = RecordSignal(
                source=source,
                name="visualisation_aux",
                value=dict(aux_payload),
                emitted_at=float(t),
                spec=specs["visualisation_aux"],
            )
        for output_name, (source_id, _units, _description) in self._HEADLINE_OUTPUTS.items():
            outputs[output_name] = ScalarSignal(
                source=source,
                name=output_name,
                value=float(self._headline_value(source_id, latest, t)),
                emitted_at=float(t),
                spec=specs[output_name],
            )
        self._outputs = outputs

    def apply_overrides(self, *, reset_initial_state: bool = False) -> None:
        signal = self._input_overrides.get("integration_step")
        if signal is not None:
            number = coerce_float(unwrap_payload(signal), keys=("value", "payload"))
            if number is not None and number > 0:
                self.integration_step = number
        if self._runner is None:
            return
        for input_name, (sbml_id, _default, _units, _description) in self._PARAMETER_INPUTS.items():
            signal = self._input_overrides.get(input_name)
            if signal is None:
                continue
            number = coerce_float(unwrap_payload(signal), keys=("value", "payload"))
            if number is None:
                continue
            try:
                self._runner[sbml_id] = float(number)
            except (KeyError, ValueError, TypeError, RuntimeError):
                pass
        apply_named_initials = reset_initial_state or float(getattr(self, "_time", 0.0)) <= 0.0
        named_initial_applied = False
        if apply_named_initials:
            for input_name, (sbml_id, _default, _units, _description) in self._INITIAL_CONDITION_INPUTS.items():
                signal = self._input_overrides.get(input_name)
                if signal is None:
                    continue
                number = coerce_float(unwrap_payload(signal), keys=("value", "payload"))
                if number is None:
                    continue
                try:
                    self._runner[sbml_id] = float(number)
                    named_initial_applied = True
                except (KeyError, ValueError, TypeError, RuntimeError):
                    pass
        if named_initial_applied and float(getattr(self, "_time", 0.0)) <= 0.0:
            self._initial_values = self._read_observables()
            if self._history:
                self._history = [{"t": 0.0, **self._initial_values}]
        for input_name, (sbml_ids, _default, _units, _description) in self._MULTIPLIER_INPUTS.items():
            signal = self._input_overrides.get(input_name)
            if signal is None:
                continue
            number = coerce_float(unwrap_payload(signal), keys=("value", "payload"))
            if number is None:
                continue
            for sbml_id in sbml_ids:
                base = self._param_baselines.get(sbml_id)
                if base is None:
                    continue
                try:
                    self._runner[sbml_id] = float(base) * float(number)
                except (KeyError, ValueError, TypeError, RuntimeError):
                    pass
        if self._ENABLE_PARAMETER_OVERRIDES:
            signal = self._input_overrides.get("parameter_overrides")
            value = unwrap_payload(signal) if signal is not None else None
            if isinstance(value, Mapping):
                for sbml_id, raw in value.items():
                    number = coerce_float(raw, keys=("value", "payload"))
                    if number is None:
                        continue
                    try:
                        self._runner[str(sbml_id)] = float(number)
                    except (KeyError, ValueError, TypeError, RuntimeError):
                        pass
        if self._ENABLE_INITIAL_CONDITIONS:
            signal = self._input_overrides.get("initial_conditions")
            value = unwrap_payload(signal) if signal is not None else None
            if isinstance(value, Mapping):
                for sbml_id, raw in value.items():
                    number = coerce_float(raw, keys=("value", "payload"))
                    if number is None:
                        continue
                    try:
                        self._runner[str(sbml_id)] = float(number)
                    except (KeyError, ValueError, TypeError, RuntimeError):
                        pass

    def _capture_multiplier_baselines(self) -> None:
        self._param_baselines = {}
        if self._runner is None:
            return
        for sbml_ids, _default, _units, _description in self._MULTIPLIER_INPUTS.values():
            for sbml_id in sbml_ids:
                try:
                    self._param_baselines[sbml_id] = float(self._runner[sbml_id])
                except (KeyError, ValueError, TypeError, RuntimeError):
                    pass

    def _discover_observables_from_xml(self) -> tuple[list[str], dict[str, Optional[str]], dict[str, str]]:
        try:
            tree = ET.parse(self._model_path)
        except (ET.ParseError, OSError):
            return [], {}, {}
        root = tree.getroot()
        ns = root.tag.split("}")[0].strip("{") if "}" in root.tag else None
        if not ns:
            return [], {}, {}

        def is_sbml_element(element: ET.Element, local_name: str) -> bool:
            return element.tag == "{" + ns + "}" + local_name

        observables: list[str] = []
        units: dict[str, Optional[str]] = {}
        display: dict[str, str] = {}
        if self._OBSERVABLE_STRATEGY == "species":
            for element in root.iter():
                if is_sbml_element(element, "species"):
                    species_id = element.attrib.get("id")
                    sbo = element.attrib.get("sboTerm", "")
                    if (
                        species_id
                        and species_id not in self._NON_BIOLOGICAL_OBSERVABLES
                        and sbo != "SBO:0000291"
                    ):
                        observables.append(species_id)
                        units[species_id] = element.attrib.get("substanceUnits") or element.attrib.get("units")
                        sbml_name = element.attrib.get("name")
                        if sbml_name and sbml_name != species_id:
                            display[species_id] = sbml_name
        else:
            param_names: dict[str, str] = {}
            for element in root.iter():
                if is_sbml_element(element, "parameter"):
                    param_id = element.attrib.get("id")
                    param_name = element.attrib.get("name")
                    if param_id and param_name and param_name != param_id:
                        param_names[param_id] = param_name
            for element in root.iter():
                if is_sbml_element(element, "rateRule"):
                    variable = element.attrib.get("variable")
                    if variable and variable not in self._NON_BIOLOGICAL_OBSERVABLES:
                        observables.append(variable)
                        units[variable] = None
                        if variable in param_names:
                            display[variable] = param_names[variable]
            if not observables:
                for element in root.iter():
                    if is_sbml_element(element, "assignmentRule"):
                        variable = element.attrib.get("variable")
                        if variable and variable not in self._NON_BIOLOGICAL_OBSERVABLES:
                            observables.append(variable)
                            units[variable] = None
                            if variable in param_names:
                                display[variable] = param_names[variable]
        return observables, units, display

    def _read_observables(self) -> dict[str, float]:
        values: dict[str, float] = {}
        for name in self._observables:
            try:
                values[name] = float(self._runner[name])
            except (KeyError, ValueError, TypeError, RuntimeError):
                values[name] = 0.0
        return values

    def _public_observable_name(self, raw_name: str) -> str:
        return str(self._STATE_OUTPUT_ALIASES.get(raw_name, raw_name))

    def _public_state_values(self, latest: Mapping[str, float]) -> dict[str, float]:
        return {
            self._public_observable_name(name): latest.get(name, 0.0)
            for name in self._observables
        }

    def _public_species_labels(self) -> dict[str, str]:
        return {
            self._public_observable_name(name): label
            for name, label in self._SPECIES_LABELS.items()
        }

    def visualisation_aux_schema(self) -> Mapping[str, str] | None:
        """Return an optional lab-local visualisation payload schema.

        The generic SBML base does not assume a visualisation contract. Wrappers
        that need private data for a sibling visualisation model can override
        this hook and ``visualisation_aux_payload()`` locally.
        """

        return None

    def visualisation_aux_description(self) -> str:
        return "Internal visualisation payload."

    def visualisation_extra_selections(self) -> list[str]:
        return []

    def visualisation_aux_payload(
        self,
        t: float,
        latest: Mapping[str, float],
    ) -> Mapping[str, Any] | None:
        return None

    def _extra_selections(self) -> list[str]:
        return [item for item in self.visualisation_extra_selections() if item not in self._observables]

    def _simulate_window(self, start: float, end: float) -> list[dict[str, float]]:
        if not self._observables:
            return []
        n_steps = max(2, int(math.ceil((end - start) / self.integration_step)) + 1)
        extra_selections = self._extra_selections()
        selections = ["time", *self._observables, *extra_selections]
        result = self._runner.simulate(start, end, n_steps, selections=selections)
        rows: list[dict[str, float]] = []
        for i in range(result.shape[0]):
            t = float(result[i, 0])
            if rows and abs(t - rows[-1]["t"]) < 1e-12:
                continue
            if self._history and i == 0 and abs(t - self._history[-1]["t"]) < 1e-12:
                continue
            row = {"t": t}
            for j, name in enumerate(self._observables, start=1):
                row[name] = float(result[i, j])
            for k, extra_name in enumerate(extra_selections, start=1 + len(self._observables)):
                row[extra_name] = float(result[i, k])
            rows.append(row)
        return rows

    def _compute_summary(self, t: float) -> dict[str, Any]:
        if not self._observables or len(self._history) < 2:
            return {
                "duration_simulated": float(t),
                "observable_count": len(self._observables),
                "largest_change_observable": "",
                "largest_change_magnitude": 0.0,
                "peak_observable": "",
                "peak_value": 0.0,
            }
        first = self._history[0]
        last = self._history[-1]
        changes = {name: abs(last.get(name, 0.0) - first.get(name, 0.0)) for name in self._observables}
        biggest_change = max(changes, key=changes.get)
        peaks = {name: max(point.get(name, 0.0) for point in self._history) for name in self._observables}
        biggest_peak = max(peaks, key=peaks.get)
        return {
            "duration_simulated": float(t),
            "observable_count": len(self._observables),
            "largest_change_observable": self._public_observable_name(biggest_change),
            "largest_change_magnitude": float(changes[biggest_change]),
            "peak_observable": self._public_observable_name(biggest_peak),
            "peak_value": float(peaks[biggest_peak]),
        }

    def _headline_value(self, source_id: str, latest: Mapping[str, float], t: float) -> float:
        window_start = float(t) - self._HEADLINE_WINDOW_S
        window_values = [
            row[source_id]
            for row in self._history
            if source_id in row and float(row.get("t", 0.0)) >= window_start
        ]
        if window_values:
            return sum(window_values) / len(window_values)
        if self._runner is not None:
            try:
                return float(self._runner[source_id])
            except (KeyError, ValueError, TypeError, RuntimeError):
                return 0.0
        return float(latest.get(source_id, 0.0))
