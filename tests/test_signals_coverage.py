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


def test_input_metadata_normalization_and_serialization_guards() -> None:
    spec = SignalSpec.scalar(
        value_type=" ",
        format="  csv  ",
        default={"ok": True},
        examples=["a", "b"],
        allowed_values=("a", "b"),
        file={"accept": ".csv"},
        ui={"widget": "select"},
    )

    assert spec.value_type is None
    assert spec.format == "csv"
    assert spec.examples == ("a", "b")
    assert spec.allowed_values == ("a", "b")
    assert spec.file == {"accept": ".csv"}
    assert spec.ui == {"widget": "select"}

    with pytest.raises(TypeError, match="examples"):
        SignalSpec(signal_type="scalar", examples={"bad": "mapping"})  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="file"):
        SignalSpec(signal_type="scalar", file=["bad"])  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="JSON-serializable"):
        SignalSpec.scalar(default={object()})


def test_signal_spec_shape_list_to_tuple() -> None:
    spec = SignalSpec.array(dtype="float32", shape=[3, 4])  # type: ignore[arg-type]
    assert spec.shape == (3, 4)


def test_accepted_signal_profile_validation_edges() -> None:
    profile = AcceptedSignalProfile(signal_type="scalar", shape=None, accepted_units=[" mV ", "V"])
    assert profile.accepted_units == ("mV", "V")
    assert AcceptedSignalProfile(accepted_units=[]).accepted_units is None

    with pytest.raises(ValueError, match="duplicates"):
        AcceptedSignalProfile(accepted_units=["mV", "mV"])
    with pytest.raises(ValueError, match="array accepted profiles require"):
        AcceptedSignalProfile(signal_type="array")
    with pytest.raises(ValueError, match="record accepted profiles require"):
        AcceptedSignalProfile(signal_type="record")
    with pytest.raises(ValueError, match="event accepted profiles cannot declare shape"):
        AcceptedSignalProfile(signal_type="event", shape=(1,))
    with pytest.raises(ValueError, match="scalar accepted profiles cannot"):
        AcceptedSignalProfile(signal_type="scalar", shape=(1,))
    with pytest.raises(ValueError, match="record accepted profiles cannot declare shape"):
        AcceptedSignalProfile(signal_type="record", schema={"x": "float"}, shape=(1,))
    with pytest.raises(ValueError, match="non-negative"):
        AcceptedSignalProfile(shape=(-1,))


def test_accepted_signal_profile_matching_handles_optional_constraints() -> None:
    output = SignalSpec.scalar(dtype="float64", emitted_unit="mV")

    assert AcceptedSignalProfile().matches_output(output)
    assert AcceptedSignalProfile(signal_type="array", shape=(1,)).matches_output(output) is False
    assert AcceptedSignalProfile(dtype="int64").matches_output(output) is False
    assert AcceptedSignalProfile(shape=(2,)).matches_output(output) is True
    assert AcceptedSignalProfile(accepted_units=("V",)).matches_output(output) is False
    assert AcceptedSignalProfile(accepted_units=("mV",)).matches_output(output) is True
    assert AcceptedSignalProfile(accepted_units=("mV",)).to_dict()["accepted_units"] == ["mV"]


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


@pytest.mark.parametrize(
    "factory, match",
    [
        (lambda: SignalSpec.scalar(emitted_unit=" "), "emitted_unit"),
        (lambda: SignalSpec.scalar(max_age=-1), "max_age"),
        (lambda: SignalSpec(signal_type="event", kind="state", interpolation="none"), "kind='event'"),
        (lambda: SignalSpec(signal_type="event", kind="event", interpolation="zoh"), "interpolation='none'"),
        (lambda: SignalSpec(signal_type="scalar", kind="event"), "kind='state'"),
        (lambda: SignalSpec(signal_type="scalar", shape=(1,)), "cannot declare an array shape"),
        (lambda: SignalSpec(signal_type="array"), "array signal specs require a shape"),
        (lambda: SignalSpec(signal_type="record"), "record signal specs require a schema"),
        (lambda: SignalSpec(signal_type="record", schema={"x": "float"}, shape=(1,)), "cannot declare shape"),
        (lambda: SignalSpec(signal_type="event", kind="event", interpolation="none", shape=(1,)), "cannot declare shape"),
        (lambda: SignalSpec.scalar(accepted_profiles=[object()]), "AcceptedSignalProfile"),
    ],
)
def test_signal_spec_rejects_invalid_contracts(factory, match: str) -> None:
    with pytest.raises((TypeError, ValueError), match=match):
        factory()


