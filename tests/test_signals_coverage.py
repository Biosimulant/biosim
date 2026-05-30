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
    coerce_float,
    make_signal,
    scalar_or_record_input,
    unwrap_payload,
    validate_connection_specs,
    validate_port_spec_direction,
)


def test_signal_spec_shape_list_to_tuple() -> None:
    spec = SignalSpec.array(dtype="float32", shape=[3, 4])  # type: ignore[arg-type]
    assert spec.shape == (3, 4)


def test_signal_spec_preserves_typed_input_metadata() -> None:
    spec = SignalSpec.record(
        schema={"payload": "json"},
        description="Boltz run options",
        value_type="record",
        format="json",
        required=False,
        default={"use_msa_server": True},
        advanced=True,
        examples=[{"sampling_steps": 50}],
        allowed_values=None,
        ui={"control": "json"},
    )

    restored = SignalSpec.from_dict(spec.to_dict())

    assert restored.value_type == "record"
    assert restored.format == "json"
    assert restored.required is False
    assert restored.default == {"use_msa_server": True}
    assert restored.advanced is True
    assert restored.examples == ({"sampling_steps": 50},)
    assert restored.ui == {"control": "json"}


def test_signal_spec_rejects_unknown_input_value_type() -> None:
    with pytest.raises(ValueError, match="value_type"):
        SignalSpec.scalar(value_type="toggle")  # type: ignore[arg-type]


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


def test_unwrap_payload_preserves_one_layer_default() -> None:
    assert unwrap_payload({"payload": {"payload": 3}}) == {"payload": 3}
    assert unwrap_payload({"payload": {"payload": 3}}, max_depth=2) == 3
    assert unwrap_payload({"payload": 1, "unit": "count"}) == {"payload": 1, "unit": "count"}


def test_coerce_float_handles_signal_and_record_carriers() -> None:
    signal = RecordSignal(
        source="src",
        name="x",
        value={"payload": {"count": "4.5"}},
        emitted_at=0.0,
        spec=SignalSpec.record(schema={"payload": "json"}),
    )

    assert coerce_float(signal) == pytest.approx(4.5)
    assert coerce_float({"value": "2.25"}) == pytest.approx(2.25)
    assert coerce_float(float("nan")) is None
    assert coerce_float("not-a-number") is None


def test_scalar_or_record_input_declares_common_profiles() -> None:
    spec = scalar_or_record_input("count", "A count input.")

    assert spec.signal_type == "scalar"
    assert spec.description == "A count input."
    assert spec.accepted_profiles is not None
    assert spec.accepted_profiles[0].accepted_units == ("count",)
    assert spec.accepted_profiles[1].schema == {"payload": "json"}


def test_make_signal_constructs_matching_signal_types() -> None:
    scalar = make_signal(
        SignalSpec.scalar(dtype="float64"),
        source="src",
        name="x",
        value=1.0,
        emitted_at=0.0,
    )
    record = make_signal(
        SignalSpec.record(schema={"payload": "json"}),
        source="src",
        name="r",
        value=[1, 2],
        emitted_at=0.0,
    )
    event = make_signal(
        SignalSpec.event(schema={"payload": "json"}),
        source="src",
        name="e",
        value="go",
        emitted_at=0.0,
    )

    assert isinstance(scalar, ScalarSignal)
    assert isinstance(record, RecordSignal)
    assert record.value == {"payload": [1, 2]}
    assert isinstance(event, EventSignal)
    assert event.value == {"payload": "go"}
