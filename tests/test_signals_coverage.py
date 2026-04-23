"""Tests for biosim.signals V2 contracts."""

from __future__ import annotations

import numpy as np
import pytest

from biosim.signals import (
    AcceptedSignalProfile,
    ArraySignal,
    BioSignal,
    EventSignal,
    RecordSignal,
    ScalarSignal,
    SignalSpec,
    validate_connection_specs,
    validate_port_spec_direction,
)


def test_signal_spec_shape_list_to_tuple() -> None:
    spec = SignalSpec.array(dtype="float32", shape=[3, 4])  # type: ignore[arg-type]
    assert spec.shape == (3, 4)


def test_signal_spec_rejects_invalid_linear_interpolation() -> None:
    with pytest.raises(ValueError, match="linear interpolation is only valid"):
        SignalSpec.record(schema={"value": "str"}, description="bad").__class__(
            signal_type="record",
            kind="state",
            schema={"value": "str"},
            interpolation="linear",
        )


def test_scalar_signal_round_trip() -> None:
    spec = SignalSpec.scalar(dtype="float64", emitted_unit="mV")
    signal = ScalarSignal(source="src", name="x", value=1.5, emitted_at=0.25, spec=spec)
    payload = signal.to_dict()

    restored = BioSignal.from_dict(payload)

    assert isinstance(restored, ScalarSignal)
    assert restored.value == pytest.approx(1.5)
    assert restored.emitted_at == pytest.approx(0.25)
    assert restored.spec is not None
    assert restored.spec.emitted_unit == "mV"


def test_array_signal_serializes_with_envelope() -> None:
    spec = SignalSpec.array(dtype="float32", shape=(2,))
    signal = ArraySignal(source="src", name="x", value=np.array([1.0, 2.0], dtype=np.float32), emitted_at=0.1, spec=spec)

    payload = signal.to_dict()

    assert payload["value"] == {"type": "array", "dtype": "float32", "shape": [2], "data": [1.0, 2.0]}


def test_record_signal_validates_schema() -> None:
    spec = SignalSpec.record(schema={"label": "str", "count": "int"})
    signal = RecordSignal(
        source="src",
        name="record",
        value={"label": "ok", "count": 2},
        emitted_at=0.0,
        spec=spec,
    )
    assert signal.spec is not None
    assert signal.spec.schema == {"label": "str", "count": "int"}

    with pytest.raises(ValueError, match="schema keys"):
        RecordSignal(
            source="src",
            name="record",
            value={"label": "bad"},
            emitted_at=0.0,
            spec=spec,
        )


def test_event_signal_requires_event_spec() -> None:
    spec = SignalSpec.event(schema={"code": "str"})
    signal = EventSignal(source="src", name="pulse", value={"code": "go"}, emitted_at=1.0, spec=spec)
    assert signal.kind == "event"
    assert signal.emitted_at == pytest.approx(1.0)


def test_validate_connection_specs_checks_incompatible_profiles() -> None:
    with pytest.raises(ValueError, match="incompatible input profiles"):
        validate_connection_specs(
            SignalSpec.scalar(dtype="float64", emitted_unit="mV"),
            SignalSpec.scalar(
                accepted_profiles=[
                    AcceptedSignalProfile(signal_type="scalar", dtype="int32", accepted_units=["mA"]),
                ]
            ),
        )


def test_validate_connection_specs_accepts_matching_profile_membership() -> None:
    validate_connection_specs(
        SignalSpec.scalar(dtype="float64", emitted_unit="V"),
        SignalSpec.scalar(
            accepted_profiles=[
                AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV", "V", "kV"]),
                AcceptedSignalProfile(signal_type="scalar", dtype="int32", accepted_units=["mV"]),
            ]
        ),
    )


def test_port_direction_validation_rejects_mismatched_unit_fields() -> None:
    with pytest.raises(ValueError, match="input SignalSpec declarations cannot set emitted_unit"):
        validate_port_spec_direction(
            SignalSpec.scalar(dtype="float64", emitted_unit="mV"),
            direction="input",
        )

    with pytest.raises(ValueError, match="output SignalSpec declarations cannot set accepted_profiles"):
        validate_port_spec_direction(
            SignalSpec.scalar(
                accepted_profiles=[
                    AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV"]),
                ]
            ),
            direction="output",
        )


def test_input_profile_round_trip() -> None:
    spec = SignalSpec.scalar(
        accepted_profiles=[
            AcceptedSignalProfile(signal_type="scalar", dtype="float64", accepted_units=["mV", "V"]),
            AcceptedSignalProfile(signal_type="array", dtype="float32", shape=(2,), accepted_units=["mV"]),
        ]
    )

    restored = SignalSpec.from_dict(spec.to_dict())

    assert restored.accepted_profiles is not None
    assert len(restored.accepted_profiles) == 2
    assert restored.accepted_profiles[0].accepted_units == ("mV", "V")
    assert restored.accepted_profiles[1].shape == (2,)


def test_array_signal_as_array() -> None:
    signal = ArraySignal(
        source="src",
        name="x",
        value=[1, 2, 3],
        emitted_at=0.0,
        spec=SignalSpec.array(dtype="int64", shape=(3,)),
    )
    arr = signal.as_array()
    assert list(arr) == [1, 2, 3]