def test_signal_spec_rejects_invalid_linear_interpolation() -> None:
    with pytest.raises(ValueError, match="linear interpolation is only valid"):
        SignalSpec.record(schema={"value": "str"}, description="bad").__class__(
            signal_type="record",
            kind="state",
            schema={"value": "str"},
            interpolation="linear",
        )


def test_signal_spec_default_input_profiles_and_direction_errors() -> None:
    record = SignalSpec.record(schema={"x": "float"})
    profile = record.input_profiles()[0]
    assert profile.signal_type == "record"
    assert profile.schema == {"x": "float"}
    assert record.has_multiple_input_profiles() is False
    assert record.match_input_profile(SignalSpec.record(schema={"x": "float"})) == profile

    with pytest.raises(ValueError, match="unknown signal direction"):
        validate_port_spec_direction(record, direction="sideways")


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


def test_signal_constructor_argument_errors_and_clone_helpers() -> None:
    spec = SignalSpec.scalar(dtype="float64")
    signal = ScalarSignal("src", "x", 1.5, 0.25, spec=spec)

    assert signal.retarget(name="y").name == "y"
    assert signal.with_spec(spec).spec == spec
    assert signal.is_scalar is True
    assert signal.is_array is False
    assert signal.as_float() == pytest.approx(1.5)

    with pytest.raises(TypeError, match="abstract base"):
        BioSignal(source="src", name="x", value=1, emitted_at=0.0)
    with pytest.raises(TypeError, match="at most four positional"):
        ScalarSignal("src", "x", 1, 0.0, "extra", spec=spec)
    with pytest.raises(TypeError, match="source, name, and emitted_at"):
        ScalarSignal(source="src", name="x", value=1)
    with pytest.raises(TypeError, match="unexpected"):
        ScalarSignal("src", "x", 1, 0.0, extra=True)  # type: ignore[call-arg]
    with pytest.raises(ValueError, match="requires signal_type"):
        ScalarSignal(source="src", name="x", value=1, emitted_at=0.0, spec=SignalSpec.array(dtype="float64", shape=(1,)))
    with pytest.raises(ValueError, match="not scalar"):
        ArraySignal(source="src", name="a", value=[1], emitted_at=0.0, spec=SignalSpec.array(dtype="int64", shape=(1,))).as_float()


def test_scalar_signal_rejects_non_scalar_values() -> None:
    with pytest.raises(TypeError, match="scalar signals require"):
        ScalarSignal(source="src", name="x", value=[1], emitted_at=0.0, spec=SignalSpec.scalar(dtype="float64"))


def test_array_signal_serializes_with_envelope() -> None:
    spec = SignalSpec.array(dtype="float32", shape=(2,))
    signal = ArraySignal(source="src", name="x", value=np.array([1.0, 2.0], dtype=np.float32), emitted_at=0.1, spec=spec)

    payload = signal.to_dict()

    assert payload["value"] == {"type": "array", "dtype": "float32", "shape": [2], "data": [1.0, 2.0]}


