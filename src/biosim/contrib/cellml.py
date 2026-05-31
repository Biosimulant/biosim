# SPDX-FileCopyrightText: 2025-present Demi <bjaiye1@gmail.com>
#
# SPDX-License-Identifier: MIT
"""Optional libCellML-backed CellML BioModule base classes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import types
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


CELLML_ADAPTER_VERSION = "4"

ParameterInput = tuple[str, float, str, str]
HeadlineOutput = tuple[str, str, str]


class CellMLRuntimeError(RuntimeError):
    """Raised when a CellML model cannot be prepared or simulated."""


def _optional_import_error(package: str, extra: str = "cellml") -> CellMLRuntimeError:
    return CellMLRuntimeError(
        f"Optional dependency '{package}' is required for CellML simulation. "
        f"Install it with: pip install 'biosimulant[{extra}]'."
    )


def _issue_level(issue: Any) -> int | None:
    level = getattr(issue, "level", None)
    if callable(level):
        try:
            return int(level())
        except (TypeError, ValueError, RuntimeError):
            return None
    return None


def _call_issues(item: Any, *, fatal_only: bool = False) -> list[str]:
    """Return readable issues from a libCellML object when available."""

    issues: list[str] = []
    count = 0
    for attr in ("issueCount", "errorCount"):
        method = getattr(item, attr, None)
        if callable(method):
            try:
                count = int(method())
                break
            except (TypeError, ValueError, RuntimeError):
                count = 0
    issue_method = getattr(item, "issue", None)
    for index in range(count):
        try:
            issue = issue_method(index) if callable(issue_method) else None
        except (TypeError, RuntimeError):
            issue = None
        if issue is None:
            issues.append(f"issue {index}")
            continue
        if fatal_only:
            level = _issue_level(issue)
            if level is not None and level != 0:
                continue
        description = getattr(issue, "description", None)
        if callable(description):
            try:
                issues.append(str(description()))
                continue
            except (TypeError, RuntimeError):
                pass
        issues.append(str(issue))
    return issues


def _raise_on_issues(stage: str, item: Any) -> None:
    issues = _call_issues(item, fatal_only=True)
    if issues:
        raise CellMLRuntimeError(f"CellML {stage} failed: " + "; ".join(issues))


def _cache_root() -> Path:
    base = os.environ.get("BIOSIM_CELLML_CACHE")
    if base:
        return Path(base).expanduser()
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg).expanduser() / "biosim" / "cellml"
    return Path.home() / ".cache" / "biosim" / "cellml"


def cellml_cache_key(cellml_text: str, *, libcellml_version: str = "unknown") -> str:
    """Return the deterministic generated-code cache key for a CellML model."""

    payload = {
        "adapter": CELLML_ADAPTER_VERSION,
        "cellml_sha256": hashlib.sha256(cellml_text.encode("utf-8")).hexdigest(),
        "libcellml": str(libcellml_version),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _strip_legacy_metadata_ids(cellml_text: str) -> str:
    """Remove XML metadata IDs that do not affect CellML simulation semantics.

    Several legacy PMR/CellML 1.x artifacts contain malformed, duplicate, or
    namespace-unbound XML ID attributes on MathML/CellML elements. libCellML
    validates those strictly before code generation, but generated ODE dynamics
    use CellML names and MathML expressions rather than XML metadata IDs.
    """

    return re.sub(r"\s+(?:cmeta:)?id=(['\"]).*?\1", "", cellml_text)


def _normalise_root_model_name(cellml_text: str) -> str:
    def replace_name(match: re.Match[str]) -> str:
        name = match.group("name")
        normalised = re.sub(r"[^A-Za-z0-9_]", "_", name)
        if not normalised or normalised[0].isdigit():
            normalised = f"_{normalised}"
        return f"{match.group('prefix')}name={match.group('quote')}{normalised}{match.group('quote')}"

    return re.sub(
        r"(?P<prefix><(?:[A-Za-z_][\w.-]*:)?model\b[^>]*?\s)name=(?P<quote>['\"])(?P<name>.*?)(?P=quote)",
        replace_name,
        cellml_text,
        count=1,
    )


def normalise_cellml_for_codegen(cellml_text: str) -> str:
    """Apply semantics-preserving compatibility fixes before libCellML codegen.

    Legacy CellML 1.x models commonly initialise the variable of integration
    with ``initial_value="0"``. libCellML analysis rejects that because the
    simulation start time supplies the VOI value. Removing a zero VOI initial
    value preserves model dynamics while allowing generated ODE code.
    """

    cellml_text = _strip_legacy_metadata_ids(cellml_text)
    cellml_text = _normalise_root_model_name(cellml_text)
    try:
        root = ET.fromstring(cellml_text)
    except ET.ParseError:
        return cellml_text
    namespace = root.tag.rsplit("}", 1)[0][1:] if root.tag.startswith("{") else ""
    if not namespace:
        return cellml_text
    def local_name(element: ET.Element) -> str:
        return element.tag.rsplit("}", 1)[-1]

    voi_names: set[str] = set()
    for apply in root.iter():
        if local_name(apply) != "apply":
            continue
        if not any(local_name(child) == "diff" for child in apply):
            continue
        for child in apply:
            if local_name(child) != "bvar":
                continue
            for item in child.iter():
                if local_name(item) == "ci" and (item.text or "").strip():
                    voi_names.add((item.text or "").strip())
    if not voi_names:
        return cellml_text
    def remove_zero_initial(match: re.Match[str]) -> str:
        tag = match.group(0)
        name_match = re.search(r'\bname=(["\'])(.*?)\1', tag)
        if name_match is None or name_match.group(2) not in voi_names:
            return tag
        initial_match = re.search(r'\s+initial_value=(["\'])(.*?)\1', tag)
        if initial_match is None:
            return tag
        try:
            is_zero = float(initial_match.group(2)) == 0.0
        except ValueError:
            is_zero = False
        if not is_zero:
            return tag
        return tag[: initial_match.start()] + tag[initial_match.end() :]

    return re.sub(r"<(?:[A-Za-z_][\w.-]*:)?variable\b[^>]*?/?>", remove_zero_initial, cellml_text)


def _load_generated_module(path: Path, module_name: str) -> Any:
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise CellMLRuntimeError(f"Could not load generated CellML code from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        _ensure_nlasolver_module()
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - generated model failures need context.
        raise CellMLRuntimeError(f"Generated CellML code failed to import: {exc}") from exc
    return module


def _ensure_nlasolver_module() -> None:
    """Provide the nonlinear solver expected by libCellML Python codegen.

    libCellML emits ``from nlasolver import nla_solve`` for generated models
    with algebraic systems. The reference helper is not packaged with the
    generated module, so Biosimulant supplies a tiny SciPy-backed equivalent.
    """

    if "nlasolver" in sys.modules:
        return
    module = types.ModuleType("nlasolver")

    def nla_solve(objective: Any, u: Any, n: int, data: Any) -> list[float]:
        try:
            from scipy.optimize import root
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency.
            raise _optional_import_error("scipy") from exc

        size = int(n)
        guess: list[float] = []
        for index in range(size):
            value = float(u[index])
            guess.append(value if math.isfinite(value) else 0.0)

        def residual(candidate: Any) -> list[float]:
            values = [float(candidate[index]) for index in range(size)]
            equations = [0.0] * size
            objective(values, equations, data)
            return equations

        result = root(residual, guess)
        if not getattr(result, "success", False):
            message = getattr(result, "message", "unknown nonlinear solve failure")
            raise CellMLRuntimeError(f"CellML nonlinear solve failed: {message}")
        solution = getattr(result, "x", result)
        return [float(solution[index]) for index in range(size)]

    module.nla_solve = nla_solve
    sys.modules["nlasolver"] = module


def _normalise_generated_python_code(implementation: str) -> str:
    """Repair known libCellML Python-profile numeric literal formatting."""

    return re.sub(r"(?<![\w.])(\d+(?:\.\d+)?[eE][+-]?\d+)\.0(?![\w.])", r"\1", implementation)


def _find_callable(module: Any, *names: str) -> Any:
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn
    return None


def _to_list(value: Any) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "tolist"):
        value = value.tolist()
    return [float(item) for item in list(value)]


class GeneratedCellMLModel:
    """Adapter around libCellML-generated Python modules."""

    def __init__(self, module: Any) -> None:
        self.module = module
        self.state_info = list(getattr(module, "STATE_INFO", []))
        self.variable_info = list(getattr(module, "VARIABLE_INFO", []))
        self.state_count = int(getattr(module, "STATE_COUNT", len(self.state_info)))
        self.variable_count = int(getattr(module, "VARIABLE_COUNT", len(self.variable_info)))
        self.create_states = _find_callable(module, "create_states_array", "createStatesArray")
        self.create_variables = _find_callable(module, "create_variables_array", "createVariablesArray")
        self.initialise = _find_callable(
            module,
            "initialise_states_and_constants",
            "initialiseStatesAndConstants",
            "initialise_variables",
            "initialiseVariables",
        )
        self.compute_constants = _find_callable(module, "compute_computed_constants", "computeComputedConstants")
        self.compute_rates = _find_callable(module, "compute_rates", "computeRates")
        self.compute_variables = _find_callable(module, "compute_variables", "computeVariables")
        missing = [
            name
            for name, fn in (
                ("initialise_states_and_constants or initialise_variables", self.initialise),
                ("compute_rates", self.compute_rates),
                ("compute_variables", self.compute_variables),
            )
            if fn is None
        ]
        if missing:
            raise CellMLRuntimeError("Generated CellML code is missing required functions: " + ", ".join(missing))

    @staticmethod
    def _item_name(item: Any, fallback: str) -> str:
        if isinstance(item, Mapping):
            return str(item.get("name") or fallback)
        return str(getattr(item, "name", fallback))

    @staticmethod
    def _item_units(item: Any) -> str:
        if isinstance(item, Mapping):
            return str(item.get("units") or "")
        return str(getattr(item, "units", ""))

    @staticmethod
    def _item_component(item: Any) -> str:
        if isinstance(item, Mapping):
            return str(item.get("component") or "")
        return str(getattr(item, "component", ""))

    def state_names(self) -> list[str]:
        return [self._item_name(item, f"state_{index}") for index, item in enumerate(self.state_info)]

    def variable_names(self) -> list[str]:
        return [self._item_name(item, f"variable_{index}") for index, item in enumerate(self.variable_info)]

    def labels(self) -> dict[str, str]:
        labels: dict[str, str] = {}
        for name, item in zip(self.state_names(), self.state_info):
            component = self._item_component(item)
            labels[name] = f"{component}.{name}" if component else name
        for name, item in zip(self.variable_names(), self.variable_info):
            component = self._item_component(item)
            labels[name] = f"{component}.{name}" if component else name
        return labels

    def units(self) -> dict[str, str]:
        units: dict[str, str] = {}
        for name, item in zip(self.state_names(), self.state_info):
            units[name] = self._item_units(item)
        for name, item in zip(self.variable_names(), self.variable_info):
            units[name] = self._item_units(item)
        return units

    def initialise_state(self) -> tuple[list[float], list[float], list[float]]:
        states = self.create_states() if self.create_states else [0.0] * self.state_count
        rates = self.create_states() if self.create_states else [0.0] * self.state_count
        variables = self.create_variables() if self.create_variables else [0.0] * self.variable_count
        try:
            self.initialise(states, rates, variables)
        except TypeError:
            self.initialise(states, variables)
        if self.compute_constants is not None:
            self.compute_constants(variables)
        self.compute_rates(0.0, states, rates, variables)
        self.compute_variables(0.0, states, rates, variables)
        return _to_list(states), _to_list(rates), _to_list(variables)

    def rates(self, t: float, states: list[float], variables: list[float]) -> list[float]:
        rates = [0.0] * self.state_count
        self.compute_rates(float(t), states, rates, variables)
        return _to_list(rates)

    def variables_at(self, t: float, states: list[float], variables: list[float]) -> list[float]:
        rates = self.rates(t, states, variables)
        self.compute_variables(float(t), states, rates, variables)
        return _to_list(variables)


def _default_generated_module_name(cache_key: str) -> str:
    return f"_biosim_cellml_{cache_key[:24]}"


class LibCellMLBioModule(StatefulBioModule):
    """Base class for generated libCellML-backed CellML wrappers."""

    _CELLML_ID = ""
    _TITLE = "libCellML CellML Model"
    _PARAMETER_INPUTS: Mapping[str, ParameterInput] = {}
    _INITIAL_CONDITION_INPUTS: Mapping[str, ParameterInput] = {}
    _HEADLINE_OUTPUTS: Mapping[str, HeadlineOutput] = {}
    _TIME_UNIT = "s"
    _HEADLINE_WINDOW_S = 60.0
    _BIOSIM_SUBCLASS_FILE: str | None = None
    _OBSERVABLES: list[str] | None = None
    _MAX_DEFAULT_OBSERVABLES = 64
    _STATE_OUTPUT_ALIASES: Mapping[str, str] = {}
    _STATE_OUTPUT_NAME = "state"
    _SUMMARY_OUTPUT_NAME = "summary"
    _TRAJECTORY_OUTPUT_NAME = "trajectory"
    _VARIABLE_LABELS_OUTPUT_NAME = "variable_labels"
    _EMIT_VARIABLE_LABELS = True
    _EXPOSE_INTEGRATION_STEP_INPUT = True
    _ENABLE_PARAMETER_OVERRIDES = False
    _ENABLE_INITIAL_CONDITIONS = False
    _TIME_ROW_KEY = "t"

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

    def __init__(
        self,
        model_path: str,
        integration_step: float = 1.0,
        *,
        generated_module: Any | None = None,
        solver: Any | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        super().__init__(integration_step=integration_step)
        subclass_module = sys.modules.get(self.__class__.__module__)
        subclass_file = getattr(subclass_module, "__file__", None) or self._BIOSIM_SUBCLASS_FILE
        base_dir = Path(subclass_file).resolve().parent.parent if subclass_file else Path.cwd()
        self._model_path = (base_dir / model_path).resolve()
        self._generated_module_override = generated_module
        self._solver_override = solver
        self._cache_dir = Path(cache_dir).expanduser() if cache_dir is not None else _cache_root()
        self._generated: GeneratedCellMLModel | None = None
        self._states: list[float] = []
        self._rates: list[float] = []
        self._variables: list[float] = []
        self._observables: list[str] = list(self._OBSERVABLES or [])
        self._state_names: list[str] = []
        self._variable_names: list[str] = []
        self._variable_labels: dict[str, str] = {}
        self._variable_units: dict[str, str] = {}
        self._history: list[dict[str, float]] = []
        self._time = 0.0

    def setup(self, config: Optional[dict[str, Any]] = None) -> None:
        module = self._generated_module_override or self._prepare_generated_module()
        self._generated = GeneratedCellMLModel(module)
        self._state_names = self._generated.state_names()
        self._variable_names = self._generated.variable_names()
        self._variable_labels = self._generated.labels()
        self._variable_units = self._generated.units()
        self._states, self._rates, self._variables = self._generated.initialise_state()
        self._observables = self._select_observables()
        self.apply_overrides(reset_initial_state=True)
        self._time = 0.0
        self._history = [self._current_row(0.0)]
        self.publish_outputs(0.0)

    def reset(self) -> None:
        self._time = 0.0
        self._history = []
        self.clear_outputs()
        if self._generated is not None:
            self._states, self._rates, self._variables = self._generated.initialise_state()
            self.apply_overrides(reset_initial_state=True)
            self._history = [self._current_row(0.0)]
            self.publish_outputs(0.0)

    def inputs(self) -> dict[str, SignalSpec]:
        specs: dict[str, SignalSpec] = {}
        if self._EXPOSE_INTEGRATION_STEP_INPUT:
            specs["integration_step"] = scalar_or_record_input(
                self._TIME_UNIT,
                "Output sampling step for the CellML simulator.",
            )
        for name, (_cellml, _default, units, description) in self._PARAMETER_INPUTS.items():
            specs[name] = scalar_or_record_input(units, description)
        for name, (_cellml, _default, units, description) in self._INITIAL_CONDITION_INPUTS.items():
            specs[name] = scalar_or_record_input(units, description)
        if self._ENABLE_PARAMETER_OVERRIDES:
            specs["parameter_overrides"] = SignalSpec.record(
                schema={"payload": "json"},
                accepted_profiles=(
                    AcceptedSignalProfile(signal_type="record", schema={"payload": "json"}),
                ),
                description="Map of generated CellML variable or state name to override value.",
            )
        if self._ENABLE_INITIAL_CONDITIONS:
            specs["initial_conditions"] = SignalSpec.record(
                schema={"payload": "json"},
                accepted_profiles=(
                    AcceptedSignalProfile(signal_type="record", schema={"payload": "json"}),
                ),
                description="Map of generated CellML state name to initial value override.",
            )
        return specs

    def outputs(self) -> dict[str, SignalSpec]:
        state_names = [self._public_observable_name(name) for name in self._observables]
        state_schema = {name: "float" for name in state_names} or {"payload": "json"}
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
                description="Latest value of selected CellML state and algebraic observables.",
            ),
            self._SUMMARY_OUTPUT_NAME: SignalSpec.record(
                schema=summary_schema,
                description="Final, peak, and largest-change diagnostics for selected CellML observables.",
            ),
            self._TRAJECTORY_OUTPUT_NAME: SignalSpec.record(
                schema={"payload": "json"},
                description="Source-faithful time trajectory for selected CellML observables from the current run.",
            ),
        }
        if self._EMIT_VARIABLE_LABELS:
            specs[self._VARIABLE_LABELS_OUTPUT_NAME] = SignalSpec.record(
                schema={self._public_observable_name(name): "str" for name in self._observables} or {"payload": "json"},
                description="Static map of public observable key to CellML component and variable label.",
            )
        for name, (_src, units, description) in self._HEADLINE_OUTPUTS.items():
            specs[name] = SignalSpec.scalar(dtype="float64", emitted_unit=units, description=description + f" Units: {units}.")
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
        if self._generated is None:
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
            self._history.append(self._current_row(target))
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
        trajectory_output_name = self._TRAJECTORY_OUTPUT_NAME
        outputs: dict[str, BioSignal] = {
            state_output_name: RecordSignal(
                source=source,
                name=state_output_name,
                value=self._public_state_values(latest),
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
            trajectory_output_name: RecordSignal(
                source=source,
                name=trajectory_output_name,
                value={"payload": self._public_trajectory()},
                emitted_at=float(t),
                spec=specs[trajectory_output_name],
            ),
        }
        if self._EMIT_VARIABLE_LABELS and self._VARIABLE_LABELS_OUTPUT_NAME in specs:
            outputs[self._VARIABLE_LABELS_OUTPUT_NAME] = RecordSignal(
                source=source,
                name=self._VARIABLE_LABELS_OUTPUT_NAME,
                value=self._public_variable_labels(),
                emitted_at=float(t),
                spec=specs[self._VARIABLE_LABELS_OUTPUT_NAME],
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
        if self._generated is None:
            return
        for input_name, (cellml_name, _default, _units, _description) in self._PARAMETER_INPUTS.items():
            signal = self._input_overrides.get(input_name)
            number = coerce_float(unwrap_payload(signal), keys=("value", "payload")) if signal is not None else None
            if number is not None:
                self._set_variable_value(cellml_name, number, allow_state=False)
        apply_initials = reset_initial_state or self._time <= 0.0
        if apply_initials:
            for input_name, (cellml_name, _default, _units, _description) in self._INITIAL_CONDITION_INPUTS.items():
                signal = self._input_overrides.get(input_name)
                number = coerce_float(unwrap_payload(signal), keys=("value", "payload")) if signal is not None else None
                if number is not None:
                    self._set_variable_value(cellml_name, number, allow_state=True)
        if self._ENABLE_PARAMETER_OVERRIDES:
            signal = self._input_overrides.get("parameter_overrides")
            value = unwrap_payload(signal) if signal is not None else None
            if isinstance(value, Mapping):
                for cellml_name, raw in value.items():
                    number = coerce_float(raw, keys=("value", "payload"))
                    if number is not None:
                        self._set_variable_value(str(cellml_name), number, allow_state=False)
        if apply_initials and self._ENABLE_INITIAL_CONDITIONS:
            signal = self._input_overrides.get("initial_conditions")
            value = unwrap_payload(signal) if signal is not None else None
            if isinstance(value, Mapping):
                for cellml_name, raw in value.items():
                    number = coerce_float(raw, keys=("value", "payload"))
                    if number is not None:
                        self._set_variable_value(str(cellml_name), number, allow_state=True)
        if self._generated is not None:
            self._variables = self._generated.variables_at(self._time, self._states, self._variables)
            if self._history and self._time <= 0.0:
                self._history = [self._current_row(0.0)]

    def _prepare_generated_module(self) -> Any:
        try:
            import libcellml
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency.
            raise _optional_import_error("libcellml") from exc

        cellml_text = self._model_path.read_text(encoding="utf-8")
        version_string = getattr(libcellml, "versionString", None)
        libcellml_version = str(version_string() if callable(version_string) else getattr(libcellml, "__version__", "unknown"))
        cache_key = cellml_cache_key(cellml_text, libcellml_version=libcellml_version)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path = self._cache_dir / f"{cache_key}.py"
        if not cache_path.exists():
            implementation = self._generate_python_code(libcellml, cellml_text)
            cache_path.write_text(implementation, encoding="utf-8")
        return _load_generated_module(cache_path, _default_generated_module_name(cache_key))

    def _generate_python_code(self, libcellml: Any, cellml_text: str) -> str:
        parser = libcellml.Parser()
        set_strict = getattr(parser, "setStrict", None)
        if callable(set_strict):
            set_strict(False)
        model = parser.parseModel(normalise_cellml_for_codegen(cellml_text))
        _raise_on_issues("parse", parser)

        importer_cls = getattr(libcellml, "Importer", None)
        if importer_cls is not None:
            importer = importer_cls()
            importer_set_strict = getattr(importer, "setStrict", None)
            if callable(importer_set_strict):
                importer_set_strict(False)
            resolve = getattr(importer, "resolveImports", None)
            flatten = getattr(importer, "flattenModel", None)
            if callable(resolve):
                resolve(model, str(self._model_path.parent))
                _raise_on_issues("import resolution", importer)
            if callable(flatten):
                model = flatten(model)
                _raise_on_issues("import flattening", importer)

        validator = libcellml.Validator()
        validator.validateModel(model)
        _raise_on_issues("validation", validator)

        analyser = libcellml.Analyser()
        analyser.analyseModel(model)
        _raise_on_issues("analysis", analyser)

        generator = libcellml.Generator()
        profile = libcellml.GeneratorProfile(libcellml.GeneratorProfile.Profile.PYTHON)
        generator.setProfile(profile)
        process = getattr(generator, "processModel", None)
        analyser_model = analyser.model()
        if callable(process):
            process(analyser_model)
        else:
            generator.setModel(analyser_model)
        _raise_on_issues("code generation", generator)
        implementation = generator.implementationCode()
        if not implementation:
            raise CellMLRuntimeError("CellML code generation produced no Python implementation.")
        return _normalise_generated_python_code(str(implementation))

    def _select_observables(self) -> list[str]:
        available = [*self._state_names, *self._variable_names]
        if self._OBSERVABLES is not None:
            return [name for name in self._OBSERVABLES if name in available]
        if self._state_names:
            return self._state_names[: self._MAX_DEFAULT_OBSERVABLES]
        return self._variable_names[: self._MAX_DEFAULT_OBSERVABLES]

    def _set_variable_value(self, name: str, value: float, *, allow_state: bool) -> None:
        if allow_state and name in self._state_names:
            self._states[self._state_names.index(name)] = float(value)
            return
        if name in self._variable_names:
            self._variables[self._variable_names.index(name)] = float(value)

    def _value_for_name(self, name: str, row: Mapping[str, float] | None = None) -> float:
        if row is not None:
            row_key = self._row_key(name)
            if row_key in row:
                return float(row[row_key])
            if name in row:
                return float(row[name])
        if name in self._state_names:
            return float(self._states[self._state_names.index(name)])
        if name in self._variable_names:
            return float(self._variables[self._variable_names.index(name)])
        return 0.0

    def _row_key(self, source_name: str) -> str:
        if source_name == self._TIME_ROW_KEY:
            return f"cellml:{source_name}"
        return source_name

    def _simulate_window(self, start: float, end: float) -> list[dict[str, float]]:
        if self._generated is None:
            return []
        if self._solver_override is not None:
            solver = self._solver_override
        else:
            try:
                from scipy.integrate import solve_ivp
            except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency.
                raise _optional_import_error("scipy") from exc
            solver = solve_ivp
        n_steps = max(2, int(math.ceil((end - start) / self.integration_step)) + 1)
        t_eval = [start + (end - start) * i / (n_steps - 1) for i in range(n_steps)]

        def rhs(t: float, y: Any) -> list[float]:
            states = _to_list(y)
            return self._generated.rates(float(t), states, list(self._variables))

        result = solver(rhs, (float(start), float(end)), list(self._states), t_eval=t_eval)
        if not getattr(result, "success", False):
            message = getattr(result, "message", "unknown solver failure")
            raise CellMLRuntimeError(f"CellML solver failed: {message}")

        y_values = getattr(result, "y", [])
        times = _to_list(getattr(result, "t", t_eval))
        rows: list[dict[str, float]] = []
        for col, t in enumerate(times):
            if rows and abs(t - rows[-1]["t"]) < 1e-12:
                continue
            if self._history and col == 0 and abs(t - self._history[-1]["t"]) < 1e-12:
                continue
            states = [float(y_values[index][col]) for index in range(len(self._states))]
            variables = self._generated.variables_at(float(t), states, list(self._variables))
            row = self._row_from_values(float(t), states, variables)
            rows.append(row)
        if rows:
            self._states = [self._value_for_name(name, rows[-1]) for name in self._state_names]
            self._variables = self._generated.variables_at(float(rows[-1]["t"]), self._states, self._variables)
        return rows

    def _row_from_values(self, t: float, states: list[float], variables: list[float]) -> dict[str, float]:
        row = {"t": float(t)}
        for name, value in zip(self._state_names, states):
            row[self._row_key(name)] = float(value)
        for name, value in zip(self._variable_names, variables):
            row[self._row_key(name)] = float(value)
        return row

    def _current_row(self, t: float) -> dict[str, float]:
        if self._generated is not None:
            self._variables = self._generated.variables_at(float(t), self._states, self._variables)
        return self._row_from_values(float(t), self._states, self._variables)

    def _public_observable_name(self, raw_name: str) -> str:
        return str(self._STATE_OUTPUT_ALIASES.get(raw_name, raw_name))

    def _public_state_values(self, latest: Mapping[str, float]) -> dict[str, float]:
        return {self._public_observable_name(name): self._value_for_name(name, latest) for name in self._observables}

    def _public_trajectory(self) -> dict[str, Any]:
        series = []
        for raw_name in self._observables:
            public_name = self._public_observable_name(raw_name)
            points = []
            for row in self._history:
                value = self._value_for_name(raw_name, row)
                if math.isfinite(value):
                    points.append([float(row.get("t", 0.0)), float(value)])
            if len(points) >= 2:
                series.append({"name": public_name, "source": raw_name, "points": points})
        return {
            "time_unit": self._TIME_UNIT,
            "series": series,
        }

    def _public_variable_labels(self) -> dict[str, str]:
        return {
            self._public_observable_name(name): self._variable_labels.get(name, name)
            for name in self._observables
        }

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
        changes = {
            name: abs(self._value_for_name(name, last) - self._value_for_name(name, first))
            for name in self._observables
        }
        biggest_change = max(changes, key=changes.get)
        peaks = {name: max(self._value_for_name(name, point) for point in self._history) for name in self._observables}
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
        row_key = self._row_key(source_id)
        values = [
            row[row_key]
            for row in self._history
            if row_key in row and float(row.get("t", 0.0)) >= window_start
        ]
        if values:
            return sum(values) / len(values)
        return self._value_for_name(source_id, latest)
