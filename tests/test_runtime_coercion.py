from __future__ import annotations

import pytest

from biosim import AcceptedSignalProfile, ArraySignal, EventSignal, RecordSignal, ScalarSignal, SignalSpec
from biosim.runtime import coerce_typed_inputs


def test_coerce_typed_inputs_scalar_with_unit() -> None:
    declared = {
        "current": SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(
                    signal_type="scalar", dtype="float64", accepted_units=["mV"]
                )
            ]
        )
    }

    result = coerce_typed_inputs({"current": 1.5}, declared, source="run")

    signal = result["current"]
    assert isinstance(signal, ScalarSignal)
    assert signal.value == 1.5
    assert signal.spec.emitted_unit == "mV"


def test_coerce_typed_inputs_record_envelope() -> None:
    declared = {"state": SignalSpec.record(schema={"name": "str", "count": "int"})}

    result = coerce_typed_inputs(
        {"state": {"value": {"name": "cells", "count": 2}, "signal_type": "record"}},
        declared,
        source="run",
        time_value=2.0,
    )

    signal = result["state"]
    assert isinstance(signal, RecordSignal)
    assert signal.emitted_at == 2.0
    assert signal.value == {"name": "cells", "count": 2}


def test_coerce_typed_inputs_rejects_undeclared() -> None:
    with pytest.raises(RuntimeError, match="not declared"):
        coerce_typed_inputs({"x": 1}, {}, source="run")


def test_coerce_typed_inputs_returns_existing_matching_signal() -> None:
    declared = {
        "current": SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV"])
            ]
        )
    }
    signal = ScalarSignal(
        source="src",
        name="current",
        value=2.0,
        emitted_at=1.0,
        spec=SignalSpec.scalar(dtype="float64", emitted_unit="mV"),
    )

    assert coerce_typed_inputs({"current": signal}, declared, source="run")["current"] is signal


def test_coerce_typed_inputs_rejects_existing_signal_with_unaccepted_profile() -> None:
    declared = {
        "current": SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV"])
            ]
        )
    }
    signal = ScalarSignal(
        source="src",
        name="current",
        value=2.0,
        emitted_at=1.0,
        spec=SignalSpec.scalar(dtype="float64", emitted_unit="V"),
    )

    with pytest.raises(RuntimeError, match="emitted profile is not accepted"):
        coerce_typed_inputs({"current": signal}, declared, source="run")


def test_coerce_typed_inputs_rejects_wire_dict_with_unaccepted_profile() -> None:
    declared = {
        "current": SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV"])
            ]
        )
    }
    signal = ScalarSignal(
        source="src",
        name="current",
        value=2.0,
        emitted_at=1.0,
        spec=SignalSpec.scalar(dtype="float64", emitted_unit="V"),
    )

    with pytest.raises(RuntimeError, match="emitted profile is not accepted"):
        coerce_typed_inputs({"current": signal.to_dict()}, declared, source="run")


def test_coerce_typed_inputs_resolves_explicit_array_envelope_metadata() -> None:
    declared = {
        "features": SignalSpec.array(
            dtype="float32",
            shape=(2,),
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="array", dtype="float32", shape=(2,), accepted_units=["au"])
            ],
        )
    }

    result = coerce_typed_inputs(
        {
            "features": {
                "value": [1, 2],
                "signal_type": "array",
                "dtype": "float32",
                "shape": [2],
                "unit": "au",
                "emitted_at": 3.5,
            }
        },
        declared,
        source="run",
    )

    signal = result["features"]
    assert isinstance(signal, ArraySignal)
    assert signal.emitted_at == pytest.approx(3.5)
    assert signal.spec.emitted_unit == "au"
    assert list(signal.as_array()) == pytest.approx([1.0, 2.0])


def test_coerce_typed_inputs_requires_explicit_unit_for_ambiguous_units() -> None:
    declared = {
        "current": SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV", "V"])
            ]
        )
    }

    with pytest.raises(RuntimeError, match="accepts multiple units"):
        coerce_typed_inputs({"current": 2.0}, declared, source="run")


def test_coerce_typed_inputs_rejects_multiple_matching_profiles_without_envelope() -> None:
    declared = {
        "value": SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="scalar", dtype="float64"),
                AcceptedSignalProfile(signal_type="scalar"),
            ]
        )
    }

    with pytest.raises(RuntimeError, match="matches multiple accepted input profiles"):
        coerce_typed_inputs({"value": 2.0}, declared, source="run")


def test_coerce_typed_inputs_event_envelope_sets_event_kind() -> None:
    declared = {
        "pulse": SignalSpec.event(
            schema={"payload": "json"},
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="event", schema={"payload": "json"})
            ],
        )
    }

    result = coerce_typed_inputs(
        {"pulse": {"value": {"payload": "go"}, "signal_type": "event", "schema": {"payload": "json"}}},
        declared,
        source="run",
    )

    signal = result["pulse"]
    assert isinstance(signal, EventSignal)
    assert signal.kind == "event"
    assert signal.spec.interpolation == "none"