def test_array_signal_round_trip_validation_edges() -> None:
    spec = SignalSpec.array(dtype="float32", shape=(2,))
    signal = ArraySignal(source="src", name="x", value=(1.0, 2.0), emitted_at=0.1, spec=spec)
    restored = BioSignal.from_dict(signal.to_dict())

    assert isinstance(restored, ArraySignal)
    assert list(restored.as_array()) == pytest.approx([1.0, 2.0])

    with pytest.raises(ValueError, match="ragged arrays|inhomogeneous"):
        ArraySignal(source="src", name="x", value=[[1], [2, 3]], emitted_at=0.0, spec=SignalSpec.array(dtype="float64", shape=(2, 1)))
    with pytest.raises(ValueError, match="array signal shape"):
        ArraySignal(source="src", name="x", value=[1.0], emitted_at=0.0, spec=spec)
    with pytest.raises(ValueError, match="without a bound SignalSpec"):
        ArraySignal(source="src", name="x", value=[1.0], emitted_at=0.0).to_dict()
    with pytest.raises(TypeError, match="wire values must be mapping"):
        ArraySignal.from_wire_dict({"source": "src", "name": "x", "value": [1.0], "emitted_at": 0.0}, spec=spec)
    with pytest.raises(ValueError, match="not an array"):
        ScalarSignal(source="src", name="x", value=1, emitted_at=0.0, spec=SignalSpec.scalar(dtype="int64")).as_array()


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


def test_record_and_event_signal_round_trip_edges() -> None:
    record_spec = SignalSpec.record(schema={"payload": "json"})
    record = RecordSignal(source="src", name="r", value={"payload": {"x": 1}}, emitted_at=0.0, spec=record_spec)
    restored_record = BioSignal.from_dict(record.to_dict())
    assert isinstance(restored_record, RecordSignal)
    assert restored_record.value == {"payload": {"x": 1}}

    event_spec = SignalSpec.event(schema={"payload": "json"})
    event = EventSignal(source="src", name="e", value={"payload": "go"}, emitted_at=0.0, spec=event_spec)
    restored_event = BioSignal.from_dict(event.to_dict())
    assert isinstance(restored_event, EventSignal)
    assert restored_event.value == {"payload": "go"}

    with pytest.raises(TypeError, match="record signals require"):
        RecordSignal(source="src", name="r", value=["bad"], emitted_at=0.0, spec=record_spec)
    with pytest.raises(TypeError, match="mapping payload"):
        EventSignal(source="src", name="e", value="bad", emitted_at=0.0, spec=event_spec)
    with pytest.raises(ValueError, match="event signal keys"):
        EventSignal(source="src", name="e", value={"other": "bad"}, emitted_at=0.0, spec=event_spec)
    with pytest.raises(ValueError, match="unknown signal type"):
        BioSignal.from_dict({"type": "unknown", "spec": record_spec.to_dict()})


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


def test_make_signal_infers_record_array_and_event_mappings() -> None:
    inferred_record = make_signal(source="src", name="r", value={"flag": True, "n": 2}, emitted_at=0.0)
    inferred_scalar = make_signal(source="src", name="s", value=2, emitted_at=0.0)
    declared_record = make_signal(
        SignalSpec.record(schema={"x": "float"}),
        source="src",
        name="declared",
        value={"x": 1.0},
        emitted_at=0.0,
    )
    declared_event = make_signal(
        SignalSpec.event(schema={"code": "str"}),
        source="src",
        name="event",
        value={"code": "go"},
        emitted_at=0.0,
    )

    assert isinstance(inferred_record, RecordSignal)
    assert inferred_record.spec is not None
    assert inferred_record.spec.schema == {"flag": "bool", "n": "int"}
    assert isinstance(inferred_scalar, ScalarSignal)
    assert inferred_scalar.spec is not None
    assert inferred_scalar.spec.dtype == "int"
    assert declared_record.value == {"x": 1.0}
    assert declared_event.value == {"code": "go"}


def test_validate_connection_specs_kind_and_linear_numeric_checks() -> None:
    with pytest.raises(ValueError, match="incompatible signal kinds"):
        validate_connection_specs(
            SignalSpec(signal_type="event", kind="event", interpolation="none"),
            SignalSpec.scalar(dtype="float64"),
        )
    with pytest.raises(ValueError, match="numeric source"):
        validate_connection_specs(
            SignalSpec.scalar(dtype="str"),
            SignalSpec.scalar(
                dtype="float64",
                accepted_profiles=[AcceptedSignalProfile(signal_type="scalar")],
                interpolation="linear",
            ),
        )
