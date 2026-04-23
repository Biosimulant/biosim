"""
Typed signal primitives and port specifications for the BioSim 1.5 kernel.
"""

from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from typing import Any, Literal, Mapping, Optional

try:  # pragma: no cover - optional dependency
    import numpy as _np  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    _np = None

_HAS_NUMPY = bool(_np is not None and hasattr(_np, "asarray") and hasattr(_np, "ndarray"))

SignalType = Literal["scalar", "array", "record", "event"]
SignalKind = Literal["state", "event"]
InterpolationPolicy = Literal["zoh", "linear", "none"]
StalePolicy = Literal["ignore", "warn", "error"]

_NUMERIC_DTYPES = {
    "float16",
    "float32",
    "float64",
    "int8",
    "int16",
    "int32",
    "int64",
    "uint8",
    "uint16",
    "uint32",
    "uint64",
}


def _ensure_json_serializable(value: Any) -> None:
    try:
        json.dumps(value)
    except TypeError as exc:  # pragma: no cover - json gives enough detail
        raise TypeError(f"value is not JSON-serializable: {value!r}") from exc


def _normalize_dtype(dtype: Optional[str]) -> Optional[str]:
    if dtype is None:
        return None
    return str(dtype)


def _coerce_init_args(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[str, str, Any, float, Optional[SignalSpec | Mapping[str, Any]], Any]:
    if len(args) > 4:
        raise TypeError("signals accept at most four positional arguments: source, name, value, emitted_at")
    source = kwargs.pop("source", None)
    if source is None and len(args) > 0:
        source = args[0]
    name = kwargs.pop("name", None)
    if name is None and len(args) > 1:
        name = args[1]
    value = kwargs.pop("value", None)
    if value is None and len(args) > 2:
        value = args[2]
    emitted_at = kwargs.pop("emitted_at", None)
    if emitted_at is None and len(args) > 3:
        emitted_at = args[3]
    spec = kwargs.pop("spec", None)
    if kwargs:
        raise TypeError(f"unexpected signal constructor arguments: {sorted(kwargs)}")
    if source is None or name is None or emitted_at is None:
        raise TypeError("signals require source, name, and emitted_at")
    return str(source), str(name), value, float(emitted_at), spec, None


def _infer_shape(value: Any) -> tuple[int, ...]:
    if isinstance(value, tuple):
        value = list(value)
    if isinstance(value, list):
        if not value:
            return (0,)
        child_shape = _infer_shape(value[0])
        for child in value[1:]:
            if _infer_shape(child) != child_shape:
                raise ValueError("ragged arrays are not supported")
        return (len(value), *child_shape)
    return ()


def _normalize_array_value(value: Any, dtype: Optional[str]) -> Any:
    if _HAS_NUMPY:
        return _np.asarray(value, dtype=dtype)
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        value = list(value)
    if not isinstance(value, list):
        raise TypeError("array signals require list/tuple/ndarray-like values")
    return copy.deepcopy(value)


@dataclass(frozen=True)
class AcceptedSignalProfile:
    """One accepted incoming wire shape for an input port."""

    signal_type: Optional[SignalType] = None
    dtype: Optional[str] = None
    shape: Optional[tuple[int, ...]] = None
    schema: Optional[dict[str, str]] = None
    accepted_units: Optional[tuple[str, ...]] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        shape = self.shape
        if isinstance(shape, list):
            object.__setattr__(self, "shape", tuple(shape))
            shape = self.shape
        if shape is not None and any(dim < 0 for dim in shape):
            raise ValueError("accepted profile shape dimensions must be non-negative")

        object.__setattr__(self, "dtype", _normalize_dtype(self.dtype))

        accepted_units = self.accepted_units
        if isinstance(accepted_units, list):
            object.__setattr__(self, "accepted_units", tuple(str(unit) for unit in accepted_units))
            accepted_units = self.accepted_units
        if accepted_units is not None:
            normalized_units = tuple(str(unit).strip() for unit in accepted_units if str(unit).strip())
            if not normalized_units:
                object.__setattr__(self, "accepted_units", None)
            else:
                if len(set(normalized_units)) != len(normalized_units):
                    raise ValueError("accepted_units must not contain duplicates")
                object.__setattr__(self, "accepted_units", normalized_units)

        if self.signal_type == "scalar" and self.shape not in (None, ()):
            raise ValueError("scalar accepted profiles cannot declare an array shape")
        if self.signal_type == "array" and self.shape is None:
            raise ValueError("array accepted profiles require a shape")
        if self.signal_type == "record":
            if not self.schema:
                raise ValueError("record accepted profiles require a schema")
            if self.shape is not None:
                raise ValueError("record accepted profiles cannot declare shape")
        if self.signal_type == "event" and self.shape is not None:
            raise ValueError("event accepted profiles cannot declare shape")

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "dtype": self.dtype,
            "shape": list(self.shape) if self.shape is not None else None,
            "schema": dict(self.schema) if self.schema is not None else None,
            "accepted_units": list(self.accepted_units) if self.accepted_units is not None else None,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AcceptedSignalProfile":
        return cls(
            signal_type=data.get("signal_type"),
            dtype=data.get("dtype"),
            shape=tuple(data["shape"]) if data.get("shape") is not None else None,
            schema=dict(data["schema"]) if data.get("schema") is not None else None,
            accepted_units=tuple(data["accepted_units"]) if data.get("accepted_units") is not None else None,
            description=data.get("description"),
        )

    def matches_output(self, source: "SignalSpec") -> bool:
        if self.signal_type is not None and source.signal_type != self.signal_type:
            return False
        if self.dtype is not None and source.dtype is not None and source.dtype != self.dtype:
            return False
        if self.shape is not None and source.shape is not None and tuple(source.shape) != tuple(self.shape):
            return False
        if self.schema is not None and source.schema is not None and source.schema != self.schema:
            return False
        if self.accepted_units is not None:
            if source.emitted_unit is None:
                return False
            if source.emitted_unit not in self.accepted_units:
                return False
        return True


@dataclass(frozen=True)
class SignalSpec:
    """Declared contract for a module port."""

    signal_type: SignalType
    kind: SignalKind = "state"
    dtype: Optional[str] = None
    shape: Optional[tuple[int, ...]] = None
    emitted_unit: Optional[str] = None
    accepted_profiles: Optional[tuple[AcceptedSignalProfile, ...]] = None
    interpolation: InterpolationPolicy = "zoh"
    max_age: Optional[float] = None
    stale_policy: StalePolicy = "warn"
    schema: Optional[dict[str, str]] = None
    description: Optional[str] = None

    def __post_init__(self) -> None:
        shape = self.shape
        if isinstance(shape, list):
            object.__setattr__(self, "shape", tuple(shape))
            shape = self.shape
        if shape is not None and any(dim < 0 for dim in shape):
            raise ValueError("shape dimensions must be non-negative")

        accepted_profiles = self.accepted_profiles
        if isinstance(accepted_profiles, list):
            normalized_profiles = tuple(
                AcceptedSignalProfile.from_dict(profile) if isinstance(profile, Mapping) else profile
                for profile in accepted_profiles
            )
            object.__setattr__(self, "accepted_profiles", normalized_profiles)
            accepted_profiles = self.accepted_profiles
        if accepted_profiles is not None:
            if not accepted_profiles:
                object.__setattr__(self, "accepted_profiles", None)
            else:
                normalized_profiles = tuple(
                    AcceptedSignalProfile.from_dict(profile) if isinstance(profile, Mapping) else profile
                    for profile in accepted_profiles
                )
                if not all(isinstance(profile, AcceptedSignalProfile) for profile in normalized_profiles):
                    raise TypeError("accepted_profiles must contain AcceptedSignalProfile entries")
                object.__setattr__(self, "accepted_profiles", normalized_profiles)

        if self.emitted_unit is not None:
            clean_emitted_unit = str(self.emitted_unit).strip()
            if not clean_emitted_unit:
                raise ValueError("emitted_unit must not be empty")
            object.__setattr__(self, "emitted_unit", clean_emitted_unit)

        object.__setattr__(self, "dtype", _normalize_dtype(self.dtype))

        if self.max_age is not None and self.max_age < 0:
            raise ValueError("max_age must be non-negative")

        if self.signal_type == "event":
            if self.kind != "event":
                raise ValueError("event signal specs must declare kind='event'")
            if self.interpolation != "none":
                raise ValueError("event signal specs must declare interpolation='none'")
        elif self.kind != "state":
            raise ValueError("non-event signal specs must declare kind='state'")

        if self.signal_type == "scalar" and self.shape not in (None, ()):
            raise ValueError("scalar signal specs cannot declare an array shape")

        if self.signal_type == "array" and self.shape is None:
            raise ValueError("array signal specs require a shape")

        if self.signal_type == "record":
            if not self.schema:
                raise ValueError("record signal specs require a schema")
            if self.shape is not None:
                raise ValueError("record signal specs cannot declare shape")

        if self.signal_type == "event" and self.shape is not None:
            raise ValueError("event signal specs cannot declare shape")

        if self.interpolation == "linear":
            if self.signal_type not in {"scalar", "array"}:
                raise ValueError("linear interpolation is only valid for numeric scalar or array signals")
            if self.dtype not in _NUMERIC_DTYPES:
                raise ValueError("linear interpolation requires a numeric dtype")

    @classmethod
    def scalar(
        cls,
        *,
        dtype: str = "float64",
        emitted_unit: Optional[str] = None,
        accepted_profiles: Optional[list[AcceptedSignalProfile | Mapping[str, Any]] | tuple[AcceptedSignalProfile, ...]] = None,
        interpolation: InterpolationPolicy = "zoh",
        max_age: Optional[float] = None,
        stale_policy: StalePolicy = "warn",
        description: Optional[str] = None,
    ) -> "SignalSpec":
        return cls(
            signal_type="scalar",
            kind="state",
            dtype=dtype,
            emitted_unit=emitted_unit,
            accepted_profiles=tuple(accepted_profiles) if accepted_profiles is not None else None,
            interpolation=interpolation,
            max_age=max_age,
            stale_policy=stale_policy,
            description=description,
        )

    @classmethod
    def array(
        cls,
        *,
        dtype: str,
        shape: tuple[int, ...],
        emitted_unit: Optional[str] = None,
        accepted_profiles: Optional[list[AcceptedSignalProfile | Mapping[str, Any]] | tuple[AcceptedSignalProfile, ...]] = None,
        interpolation: InterpolationPolicy = "zoh",
        max_age: Optional[float] = None,
        stale_policy: StalePolicy = "warn",
        description: Optional[str] = None,
    ) -> "SignalSpec":
        return cls(
            signal_type="array",
            kind="state",
            dtype=dtype,
            shape=shape,
            emitted_unit=emitted_unit,
            accepted_profiles=tuple(accepted_profiles) if accepted_profiles is not None else None,
            interpolation=interpolation,
            max_age=max_age,
            stale_policy=stale_policy,
            description=description,
        )

    @classmethod
    def record(
        cls,
        *,
        schema: Mapping[str, str],
        emitted_unit: Optional[str] = None,
        accepted_profiles: Optional[list[AcceptedSignalProfile | Mapping[str, Any]] | tuple[AcceptedSignalProfile, ...]] = None,
        max_age: Optional[float] = None,
        stale_policy: StalePolicy = "warn",
        description: Optional[str] = None,
    ) -> "SignalSpec":
        return cls(
            signal_type="record",
            kind="state",
            emitted_unit=emitted_unit,
            accepted_profiles=tuple(accepted_profiles) if accepted_profiles is not None else None,
            schema=dict(schema),
            max_age=max_age,
            stale_policy=stale_policy,
            description=description,
        )

    @classmethod
    def event(
        cls,
        *,
        schema: Optional[Mapping[str, str]] = None,
        emitted_unit: Optional[str] = None,
        accepted_profiles: Optional[list[AcceptedSignalProfile | Mapping[str, Any]] | tuple[AcceptedSignalProfile, ...]] = None,
        max_age: Optional[float] = None,
        stale_policy: StalePolicy = "warn",
        description: Optional[str] = None,
    ) -> "SignalSpec":
        return cls(
            signal_type="event",
            kind="event",
            interpolation="none",
            emitted_unit=emitted_unit,
            accepted_profiles=tuple(accepted_profiles) if accepted_profiles is not None else None,
            schema=dict(schema) if schema else None,
            max_age=max_age,
            stale_policy=stale_policy,
            description=description,
        )

    @property
    def is_numeric(self) -> bool:
        return self.dtype in _NUMERIC_DTYPES

    def input_profiles(self) -> tuple[AcceptedSignalProfile, ...]:
        if self.accepted_profiles is not None:
            return self.accepted_profiles
        return (
            AcceptedSignalProfile(
                signal_type=self.signal_type,
                dtype=self.dtype,
                shape=self.shape,
                schema=dict(self.schema) if self.schema is not None else None,
            ),
        )

    def match_input_profile(self, source: "SignalSpec") -> Optional[AcceptedSignalProfile]:
        for profile in self.input_profiles():
            if profile.matches_output(source):
                return profile
        return None

    def has_multiple_input_profiles(self) -> bool:
        return len(self.input_profiles()) > 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "kind": self.kind,
            "dtype": self.dtype,
            "shape": list(self.shape) if self.shape is not None else None,
            "emitted_unit": self.emitted_unit,
            "accepted_profiles": [profile.to_dict() for profile in self.accepted_profiles] if self.accepted_profiles is not None else None,
            "interpolation": self.interpolation,
            "max_age": self.max_age,
            "stale_policy": self.stale_policy,
            "schema": dict(self.schema) if self.schema is not None else None,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SignalSpec":
        return cls(
            signal_type=data["signal_type"],
            kind=data.get("kind", "state"),
            dtype=data.get("dtype"),
            shape=tuple(data["shape"]) if data.get("shape") is not None else None,
            emitted_unit=data.get("emitted_unit"),
            accepted_profiles=tuple(
                AcceptedSignalProfile.from_dict(profile) for profile in data["accepted_profiles"]
            ) if data.get("accepted_profiles") is not None else None,
            interpolation=data.get("interpolation", "zoh"),
            max_age=data.get("max_age"),
            stale_policy=data.get("stale_policy", "warn"),
            schema=dict(data["schema"]) if data.get("schema") is not None else None,
            description=data.get("description"),
        )


def validate_port_spec_direction(spec: SignalSpec, *, direction: str) -> None:
    if direction == "input":
        if spec.emitted_unit is not None:
            raise ValueError("input SignalSpec declarations cannot set emitted_unit")
        return
    if direction == "output":
        if spec.accepted_profiles is not None:
            raise ValueError("output SignalSpec declarations cannot set accepted_profiles")
        return
    raise ValueError(f"unknown signal direction: {direction!r}")


def validate_connection_specs(source: SignalSpec, target: SignalSpec) -> None:
    """Validate that one declared output port can feed one input port."""
    if source.kind != target.kind:
        raise ValueError(f"incompatible signal kinds: source '{source.kind}' cannot feed target '{target.kind}'")
    profile = target.match_input_profile(source)
    if profile is None:
        raise ValueError(
            "incompatible input profiles: "
            f"source ({source.signal_type}, {source.dtype}, {source.shape}, {source.emitted_unit}) "
            f"does not match any accepted input profile"
        )
    if target.interpolation == "linear" and not source.is_numeric:
        raise ValueError("linear interpolation requires a numeric source signal")


class BioSignal:
    """Base class for all typed 1.5 signals."""

    signal_type: SignalType = "record"

    def __init__(
        self,
        *args: Any,
        source: Optional[str] = None,
        name: Optional[str] = None,
        value: Any = None,
        emitted_at: Optional[float] = None,
        spec: Optional[SignalSpec | Mapping[str, Any]] = None,
    ) -> None:
        if self.__class__ is BioSignal:
            raise TypeError("BioSignal is an abstract base; construct ScalarSignal, ArraySignal, RecordSignal, or EventSignal")
        kwargs = {
            "source": source,
            "name": name,
            "value": value,
            "emitted_at": emitted_at,
            "spec": spec,
        }
        source, name, value, emitted_at, spec, _ = _coerce_init_args(args, kwargs)

        self.source = source
        self.name = name
        self.value = value
        self.emitted_at = emitted_at
        self.spec = self._normalize_spec(spec)
        self._validate_value()

    def _normalize_spec(self, spec: Optional[SignalSpec | Mapping[str, Any]]) -> Optional[SignalSpec]:
        if spec is None:
            return None
        if isinstance(spec, Mapping):
            spec = SignalSpec.from_dict(spec)
        if spec.signal_type != self.signal_type:
            raise ValueError(
                f"{self.__class__.__name__} requires signal_type='{self.signal_type}', got '{spec.signal_type}'"
            )
        return spec

    @property
    def kind(self) -> SignalKind:
        return "event" if self.signal_type == "event" else "state"

    def with_spec(self, spec: SignalSpec) -> "BioSignal":
        cloned = self._clone(spec=spec)
        return cloned

    def retarget(self, *, name: str) -> "BioSignal":
        return self._clone(name=name)

    def _clone(self, *, spec: Optional[SignalSpec] = None, name: Optional[str] = None) -> "BioSignal":
        return self.__class__(
            source=self.source,
            name=name or self.name,
            value=copy.deepcopy(self.value),
            emitted_at=self.emitted_at,
            spec=spec or self.spec,
        )

    def _validate_value(self) -> None:
        if self.signal_type == "scalar":
            disallowed = (list, tuple, dict)
            if _HAS_NUMPY:
                disallowed = disallowed + (_np.ndarray,)
            if isinstance(self.value, disallowed):
                raise TypeError("scalar signals require a scalar JSON value")
            _ensure_json_serializable(self.value)
            return

        if self.signal_type == "array":
            if _HAS_NUMPY and isinstance(self.value, _np.ndarray):
                actual_shape = tuple(self.value.shape)
            else:
                if not isinstance(self.value, list):
                    raise TypeError("array signals require list/tuple/ndarray-like values")
                _ensure_json_serializable(self.value)
                actual_shape = _infer_shape(self.value)
            if self.spec is not None and self.spec.shape is not None and actual_shape != tuple(self.spec.shape):
                raise ValueError(f"array signal shape {actual_shape} != declared shape {self.spec.shape}")
            return

        if self.signal_type == "record":
            if not isinstance(self.value, dict):
                raise TypeError("record signals require a mapping value")
            _ensure_json_serializable(self.value)
            if self.spec is not None and self.spec.schema is not None:
                expected_keys = set(self.spec.schema.keys())
                actual_keys = set(self.value.keys())
                if actual_keys != expected_keys:
                    raise ValueError(
                        f"record signal keys {sorted(actual_keys)} != declared schema keys {sorted(expected_keys)}"
                    )
            return

        if self.signal_type == "event":
            _ensure_json_serializable(self.value)
            if self.spec is not None and self.spec.schema is not None:
                if not isinstance(self.value, dict):
                    raise TypeError("schema-bound event signals require a mapping payload")
                expected_keys = set(self.spec.schema.keys())
                actual_keys = set(self.value.keys())
                if actual_keys != expected_keys:
                    raise ValueError(
                        f"event signal keys {sorted(actual_keys)} != declared schema keys {sorted(expected_keys)}"
                    )
            return

        raise ValueError(f"unknown signal type: {self.signal_type!r}")

    def _to_wire_value(self) -> Any:
        if self.signal_type == "array":
            if self.spec is None:
                raise ValueError("cannot serialize an array signal without a bound SignalSpec")
            return {
                "type": "array",
                "dtype": self.spec.dtype,
                "shape": list(self.spec.shape or (_infer_shape(self.value) if isinstance(self.value, list) else tuple(self.value.shape))),
                "data": self.value.tolist() if hasattr(self.value, "tolist") else copy.deepcopy(self.value),
            }
        return copy.deepcopy(self.value)

    def to_dict(self) -> dict[str, Any]:
        if self.spec is None:
            raise ValueError("cannot serialize a signal without a bound SignalSpec")
        return {
            "type": self.signal_type,
            "source": self.source,
            "name": self.name,
            "emitted_at": self.emitted_at,
            "spec": self.spec.to_dict(),
            "value": self._to_wire_value(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "BioSignal":
        signal_type = data.get("type")
        spec = SignalSpec.from_dict(data["spec"])
        signal_type = signal_type or spec.signal_type
        signal_cls = {
            "scalar": ScalarSignal,
            "array": ArraySignal,
            "record": RecordSignal,
            "event": EventSignal,
        }.get(signal_type)
        if signal_cls is None:
            raise ValueError(f"unknown signal type: {signal_type!r}")
        return signal_cls.from_wire_dict(data, spec=spec)

    @property
    def is_scalar(self) -> bool:
        return self.signal_type == "scalar"

    @property
    def is_array(self) -> bool:
        return self.signal_type == "array"

    def as_float(self) -> float:
        if self.signal_type != "scalar":
            raise ValueError(f"signal {self.name!r} is not scalar")
        return float(self.value)

    def as_array(self) -> np.ndarray:
        if self.signal_type != "array":
            raise ValueError(f"signal {self.name!r} is not an array")
        if _HAS_NUMPY:
            return _np.asarray(self.value)
        return self.value


class ScalarSignal(BioSignal):
    signal_type: SignalType = "scalar"

    def _validate_value(self) -> None:
        disallowed = (list, tuple, dict)
        if _HAS_NUMPY:
            disallowed = disallowed + (_np.ndarray,)
        if isinstance(self.value, disallowed):
            raise TypeError("scalar signals require a scalar JSON value")
        _ensure_json_serializable(self.value)

    def _clone(self, *, spec: Optional[SignalSpec] = None, name: Optional[str] = None) -> "ScalarSignal":
        return ScalarSignal(
            source=self.source,
            name=name or self.name,
            value=copy.deepcopy(self.value),
            emitted_at=self.emitted_at,
            spec=spec or self.spec,
        )

    def _to_wire_value(self) -> Any:
        return self.value

    @classmethod
    def from_wire_dict(cls, data: Mapping[str, Any], *, spec: SignalSpec) -> "ScalarSignal":
        return cls(
            source=data["source"],
            name=data["name"],
            value=data["value"],
            emitted_at=float(data["emitted_at"]),
            spec=spec,
        )


class ArraySignal(BioSignal):
    signal_type: SignalType = "array"

    def __init__(
        self,
        *args: Any,
        source: Optional[str] = None,
        name: Optional[str] = None,
        value: Any = None,
        emitted_at: Optional[float] = None,
        spec: Optional[SignalSpec | Mapping[str, Any]] = None,
    ) -> None:
        kwargs = {
            "source": source,
            "name": name,
            "value": value,
            "emitted_at": emitted_at,
            "spec": spec,
        }
        source, name, value, emitted_at, spec, _ = _coerce_init_args(args, kwargs)
        self._array = _normalize_array_value(value, spec.dtype if isinstance(spec, SignalSpec) else None)
        super().__init__(
            source=source,
            name=name,
            value=self._array,
            emitted_at=emitted_at,
            spec=spec,
        )

    def _validate_value(self) -> None:
        if _HAS_NUMPY and isinstance(self.value, _np.ndarray):
            actual_shape = tuple(self.value.shape)
            actual_dtype = str(self.value.dtype)
        else:
            if not isinstance(self.value, list):
                raise TypeError("array signals require list/tuple/ndarray-like values")
            _ensure_json_serializable(self.value)
            actual_shape = _infer_shape(self.value)
            actual_dtype = self.spec.dtype if self.spec is not None else None
        if self.spec is not None:
            if self.spec.shape is not None and actual_shape != tuple(self.spec.shape):
                raise ValueError(f"array signal shape {actual_shape} != declared shape {self.spec.shape}")
            if _HAS_NUMPY and isinstance(self.value, _np.ndarray) and self.spec.dtype is not None and actual_dtype != self.spec.dtype:
                try:
                    self.value = self.value.astype(self.spec.dtype)
                except TypeError as exc:
                    raise ValueError(
                        f"array signal dtype {actual_dtype!s} != declared dtype {self.spec.dtype}"
                    ) from exc

    def _clone(self, *, spec: Optional[SignalSpec] = None, name: Optional[str] = None) -> "ArraySignal":
        return ArraySignal(
            source=self.source,
            name=name or self.name,
            value=self.value.copy() if hasattr(self.value, "copy") else copy.deepcopy(self.value),
            emitted_at=self.emitted_at,
            spec=spec or self.spec,
        )

    def _to_wire_value(self) -> Any:
        if self.spec is None:
            raise ValueError("cannot serialize an array signal without a bound SignalSpec")
        return {
            "type": "array",
            "dtype": self.spec.dtype,
            "shape": list(self.spec.shape or (_infer_shape(self.value) if isinstance(self.value, list) else tuple(self.value.shape))),
            "data": self.value.tolist() if hasattr(self.value, "tolist") else copy.deepcopy(self.value),
        }

    @classmethod
    def from_wire_dict(cls, data: Mapping[str, Any], *, spec: SignalSpec) -> "ArraySignal":
        value = data["value"]
        if not isinstance(value, Mapping):
            raise TypeError("array signal wire values must be mapping objects")
        return cls(
            source=data["source"],
            name=data["name"],
            value=_normalize_array_value(value["data"], spec.dtype),
            emitted_at=float(data["emitted_at"]),
            spec=spec,
        )


class RecordSignal(BioSignal):
    signal_type: SignalType = "record"

    def _validate_value(self) -> None:
        if not isinstance(self.value, dict):
            raise TypeError("record signals require a mapping value")
        _ensure_json_serializable(self.value)
        if self.spec is not None and self.spec.schema is not None:
            expected_keys = set(self.spec.schema.keys())
            actual_keys = set(self.value.keys())
            if actual_keys != expected_keys:
                raise ValueError(
                    f"record signal keys {sorted(actual_keys)} != declared schema keys {sorted(expected_keys)}"
                )

    def _clone(self, *, spec: Optional[SignalSpec] = None, name: Optional[str] = None) -> "RecordSignal":
        return RecordSignal(
            source=self.source,
            name=name or self.name,
            value=copy.deepcopy(self.value),
            emitted_at=self.emitted_at,
            spec=spec or self.spec,
        )

    def _to_wire_value(self) -> Any:
        return copy.deepcopy(self.value)

    @classmethod
    def from_wire_dict(cls, data: Mapping[str, Any], *, spec: SignalSpec) -> "RecordSignal":
        return cls(
            source=data["source"],
            name=data["name"],
            value=dict(data["value"]),
            emitted_at=float(data["emitted_at"]),
            spec=spec,
        )


class EventSignal(BioSignal):
    signal_type: SignalType = "event"

    def _validate_value(self) -> None:
        _ensure_json_serializable(self.value)
        if self.spec is not None and self.spec.schema is not None:
            if not isinstance(self.value, dict):
                raise TypeError("schema-bound event signals require a mapping payload")
            expected_keys = set(self.spec.schema.keys())
            actual_keys = set(self.value.keys())
            if actual_keys != expected_keys:
                raise ValueError(
                    f"event signal keys {sorted(actual_keys)} != declared schema keys {sorted(expected_keys)}"
                )

    def _clone(self, *, spec: Optional[SignalSpec] = None, name: Optional[str] = None) -> "EventSignal":
        return EventSignal(
            source=self.source,
            name=name or self.name,
            value=copy.deepcopy(self.value),
            emitted_at=self.emitted_at,
            spec=spec or self.spec,
        )

    def _to_wire_value(self) -> Any:
        return copy.deepcopy(self.value)

    @classmethod
    def from_wire_dict(cls, data: Mapping[str, Any], *, spec: SignalSpec) -> "EventSignal":
        return cls(
            source=data["source"],
            name=data["name"],
            value=copy.deepcopy(data["value"]),
            emitted_at=float(data["emitted_at"]),
            spec=spec,
        )
