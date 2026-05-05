from __future__ import annotations

import pytest

from biosim import AcceptedSignalProfile, RecordSignal, ScalarSignal, SignalSpec
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
